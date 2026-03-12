"""Apple Contacts adapter — contacts via osascript (AppleScript)."""

import json
import subprocess
from typing import Any

from src.adapter import Adapter, Node, SyncResult, escape_applescript
from src.uri import pim_uri


# --- AppleScript templates ---

AS_LIST_CONTACTS = """\
tell application "Contacts"
    set contactList to {}
    repeat with p in people
        set phones to {}
        repeat with ph in phones of p
            set end of phones to value of ph
        end repeat
        set emails to {}
        repeat with em in emails of p
            set end of emails to value of em
        end repeat
        set end of contactList to {id:id of p, |name|:name of p, ¬
            firstName:first name of p, lastName:last name of p, ¬
            organization:organization of p, ¬
            jobTitle:job title of p, ¬
            note:note of p, ¬
            emailList:emails, phoneList:phones}
    end repeat
    return contactList
end tell
"""

AS_GET_CONTACT = """\
tell application "Contacts"
    set p to first person whose id is "%CONTACT_ID%"
    set phones to {}
    repeat with ph in phones of p
        set end of phones to value of ph
    end repeat
    set emails to {}
    repeat with em in emails of p
        set end of emails to value of em
    end repeat
    return {id:id of p, |name|:name of p, ¬
        firstName:first name of p, lastName:last name of p, ¬
        organization:organization of p, ¬
        jobTitle:job title of p, ¬
        note:note of p, ¬
        emailList:emails, phoneList:phones}
end tell
"""

AS_CREATE_CONTACT = """\
tell application "Contacts"
    set newPerson to make new person with properties {first name:%FIRST%, last name:%LAST%}
    %EXTRAS%
    save
    return id of newPerson
end tell
"""

AS_UPDATE_CONTACT = """\
tell application "Contacts"
    set p to first person whose id is "%CONTACT_ID%"
    %UPDATES%
    save
    return id of p
end tell
"""

AS_DELETE_CONTACT = """\
tell application "Contacts"
    set p to first person whose id is "%CONTACT_ID%"
    delete p
    save
end tell
"""

AS_SEARCH_CONTACTS = """\
tell application "Contacts"
    set contactList to {}
    set searchResults to people whose name contains "%QUERY%"
    repeat with p in searchResults
        set end of contactList to {id:id of p, |name|:name of p, ¬
            firstName:first name of p, lastName:last name of p, ¬
            organization:organization of p}
    end repeat
    return contactList
end tell
"""


class AppleContactsAdapter(Adapter):
    adapter_id = "apple-contacts"
    supported_types = ("contact",)
    supported_operations = ("create", "query", "update", "close")
    supported_registers = ("reference",)

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

        # Fallback: field extraction for AS record format
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

    # --- Node builder ---

    def _contact_to_node(self, data: dict) -> Node:
        contact_id = data.get("id", "")
        name = data.get("name", "")
        first_name = data.get("firstName", "")
        last_name = data.get("lastName", "")
        organization = data.get("organization", "")
        job_title = data.get("jobTitle", "")
        note = data.get("note", "")

        emails = data.get("emailList", [])
        phones = data.get("phoneList", [])
        email = emails[0] if isinstance(emails, list) and emails else ""
        phone = phones[0] if isinstance(phones, list) and phones else ""

        if not name and (first_name or last_name):
            name = f"{first_name} {last_name}".strip()

        attrs: dict[str, Any] = {
            "name": name,
        }
        if email:
            attrs["email"] = email
        if phone:
            attrs["phone"] = phone
        if organization:
            attrs["organization"] = organization
        if job_title:
            attrs["role"] = job_title

        return Node({
            "id": pim_uri("contact", "apple-contacts", contact_id),
            "type": "contact",
            "register": "reference",  # Contacts are always reference
            "adapter": "apple-contacts",
            "native_id": contact_id,
            "attributes": attrs,
            "body": note if note else None,
            "body_path": None,
            "source_op": None,
            "created_at": None,
            "modified_at": None,
        })

    # --- Adapter interface ---

    def health_check(self) -> bool:
        result = self._run_osascript('tell application "Contacts" to name')
        return result.returncode == 0

    def resolve(self, native_id: str) -> Node | None:
        script = AS_GET_CONTACT.replace("%CONTACT_ID%", escape_applescript(native_id))
        result = self._run_osascript(script)
        if result.returncode != 0:
            return None
        records = self._parse_as_records(result.stdout)
        if not records:
            return None
        return self._contact_to_node(records[0])

    def reverse_resolve(self, uri: str) -> str | None:
        if "apple-contacts" not in uri:
            return None
        parts = uri.replace("pim://", "").split("/")
        if len(parts) >= 3:
            return "/".join(parts[2:])
        return None

    def enumerate(self, obj_type: str, filters: dict | None = None,
                  limit: int = 100, offset: int = 0) -> list[Node]:
        if obj_type != "contact":
            return []
        result = self._run_osascript(AS_LIST_CONTACTS)
        if result.returncode != 0:
            return []
        records = self._parse_as_records(result.stdout)
        nodes = [self._contact_to_node(r) for r in records]
        return nodes[offset:offset + limit]

    def create_node(self, obj_type: str, attributes: dict, body: str | None = None) -> Node:
        if obj_type != "contact":
            raise ValueError(f"Unsupported type for Apple Contacts: {obj_type}")

        name = attributes.get("name", "")
        parts = name.split(None, 1)
        first_name = parts[0] if parts else ""
        last_name = parts[1] if len(parts) > 1 else ""

        extras = []
        if attributes.get("email"):
            extras.append(
                f'make new email at end of emails of newPerson with properties '
                f'{{value:{json.dumps(attributes["email"])}}}'
            )
        if attributes.get("phone"):
            extras.append(
                f'make new phone at end of phones of newPerson with properties '
                f'{{value:{json.dumps(attributes["phone"])}}}'
            )
        if attributes.get("organization"):
            extras.append(
                f'set organization of newPerson to {json.dumps(attributes["organization"])}'
            )

        script = AS_CREATE_CONTACT
        script = script.replace("%FIRST%", json.dumps(first_name))
        script = script.replace("%LAST%", json.dumps(last_name))
        script = script.replace("%EXTRAS%", "\n    ".join(extras))

        result = self._run_osascript(script)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to create contact: {result.stderr}")

        contact_id = result.stdout.strip()
        return self._contact_to_node({
            "id": contact_id,
            "name": name,
            "firstName": first_name,
            "lastName": last_name,
            "organization": attributes.get("organization", ""),
            "emailList": [attributes["email"]] if attributes.get("email") else [],
            "phoneList": [attributes["phone"]] if attributes.get("phone") else [],
            "note": body or "",
        })

    def query_nodes(self, obj_type: str, filters: dict | None = None) -> list[Node]:
        if obj_type != "contact":
            return []
        filters = filters or {}

        text_search = filters.get("text_search")
        limit = filters.get("limit", 100)

        if text_search:
            script = AS_SEARCH_CONTACTS.replace("%QUERY%", escape_applescript(text_search))
            result = self._run_osascript(script)
        else:
            result = self._run_osascript(AS_LIST_CONTACTS)

        if result.returncode != 0:
            return []

        records = self._parse_as_records(result.stdout)
        nodes = [self._contact_to_node(r) for r in records]

        if "attributes" in filters:
            for key, value in filters["attributes"].items():
                nodes = [n for n in nodes if n["attributes"].get(key) == value]

        return nodes[:limit]

    def update_node(self, native_id: str, changes: dict) -> Node:
        attrs = changes.get("attributes", {})
        update_lines = []

        if "name" in attrs:
            parts = attrs["name"].split(None, 1)
            update_lines.append(f'set first name of p to {json.dumps(parts[0] if parts else "")}')
            update_lines.append(f'set last name of p to {json.dumps(parts[1] if len(parts) > 1 else "")}')
        if "organization" in attrs:
            update_lines.append(f'set organization of p to {json.dumps(attrs["organization"])}')

        updates_str = "\n    ".join(update_lines) if update_lines else ""
        script = AS_UPDATE_CONTACT.replace("%CONTACT_ID%", escape_applescript(native_id)).replace("%UPDATES%", updates_str)

        result = self._run_osascript(script)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to update contact: {result.stderr}")

        node = self.resolve(native_id)
        if node is None:
            raise ValueError(f"Contact not found after update: {native_id}")
        return node

    def close_node(self, native_id: str, mode: str) -> None:
        if mode == "delete":
            script = AS_DELETE_CONTACT.replace("%CONTACT_ID%", escape_applescript(native_id))
            result = self._run_osascript(script)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to delete contact: {result.stderr}")
        elif mode in ("archive", "complete"):
            pass  # No-op for contacts
        else:
            raise ValueError(
                f"Apple Contacts adapter supports close modes: delete, archive, complete. Got: {mode}"
            )

    def sync(self, since: str | None = None) -> SyncResult:
        result = self._run_osascript(AS_LIST_CONTACTS)
        if result.returncode != 0:
            return SyncResult({"changed_nodes": [], "changed_edges": []})
        records = self._parse_as_records(result.stdout)
        changed = [self._contact_to_node(r) for r in records]
        return SyncResult({"changed_nodes": changed, "changed_edges": []})

    def fetch_body(self, native_id: str) -> str | None:
        node = self.resolve(native_id)
        if node is None:
            return None
        return node.get("body")
