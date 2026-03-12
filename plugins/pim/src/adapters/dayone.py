"""Day One adapter — journal entries via the dayone2 CLI."""

import json
import subprocess
from typing import Any

from src.adapter import Adapter, Node, SyncResult
from src.uri import pim_uri


class DayOneAdapter(Adapter):
    adapter_id = "dayone"
    supported_types = ("entry",)
    supported_operations = ("create", "query", "update", "close")
    supported_registers = ("log",)

    def __init__(self, journal: str = "Journal"):
        self.journal = journal

    def _run_dayone(self, *args: str, stdin_data: str | None = None) -> subprocess.CompletedProcess:
        cmd = ["dayone2", *args]
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            input=stdin_data,
        )

    def _parse_json(self, result: subprocess.CompletedProcess) -> Any:
        if result.returncode != 0:
            raise RuntimeError(f"dayone2 error: {result.stderr}")
        output = result.stdout.strip()
        if not output:
            return None
        return json.loads(output)

    # --- Node builder ---

    def _entry_to_node(self, data: dict) -> Node:
        uuid = data.get("uuid", "")
        creation_date = data.get("creationDate", "")
        text = data.get("text", "")
        tags = data.get("tags", [])

        # Extract title from first line of text
        lines = text.split("\n", 1) if text else [""]
        title = lines[0].strip()
        # Strip markdown heading prefix
        if title.startswith("# "):
            title = title[2:]

        attrs: dict[str, Any] = {
            "title": title,
            "format": "markdown",
            "timestamp": creation_date,
        }
        if tags:
            attrs["tags"] = tags

        return Node({
            "id": pim_uri("entry", "dayone", uuid),
            "type": "entry",
            "register": "log",  # Journal entries are always historical
            "adapter": "dayone",
            "native_id": uuid,
            "attributes": attrs,
            "body": text,
            "body_path": None,
            "source_op": None,
            "created_at": creation_date,
            "modified_at": data.get("modifiedDate"),
        })

    # --- Adapter interface ---

    def health_check(self) -> bool:
        result = self._run_dayone("--version")
        return result.returncode == 0

    def resolve(self, native_id: str) -> Node | None:
        result = self._run_dayone(
            "view", "--uuid", native_id,
            "--journal", self.journal,
            "--output", "json",
        )
        if result.returncode != 0:
            return None
        data = self._parse_json(result)
        if data is None:
            return None
        # dayone2 view --output json returns {"entries": [...]}
        entries = data.get("entries", []) if isinstance(data, dict) else []
        if not entries:
            return None
        return self._entry_to_node(entries[0])

    def reverse_resolve(self, uri: str) -> str | None:
        if "dayone" not in uri:
            return None
        parts = uri.replace("pim://", "").split("/")
        if len(parts) == 3:
            return parts[2]
        return None

    def enumerate(self, obj_type: str, filters: dict | None = None,
                  limit: int = 100, offset: int = 0) -> list[Node]:
        if obj_type != "entry":
            return []
        result = self._run_dayone(
            "list", "--journal", self.journal,
            "--output", "json",
            "--max", str(limit + offset),
        )
        if result.returncode != 0:
            return []
        data = self._parse_json(result)
        entries = data.get("entries", []) if isinstance(data, dict) else []
        nodes = [self._entry_to_node(e) for e in entries]
        return nodes[offset:offset + limit]

    def create_node(self, obj_type: str, attributes: dict, body: str | None = None) -> Node:
        if obj_type != "entry":
            raise ValueError(f"Unsupported type for Day One: {obj_type}")

        text = body or ""
        title = attributes.get("title")
        if title and not text.startswith(f"# {title}"):
            text = f"# {title}\n\n{text}"

        args = ["new", "--journal", self.journal]

        tags = attributes.get("tags")
        if tags and isinstance(tags, list):
            for tag in tags:
                args.extend(["--tags", tag])

        timestamp = attributes.get("timestamp")
        if timestamp:
            args.extend(["--date", timestamp])

        result = self._run_dayone(*args, stdin_data=text)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to create entry: {result.stderr}")

        # dayone2 new outputs the UUID on success
        uuid = result.stdout.strip()
        # Sometimes output is "Created entry: <uuid>" or just the uuid
        if ":" in uuid:
            uuid = uuid.split(":")[-1].strip()

        return self._entry_to_node({
            "uuid": uuid,
            "creationDate": timestamp or "",
            "text": text,
            "tags": tags or [],
        })

    def query_nodes(self, obj_type: str, filters: dict | None = None) -> list[Node]:
        if obj_type != "entry":
            return []
        filters = filters or {}

        text_search = filters.get("text_search")
        limit = filters.get("limit", 100)

        if text_search:
            args = ["search", text_search,
                    "--journal", self.journal,
                    "--output", "json"]
        else:
            args = ["list", "--journal", self.journal,
                    "--output", "json",
                    "--max", str(limit)]

        result = self._run_dayone(*args)
        if result.returncode != 0:
            return []
        data = self._parse_json(result)
        entries = data.get("entries", []) if isinstance(data, dict) else []
        nodes = [self._entry_to_node(e) for e in entries]

        if "attributes" in filters:
            for key, value in filters["attributes"].items():
                nodes = [n for n in nodes if n["attributes"].get(key) == value]

        return nodes[:limit]

    def update_node(self, native_id: str, changes: dict) -> Node:
        body = changes.get("body")
        attrs = changes.get("attributes", {})

        if body is not None:
            title = attrs.get("title")
            if title and not body.startswith(f"# {title}"):
                body = f"# {title}\n\n{body}"

            result = self._run_dayone(
                "edit", "--uuid", native_id,
                "--journal", self.journal,
                stdin_data=body,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Failed to update entry: {result.stderr}")

        if "tags" in attrs:
            tags = attrs["tags"]
            if isinstance(tags, list):
                for tag in tags:
                    self._run_dayone(
                        "tag", tag, "--uuid", native_id,
                        "--journal", self.journal,
                    )

        node = self.resolve(native_id)
        if node is None:
            raise ValueError(f"Entry not found after update: {native_id}")
        return node

    def close_node(self, native_id: str, mode: str) -> None:
        if mode == "delete":
            result = self._run_dayone(
                "delete", "--uuid", native_id,
                "--journal", self.journal,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Failed to delete entry: {result.stderr}")
        elif mode in ("archive", "complete"):
            # Journal entries are already in log register; archive is a no-op
            pass
        else:
            raise ValueError(
                f"Day One adapter supports close modes: delete, archive, complete. Got: {mode}"
            )

    def sync(self, since: str | None = None) -> SyncResult:
        args = ["list", "--journal", self.journal,
                "--output", "json", "--max", "50"]
        if since:
            args.extend(["--after", since])
        result = self._run_dayone(*args)
        if result.returncode != 0:
            return SyncResult({"changed_nodes": [], "changed_edges": []})
        data = self._parse_json(result)
        entries = data.get("entries", []) if isinstance(data, dict) else []
        changed = [self._entry_to_node(e) for e in entries]
        return SyncResult({"changed_nodes": changed, "changed_edges": []})

    def fetch_body(self, native_id: str) -> str | None:
        node = self.resolve(native_id)
        if node is None:
            return None
        return node.get("body")
