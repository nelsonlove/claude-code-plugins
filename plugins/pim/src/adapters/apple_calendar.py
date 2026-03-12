"""Apple Calendar adapter — events via icalbuddy (read) and osascript (write)."""

import json
import re
import subprocess
from datetime import datetime, timedelta
from typing import Any

from src.adapter import Adapter, Node, SyncResult
from src.uri import pim_uri


# icalbuddy is read-only. For write operations we use AppleScript via osascript.

AS_CREATE_EVENT = """\
tell application "Calendar"
    tell calendar %CALENDAR%
        set newEvent to make new event with properties {summary:%TITLE%, start date:date "%START%", end date:date "%END%", location:%LOCATION%}
        return uid of newEvent
    end tell
end tell
"""

AS_UPDATE_EVENT = """\
tell application "Calendar"
    repeat with c in calendars
        repeat with e in events of c
            if uid of e is "%UID%" then
                %UPDATES%
                return uid of e
            end if
        end repeat
    end repeat
end tell
"""

AS_DELETE_EVENT = """\
tell application "Calendar"
    repeat with c in calendars
        repeat with e in events of c
            if uid of e is "%UID%" then
                delete e
                return "deleted"
            end if
        end repeat
    end repeat
end tell
"""


class AppleCalendarAdapter(Adapter):
    adapter_id = "apple-calendar"
    supported_types = ("event",)
    supported_operations = ("create", "query", "update", "close")
    supported_registers = ("working", "log")

    def __init__(self, calendar_name: str = "Calendar"):
        self.calendar_name = calendar_name

    def _run_icalbuddy(self, *args: str) -> subprocess.CompletedProcess:
        cmd = ["icalbuddy", *args]
        return subprocess.run(cmd, capture_output=True, text=True)

    def _run_osascript(self, script: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
        )

    # --- icalbuddy output parsing ---

    def _parse_icalbuddy_events(self, output: str) -> list[dict]:
        """Parse icalbuddy output into event dicts.

        icalbuddy outputs events in a structured text format. We use
        -b "" -nc to get a clean format with fields on separate lines.
        """
        events = []
        if not output.strip():
            return events

        # Split by double newline (event separator)
        blocks = re.split(r"\n(?=\S)", output.strip())
        for block in blocks:
            event = self._parse_event_block(block)
            if event:
                events.append(event)
        return events

    def _parse_event_block(self, block: str) -> dict | None:
        """Parse a single event block from icalbuddy output."""
        lines = block.strip().split("\n")
        if not lines:
            return None

        event: dict[str, Any] = {}

        # First line is the title
        event["title"] = lines[0].strip()

        for line in lines[1:]:
            line = line.strip()
            if line.startswith("location:"):
                event["location"] = line[len("location:"):].strip()
            elif line.startswith("url:"):
                event["url"] = line[len("url:"):].strip()
            elif line.startswith("notes:"):
                event["notes"] = line[len("notes:"):].strip()
            elif line.startswith("uid:"):
                event["uid"] = line[len("uid:"):].strip()
            elif line.startswith("datetime:"):
                event["datetime_str"] = line[len("datetime:"):].strip()
            elif " - " in line and not event.get("datetime_str"):
                # Fallback: date range line like "Jan 15, 2026 at 10:00 - 11:00"
                event["datetime_str"] = line.strip()

        return event if event.get("title") else None

    # --- Register mapping ---

    def _register_for_event(self, event: dict) -> str:
        """Upcoming events are working; past events are log."""
        start = event.get("start")
        if start:
            try:
                dt = datetime.fromisoformat(start) if isinstance(start, str) else start
                if dt < datetime.now(dt.tzinfo):
                    return "log"
            except (ValueError, TypeError):
                pass
        return "working"

    # --- Node builder ---

    def _event_to_node(self, data: dict) -> Node:
        uid = data.get("uid", "")
        title = data.get("title", "")
        location = data.get("location")
        start = data.get("start")
        end = data.get("end")
        notes = data.get("notes")
        status = data.get("status", "confirmed")

        attrs: dict[str, Any] = {
            "title": title,
            "status": status,
        }
        if start:
            attrs["start"] = start
        if end:
            attrs["end"] = end
        if location:
            attrs["location"] = location

        return Node({
            "id": pim_uri("event", "apple-calendar", uid),
            "type": "event",
            "register": self._register_for_event(data),
            "adapter": "apple-calendar",
            "native_id": uid,
            "attributes": attrs,
            "body": notes,
            "body_path": None,
            "source_op": None,
            "created_at": None,
            "modified_at": None,
        })

    # --- Adapter interface ---

    def health_check(self) -> bool:
        result = self._run_icalbuddy("-V")
        return result.returncode == 0

    def resolve(self, native_id: str) -> Node | None:
        result = self._run_icalbuddy(
            "-uid", native_id,
            "-b", "", "-nc",
            "-iep", "title,location,notes,datetime,uid",
        )
        if result.returncode != 0:
            return None
        events = self._parse_icalbuddy_events(result.stdout)
        if not events:
            return None
        return self._event_to_node(events[0])

    def reverse_resolve(self, uri: str) -> str | None:
        if "apple-calendar" not in uri:
            return None
        parts = uri.replace("pim://", "").split("/")
        if len(parts) == 3:
            return parts[2]
        return None

    def enumerate(self, obj_type: str, filters: dict | None = None,
                  limit: int = 100, offset: int = 0) -> list[Node]:
        if obj_type != "event":
            return []
        result = self._run_icalbuddy(
            "-b", "", "-nc",
            "-iep", "title,location,notes,datetime,uid",
            "-li", str(limit + offset),
            "eventsToday+365",
        )
        items = self._parse_icalbuddy_events(result.stdout) if result.returncode == 0 else []
        nodes = [self._event_to_node(e) for e in items]
        return nodes[offset:offset + limit]

    def create_node(self, obj_type: str, attributes: dict, body: str | None = None) -> Node:
        if obj_type != "event":
            raise ValueError(f"Unsupported type for Apple Calendar: {obj_type}")

        title = attributes.get("title", "Untitled")
        start = attributes.get("start", "")
        end = attributes.get("end", "")
        location = attributes.get("location", "")
        calendar = json.dumps(self.calendar_name)

        # If no end time, default to 1 hour after start
        if not end and start:
            try:
                dt = datetime.fromisoformat(start)
                end_dt = dt + timedelta(hours=1)
                end = end_dt.strftime("%B %d, %Y at %I:%M:%S %p")
            except ValueError:
                end = start

        # Format start for AppleScript date string
        if start:
            try:
                dt = datetime.fromisoformat(start)
                start = dt.strftime("%B %d, %Y at %I:%M:%S %p")
            except ValueError:
                pass  # Use raw string if not ISO format
        if end:
            try:
                dt = datetime.fromisoformat(end)
                end = dt.strftime("%B %d, %Y at %I:%M:%S %p")
            except ValueError:
                pass

        script = AS_CREATE_EVENT
        script = script.replace("%CALENDAR%", calendar)
        script = script.replace("%TITLE%", json.dumps(title))
        script = script.replace("%START%", start)
        script = script.replace("%END%", end)
        script = script.replace("%LOCATION%", json.dumps(location))

        result = self._run_osascript(script)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to create event: {result.stderr}")

        uid = result.stdout.strip()
        return self._event_to_node({
            "uid": uid,
            "title": title,
            "start": attributes.get("start", ""),
            "end": attributes.get("end", ""),
            "location": location,
            "notes": body,
            "status": "confirmed",
        })

    def query_nodes(self, obj_type: str, filters: dict | None = None) -> list[Node]:
        if obj_type != "event":
            return []
        filters = filters or {}

        register = filters.get("register")
        text_search = filters.get("text_search")

        # Build icalbuddy command
        if register == "log":
            # Past events
            args = ["-b", "", "-nc", "-iep", "title,location,notes,datetime,uid",
                    "eventsFrom:today-365 to:today"]
        else:
            # Upcoming events (working register)
            args = ["-b", "", "-nc", "-iep", "title,location,notes,datetime,uid",
                    "eventsToday+365"]

        result = self._run_icalbuddy(*args)
        items = self._parse_icalbuddy_events(result.stdout) if result.returncode == 0 else []
        nodes = [self._event_to_node(e) for e in items]

        if register:
            nodes = [n for n in nodes if n["register"] == register]

        if text_search:
            search_lower = text_search.lower()
            nodes = [n for n in nodes if
                     search_lower in n["attributes"].get("title", "").lower() or
                     search_lower in (n.get("body") or "").lower()]

        if "attributes" in filters:
            for key, value in filters["attributes"].items():
                nodes = [n for n in nodes if n["attributes"].get(key) == value]

        limit = filters.get("limit", 100)
        return nodes[:limit]

    def update_node(self, native_id: str, changes: dict) -> Node:
        attrs = changes.get("attributes", {})
        update_lines = []

        if "title" in attrs:
            update_lines.append(f'set summary of e to {json.dumps(attrs["title"])}')
        if "location" in attrs:
            update_lines.append(f'set location of e to {json.dumps(attrs["location"])}')
        if "start" in attrs:
            update_lines.append(f'set start date of e to date "{attrs["start"]}"')
        if "end" in attrs:
            update_lines.append(f'set end date of e to date "{attrs["end"]}"')

        updates_str = "\n".join(update_lines) if update_lines else ""
        script = AS_UPDATE_EVENT.replace("%UID%", native_id).replace("%UPDATES%", updates_str)

        result = self._run_osascript(script)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to update event: {result.stderr}")

        # Re-resolve to get updated state
        node = self.resolve(native_id)
        if node is None:
            raise ValueError(f"Event not found after update: {native_id}")
        return node

    def close_node(self, native_id: str, mode: str) -> None:
        if mode == "delete":
            script = AS_DELETE_EVENT.replace("%UID%", native_id)
            result = self._run_osascript(script)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to delete event: {result.stderr}")
        elif mode == "cancel":
            # Set status to cancelled via update
            self.update_node(native_id, {
                "attributes": {"status": "cancelled"}
            })
        elif mode in ("complete", "archive"):
            # Events don't really "complete" — this is a no-op for past events
            pass
        else:
            raise ValueError(
                f"Apple Calendar adapter supports close modes: delete, cancel, complete, archive. Got: {mode}"
            )

    def sync(self, since: str | None = None) -> SyncResult:
        # icalbuddy doesn't support modified-since; return recent events
        result = self._run_icalbuddy(
            "-b", "", "-nc",
            "-iep", "title,location,notes,datetime,uid",
            "eventsToday+30",
        )
        items = self._parse_icalbuddy_events(result.stdout) if result.returncode == 0 else []
        changed = [self._event_to_node(e) for e in items]
        return SyncResult({"changed_nodes": changed, "changed_edges": []})

    def fetch_body(self, native_id: str) -> str | None:
        node = self.resolve(native_id)
        if node is None:
            return None
        return node.get("body")
