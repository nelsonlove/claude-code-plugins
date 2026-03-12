"""Safari adapter — reading list and bookmarks via osascript."""

import json
import subprocess
from typing import Any

from src.adapter import Adapter, Node, SyncResult
from src.uri import pim_uri


# --- AppleScript templates ---

AS_READING_LIST = """\
tell application "Safari"
    set rlItems to {}
    repeat with rl in reading list items
        set end of rlItems to {|url|:url of rl, title:title of rl, ¬
            |description|:description of rl, ¬
            dateAdded:date added of rl as «class isot» as string, ¬
            hasBeenRead:has been read of rl}
    end repeat
    return rlItems
end tell
"""

AS_BOOKMARKS = """\
tell application "Safari"
    set bmItems to {}
    repeat with bm in bookmarks
        set end of bmItems to {|url|:url of bm, title:title of bm}
    end repeat
    return bmItems
end tell
"""

AS_ADD_READING_LIST = """\
tell application "Safari"
    add reading list item "%URL%"
end tell
"""

AS_ADD_BOOKMARK = """\
tell application "Safari"
    make new bookmark with properties {url:"%URL%", title:%TITLE%}
end tell
"""


class SafariAdapter(Adapter):
    adapter_id = "safari"
    supported_types = ("resource",)
    supported_operations = ("create", "query")
    supported_registers = ("scratch", "reference")

    def _run_osascript(self, script: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["osascript", "-ss", "-e", script],
            capture_output=True,
            text=True,
        )

    def _parse_as_records(self, output: str) -> list[dict]:
        """Parse AppleScript record output into dicts."""
        if not output.strip():
            return []
        try:
            data = json.loads(output)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return [data]
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: simple field extraction
        records = []
        text = output.strip().strip("{}")
        record_texts = text.split("}, {")
        for rt in record_texts:
            rt = rt.strip().strip("{}")
            record: dict[str, str] = {}
            parts = rt.split(", ")
            for part in parts:
                if ":" not in part:
                    continue
                key, _, value = part.partition(":")
                key = key.strip().strip("|")
                value = value.strip().strip('"')
                record[key] = value
            if record:
                records.append(record)
        return records

    # --- Register mapping ---

    def _register_for_item(self, data: dict, source: str = "reading_list") -> str:
        """Reading list items are scratch; bookmarks are reference."""
        if source == "bookmark":
            return "reference"
        # Unread reading list items are scratch; read ones are reference
        if data.get("hasBeenRead"):
            return "reference"
        return "scratch"

    # --- Node builder ---

    def _item_to_node(self, data: dict, source: str = "reading_list") -> Node:
        url = data.get("url", "")
        title = data.get("title", url)
        description = data.get("description", "")
        date_added = data.get("dateAdded", "")
        has_been_read = data.get("hasBeenRead", False)

        # Use URL as native_id (stable across sessions)
        native_id = url

        attrs: dict[str, Any] = {
            "uri": url,
            "title": title,
            "read_status": "read" if has_been_read else "unread",
        }
        if description:
            attrs["description"] = description

        return Node({
            "id": pim_uri("resource", "safari", native_id),
            "type": "resource",
            "register": self._register_for_item(data, source),
            "adapter": "safari",
            "native_id": native_id,
            "attributes": attrs,
            "body": description,
            "body_path": None,
            "source_op": None,
            "created_at": date_added,
            "modified_at": None,
        })

    # --- Adapter interface ---

    def health_check(self) -> bool:
        result = self._run_osascript('tell application "Safari" to name')
        return result.returncode == 0

    def resolve(self, native_id: str) -> Node | None:
        # Native ID is URL; search reading list and bookmarks
        result = self._run_osascript(AS_READING_LIST)
        if result.returncode == 0:
            records = self._parse_as_records(result.stdout)
            for r in records:
                if r.get("url") == native_id:
                    return self._item_to_node(r, "reading_list")

        result = self._run_osascript(AS_BOOKMARKS)
        if result.returncode == 0:
            records = self._parse_as_records(result.stdout)
            for r in records:
                if r.get("url") == native_id:
                    return self._item_to_node(r, "bookmark")

        return None

    def reverse_resolve(self, uri: str) -> str | None:
        if "safari" not in uri:
            return None
        parts = uri.replace("pim://", "").split("/")
        if len(parts) >= 3:
            return "/".join(parts[2:])  # URL may contain slashes
        return None

    def enumerate(self, obj_type: str, filters: dict | None = None,
                  limit: int = 100, offset: int = 0) -> list[Node]:
        if obj_type != "resource":
            return []

        nodes = []
        result = self._run_osascript(AS_READING_LIST)
        if result.returncode == 0:
            records = self._parse_as_records(result.stdout)
            nodes.extend(self._item_to_node(r, "reading_list") for r in records)

        result = self._run_osascript(AS_BOOKMARKS)
        if result.returncode == 0:
            records = self._parse_as_records(result.stdout)
            nodes.extend(self._item_to_node(r, "bookmark") for r in records)

        return nodes[offset:offset + limit]

    def create_node(self, obj_type: str, attributes: dict, body: str | None = None) -> Node:
        if obj_type != "resource":
            raise ValueError(f"Unsupported type for Safari: {obj_type}")

        url = attributes.get("uri", "")
        title = attributes.get("title", url)
        target = attributes.get("target", "reading_list")

        if target == "bookmark":
            script = AS_ADD_BOOKMARK.replace("%URL%", url).replace("%TITLE%", json.dumps(title))
        else:
            script = AS_ADD_READING_LIST.replace("%URL%", url)

        result = self._run_osascript(script)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to add to Safari: {result.stderr}")

        return self._item_to_node({
            "url": url,
            "title": title,
            "description": body or "",
            "hasBeenRead": False,
        }, target)

    def query_nodes(self, obj_type: str, filters: dict | None = None) -> list[Node]:
        if obj_type != "resource":
            return []
        filters = filters or {}

        register = filters.get("register")
        text_search = filters.get("text_search")
        limit = filters.get("limit", 100)

        nodes = []

        # Get reading list items (scratch register)
        if register in (None, "scratch"):
            result = self._run_osascript(AS_READING_LIST)
            if result.returncode == 0:
                records = self._parse_as_records(result.stdout)
                nodes.extend(self._item_to_node(r, "reading_list") for r in records)

        # Get bookmarks (reference register)
        if register in (None, "reference"):
            result = self._run_osascript(AS_BOOKMARKS)
            if result.returncode == 0:
                records = self._parse_as_records(result.stdout)
                nodes.extend(self._item_to_node(r, "bookmark") for r in records)

        if register:
            nodes = [n for n in nodes if n["register"] == register]

        if text_search:
            search_lower = text_search.lower()
            nodes = [n for n in nodes if
                     search_lower in n["attributes"].get("title", "").lower() or
                     search_lower in n["attributes"].get("uri", "").lower() or
                     search_lower in (n.get("body") or "").lower()]

        if "attributes" in filters:
            for key, value in filters["attributes"].items():
                nodes = [n for n in nodes if n["attributes"].get(key) == value]

        return nodes[:limit]

    def update_node(self, native_id: str, changes: dict) -> Node:
        # Safari reading list/bookmarks are largely immutable
        # The only meaningful update is marking as read (reading list)
        node = self.resolve(native_id)
        if node is None:
            raise ValueError(f"Resource not found: {native_id}")
        return node

    def close_node(self, native_id: str, mode: str) -> None:
        if mode in ("archive", "complete", "delete"):
            # Safari doesn't support programmatic removal of reading list items
            # or bookmarks easily via AppleScript
            pass
        else:
            raise ValueError(
                f"Safari adapter supports close modes: archive, complete, delete. Got: {mode}"
            )

    def sync(self, since: str | None = None) -> SyncResult:
        nodes = self.enumerate("resource")
        return SyncResult({"changed_nodes": nodes, "changed_edges": []})

    def fetch_body(self, native_id: str) -> str | None:
        node = self.resolve(native_id)
        if node is None:
            return None
        return node.get("body")
