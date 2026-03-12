"""Apple Notes adapter — notes via osascript (AppleScript)."""

import json
import subprocess
from typing import Any

from src.adapter import Adapter, Node, SyncResult, escape_applescript
from src.uri import pim_uri


# --- AppleScript templates ---

AS_LIST_NOTES = """\
tell application "Notes"
    set noteList to {}
    repeat with n in notes
        set end of noteList to {id:id of n, |name|:name of n, body:plaintext of n, ¬
            creationDate:(creation date of n as «class isot» as string), ¬
            modificationDate:(modification date of n as «class isot» as string), ¬
            folderId:id of container of n, ¬
            folderName:name of container of n}
    end repeat
    return noteList
end tell
"""

AS_GET_NOTE = """\
tell application "Notes"
    set n to first note whose id is "%NOTE_ID%"
    return {id:id of n, |name|:name of n, body:plaintext of n, ¬
        htmlBody:body of n, ¬
        creationDate:(creation date of n as «class isot» as string), ¬
        modificationDate:(modification date of n as «class isot» as string), ¬
        folderId:id of container of n, ¬
        folderName:name of container of n}
end tell
"""

AS_CREATE_NOTE = """\
tell application "Notes"
    set targetFolder to %FOLDER%
    set newNote to make new note at targetFolder with properties {name:%TITLE%, body:%BODY%}
    return {id:id of newNote, |name|:name of newNote}
end tell
"""

AS_UPDATE_NOTE = """\
tell application "Notes"
    set n to first note whose id is "%NOTE_ID%"
    %UPDATES%
    return {id:id of n, |name|:name of n}
end tell
"""

AS_DELETE_NOTE = """\
tell application "Notes"
    set n to first note whose id is "%NOTE_ID%"
    delete n
end tell
"""

AS_SEARCH_NOTES = """\
tell application "Notes"
    set noteList to {}
    set searchResults to notes whose name contains "%QUERY%" or plaintext contains "%QUERY%"
    repeat with n in searchResults
        set end of noteList to {id:id of n, |name|:name of n, body:plaintext of n, ¬
            creationDate:(creation date of n as «class isot» as string), ¬
            modificationDate:(modification date of n as «class isot» as string), ¬
            folderId:id of container of n, ¬
            folderName:name of container of n}
    end repeat
    return noteList
end tell
"""

AS_LIST_FOLDERS = """\
tell application "Notes"
    set folderList to {}
    repeat with f in folders
        set end of folderList to {id:id of f, |name|:name of f}
    end repeat
    return folderList
end tell
"""


class AppleNotesAdapter(Adapter):
    adapter_id = "apple-notes"
    supported_types = ("note",)
    supported_operations = ("create", "query", "update", "close")
    supported_registers = ("scratch", "reference")

    def _run_osascript(self, script: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
        )

    def _run_osascript_json(self, script: str) -> subprocess.CompletedProcess:
        """Run AppleScript that returns JSON via a wrapper."""
        # Wrap the script to output JSON via osascript -ss
        return subprocess.run(
            ["osascript", "-ss", "-e", script],
            capture_output=True,
            text=True,
        )

    def _parse_as_records(self, output: str) -> list[dict]:
        """Parse AppleScript record list output into dicts.

        AppleScript outputs records like:
        {id:"x-coredata://...", |name|:"Title", body:"Content", ...}

        This is a best-effort parser for the structured output.
        """
        if not output.strip():
            return []

        # Try JSON first (if we managed to get JSON output)
        try:
            data = json.loads(output)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return [data]
        except (json.JSONDecodeError, ValueError):
            pass

        # For AppleScript record output, we return the raw text
        # and let the caller handle parsing. In practice, we use
        # a JSON-returning wrapper or parse the structured output.
        return self._parse_applescript_records(output)

    def _parse_applescript_records(self, output: str) -> list[dict]:
        """Parse AppleScript record format into dicts.

        Handles output like:
        {{id:"x-coredata://123", |name|:"Title", body:"Content"}, ...}
        """
        records = []
        # Strip outer braces for list of records
        text = output.strip()
        if not text:
            return records

        # Simple field extraction — handles the common AS record format
        # Split on "}, {" to separate records
        # This is intentionally simple; complex nested records aren't expected
        record_texts = text.split("}, {")
        for rt in record_texts:
            rt = rt.strip().strip("{}")
            record: dict[str, str] = {}
            # Split on ", " but respect quoted strings
            parts = self._split_as_fields(rt)
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

    def _split_as_fields(self, text: str) -> list[str]:
        """Split AppleScript record fields respecting quoted strings."""
        fields = []
        current = []
        in_quotes = False
        for char in text:
            if char == '"' and (not current or current[-1] != '\\'):
                in_quotes = not in_quotes
                current.append(char)
            elif char == ',' and not in_quotes:
                fields.append("".join(current).strip())
                current = []
            else:
                current.append(char)
        if current:
            fields.append("".join(current).strip())
        return fields

    # --- Register mapping ---

    def _register_for_note(self, data: dict) -> str:
        """Notes in the default 'Notes' folder are scratch; others are reference."""
        folder = data.get("folderName", "")
        if folder.lower() in ("notes", "recently deleted", ""):
            return "scratch"
        return "reference"

    # --- Node builder ---

    def _note_to_node(self, data: dict) -> Node:
        note_id = data.get("id", "")
        title = data.get("name", "")
        body = data.get("body", "")
        html_body = data.get("htmlBody")
        folder_name = data.get("folderName", "")
        creation_date = data.get("creationDate", "")
        modification_date = data.get("modificationDate", "")

        attrs: dict[str, Any] = {
            "title": title,
            "format": "richtext" if html_body else "plaintext",
        }
        if folder_name:
            attrs["folder"] = folder_name

        return Node({
            "id": pim_uri("note", "apple-notes", note_id),
            "type": "note",
            "register": self._register_for_note(data),
            "adapter": "apple-notes",
            "native_id": note_id,
            "attributes": attrs,
            "body": body,
            "body_path": None,
            "source_op": None,
            "created_at": creation_date,
            "modified_at": modification_date,
        })

    # --- Adapter interface ---

    def health_check(self) -> bool:
        result = self._run_osascript('tell application "Notes" to name')
        return result.returncode == 0

    def resolve(self, native_id: str) -> Node | None:
        script = AS_GET_NOTE.replace("%NOTE_ID%", escape_applescript(native_id))
        result = self._run_osascript_json(script)
        if result.returncode != 0:
            return None
        records = self._parse_as_records(result.stdout)
        if not records:
            return None
        return self._note_to_node(records[0])

    def reverse_resolve(self, uri: str) -> str | None:
        if "apple-notes" not in uri:
            return None
        parts = uri.replace("pim://", "").split("/")
        if len(parts) >= 3:
            return "/".join(parts[2:])  # Note IDs may contain slashes
        return None

    def enumerate(self, obj_type: str, filters: dict | None = None,
                  limit: int = 100, offset: int = 0) -> list[Node]:
        if obj_type != "note":
            return []
        result = self._run_osascript_json(AS_LIST_NOTES)
        if result.returncode != 0:
            return []
        records = self._parse_as_records(result.stdout)
        nodes = [self._note_to_node(r) for r in records]
        return nodes[offset:offset + limit]

    def create_node(self, obj_type: str, attributes: dict, body: str | None = None) -> Node:
        if obj_type != "note":
            raise ValueError(f"Unsupported type for Apple Notes: {obj_type}")

        title = attributes.get("title", "Untitled")
        folder = attributes.get("folder")

        if folder:
            folder_ref = f'folder "{escape_applescript(folder)}"'
        else:
            folder_ref = "default account"

        html_body = body or ""
        # Wrap in basic HTML if plain text
        if body and not body.strip().startswith("<"):
            html_body = f"<div>{body}</div>"

        script = AS_CREATE_NOTE
        script = script.replace("%FOLDER%", folder_ref)
        script = script.replace("%TITLE%", json.dumps(title))
        script = script.replace("%BODY%", json.dumps(html_body))

        result = self._run_osascript(script)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to create note: {result.stderr}")

        # Parse the returned record for the new note ID
        records = self._parse_as_records(result.stdout)
        note_id = records[0].get("id", "") if records else ""

        return self._note_to_node({
            "id": note_id,
            "name": title,
            "body": body or "",
            "folderName": folder or "",
        })

    def query_nodes(self, obj_type: str, filters: dict | None = None) -> list[Node]:
        if obj_type != "note":
            return []
        filters = filters or {}

        text_search = filters.get("text_search")
        register = filters.get("register")
        limit = filters.get("limit", 100)

        if text_search:
            script = AS_SEARCH_NOTES.replace("%QUERY%", escape_applescript(text_search))
            result = self._run_osascript_json(script)
        else:
            result = self._run_osascript_json(AS_LIST_NOTES)

        if result.returncode != 0:
            return []

        records = self._parse_as_records(result.stdout)
        nodes = [self._note_to_node(r) for r in records]

        if register:
            nodes = [n for n in nodes if n["register"] == register]

        if "attributes" in filters:
            for key, value in filters["attributes"].items():
                nodes = [n for n in nodes if n["attributes"].get(key) == value]

        return nodes[:limit]

    def update_node(self, native_id: str, changes: dict) -> Node:
        attrs = changes.get("attributes", {})
        update_lines = []

        if "title" in attrs:
            update_lines.append(f'set name of n to {json.dumps(attrs["title"])}')
        if "body" in changes:
            body = changes["body"]
            if not body.strip().startswith("<"):
                body = f"<div>{body}</div>"
            update_lines.append(f'set body of n to {json.dumps(body)}')

        updates_str = "\n    ".join(update_lines) if update_lines else ""
        script = AS_UPDATE_NOTE.replace("%NOTE_ID%", escape_applescript(native_id)).replace("%UPDATES%", updates_str)

        result = self._run_osascript(script)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to update note: {result.stderr}")

        node = self.resolve(native_id)
        if node is None:
            raise ValueError(f"Note not found after update: {native_id}")
        return node

    def close_node(self, native_id: str, mode: str) -> None:
        if mode == "delete":
            script = AS_DELETE_NOTE.replace("%NOTE_ID%", escape_applescript(native_id))
            result = self._run_osascript(script)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to delete note: {result.stderr}")
        elif mode in ("archive", "complete"):
            # No native archive in Apple Notes; this is a no-op
            pass
        else:
            raise ValueError(
                f"Apple Notes adapter supports close modes: delete, archive, complete. Got: {mode}"
            )

    def sync(self, since: str | None = None) -> SyncResult:
        result = self._run_osascript_json(AS_LIST_NOTES)
        if result.returncode != 0:
            return SyncResult({"changed_nodes": [], "changed_edges": []})
        records = self._parse_as_records(result.stdout)
        changed = [self._note_to_node(r) for r in records]
        return SyncResult({"changed_nodes": changed, "changed_edges": []})

    def fetch_body(self, native_id: str) -> str | None:
        node = self.resolve(native_id)
        if node is None:
            return None
        return node.get("body")
