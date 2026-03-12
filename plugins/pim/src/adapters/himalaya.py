"""Himalaya adapter — email messages via the himalaya CLI."""

import json
import subprocess
from typing import Any

from src.adapter import Adapter, Node, Edge, SyncResult
from src.uri import pim_uri


class HimalayaAdapter(Adapter):
    adapter_id = "himalaya"
    supported_types = ("message",)
    supported_operations = ("create", "query", "update", "close")
    supported_registers = ("scratch", "working", "log")

    def _run_himalaya(self, *args: str, stdin_data: str | None = None) -> subprocess.CompletedProcess:
        cmd = ["himalaya", *args]
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            input=stdin_data,
        )

    def _parse_json(self, result: subprocess.CompletedProcess) -> Any:
        if result.returncode != 0:
            raise RuntimeError(f"himalaya error: {result.stderr}")
        output = result.stdout.strip()
        if not output:
            return None
        return json.loads(output)

    # --- Register mapping ---

    def _register_for_folder(self, folder: str | None) -> str:
        if folder is None:
            return "scratch"
        folder_lower = folder.lower()
        if folder_lower in ("inbox", "inbox/"):
            return "scratch"
        if folder_lower in ("sent", "sent/", "archive", "archive/", "all", "all mail"):
            return "log"
        return "working"

    def _direction_for_message(self, msg: dict) -> str:
        """Determine direction based on folder context."""
        # This is a heuristic; real implementation would check sender against account
        return "inbound"

    # --- Node builder ---

    def _message_to_node(self, data: dict, folder: str | None = None) -> Node:
        sender = data.get("from", {})
        if isinstance(sender, dict):
            from_name = sender.get("name", "")
            from_addr = sender.get("addr", "")
        else:
            from_name = ""
            from_addr = str(sender)

        msg_id = str(data.get("id", ""))

        return Node({
            "id": pim_uri("message", "himalaya", msg_id),
            "type": "message",
            "register": self._register_for_folder(folder),
            "adapter": "himalaya",
            "native_id": msg_id,
            "attributes": {
                "subject": data.get("subject", ""),
                "from_name": from_name,
                "from_addr": from_addr,
                "date": data.get("date", ""),
                "direction": self._direction_for_message(data),
            },
            "body": None,
            "body_path": None,
            "source_op": None,
            "created_at": data.get("date"),
            "modified_at": None,
        })

    # --- Adapter interface ---

    def health_check(self) -> bool:
        result = self._run_himalaya("account", "list")
        return result.returncode == 0

    def resolve(self, native_id: str) -> Node | None:
        result = self._run_himalaya("read", native_id, "--output", "json")
        if result.returncode != 0:
            return None
        data = self._parse_json(result)
        if data is None:
            return None
        # himalaya read --output json may return the message object
        if isinstance(data, list) and len(data) > 0:
            data = data[0]
        return self._message_to_node(data)

    def reverse_resolve(self, uri: str) -> str | None:
        if "himalaya" not in uri:
            return None
        parts = uri.replace("pim://", "").split("/")
        if len(parts) == 3:
            return parts[2]
        return None

    def enumerate(self, obj_type: str, filters: dict | None = None, limit: int = 100, offset: int = 0) -> list[Node]:
        if obj_type != "message":
            return []
        folder = (filters or {}).get("folder", "INBOX")
        args = ["list", "--output", "json", "--page-size", str(limit)]
        args.extend(["--folder", folder])
        if offset > 0:
            page = (offset // limit) + 1
            args.extend(["--page", str(page)])
        result = self._run_himalaya(*args)
        items = self._parse_json(result) or []
        return [self._message_to_node(m, folder=folder) for m in items]

    def create_node(self, obj_type: str, attributes: dict, body: str | None = None) -> Node:
        if obj_type != "message":
            raise ValueError(f"Unsupported type for Himalaya: {obj_type}")

        subject = attributes.get("subject", "").replace("\n", " ").replace("\r", " ")
        to_addr = attributes.get("to", "").replace("\n", " ").replace("\r", " ")
        from_addr = attributes.get("from", "").replace("\n", " ").replace("\r", " ")

        # Compose RFC 2822 message
        lines = []
        if from_addr:
            lines.append(f"From: {from_addr}")
        if to_addr:
            lines.append(f"To: {to_addr}")
        lines.append(f"Subject: {subject}")
        lines.append("")
        lines.append(body or "")
        message_text = "\n".join(lines)

        result = self._run_himalaya("send", stdin_data=message_text)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to send message: {result.stderr}")

        # Return a synthetic node since himalaya send doesn't return the message ID
        return Node({
            "id": pim_uri("message", "himalaya", "sent"),
            "type": "message",
            "register": "log",
            "adapter": "himalaya",
            "native_id": "sent",
            "attributes": {
                "subject": subject,
                "direction": "outbound",
                "from_addr": from_addr,
                "to": to_addr,
            },
            "body": body,
            "body_path": None,
            "source_op": None,
            "created_at": None,
            "modified_at": None,
        })

    def query_nodes(self, obj_type: str, filters: dict | None = None) -> list[Node]:
        if obj_type != "message":
            return []
        filters = filters or {}

        text_search = filters.get("text_search")
        folder = filters.get("folder")

        if text_search:
            args = ["search", text_search, "--output", "json"]
            if folder:
                args.extend(["--folder", folder])
            result = self._run_himalaya(*args)
        else:
            args = ["list", "--output", "json"]
            if folder:
                args.extend(["--folder", folder])
            result = self._run_himalaya(*args)

        items = self._parse_json(result) or []
        return [self._message_to_node(m, folder=folder) for m in items]

    def update_node(self, native_id: str, changes: dict) -> Node:
        # Email messages are largely immutable; the main mutable operation is
        # moving to a different folder (register change)
        target_folder: str | None = None
        if "register" in changes or "folder" in changes:
            target_folder = changes.get("folder")
            if not target_folder:
                register = changes.get("register", "working")
                folder_map = {"scratch": "INBOX", "working": "INBOX", "log": "Archive"}
                target_folder = folder_map.get(register, "INBOX")
            result = self._run_himalaya("move", native_id, target_folder)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to move message: {result.stderr}")

        # Re-resolve; pass target folder so register is computed correctly
        result = self._run_himalaya("read", native_id, "--output", "json")
        if result.returncode != 0:
            raise ValueError(f"Message not found after update: {native_id}")
        data = self._parse_json(result)
        if data is None:
            raise ValueError(f"Message not found after update: {native_id}")
        if isinstance(data, list):
            if len(data) == 0:
                raise ValueError(f"Message not found after update: {native_id}")
            data = data[0]
        return self._message_to_node(data, folder=target_folder)

    def close_node(self, native_id: str, mode: str) -> None:
        if mode == "delete":
            result = self._run_himalaya("delete", native_id)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to delete message: {result.stderr}")
        elif mode == "archive":
            result = self._run_himalaya("move", native_id, "Archive")
            if result.returncode != 0:
                raise RuntimeError(f"Failed to archive message: {result.stderr}")
        else:
            raise ValueError(f"Himalaya adapter supports close modes: delete, archive. Got: {mode}")

    def sync(self, since: str | None = None) -> SyncResult:
        # Himalaya doesn't have a native sync-since; return recent INBOX messages
        result = self._run_himalaya("list", "--output", "json", "--folder", "INBOX")
        items = self._parse_json(result) or []
        changed = [self._message_to_node(m, folder="INBOX") for m in items]
        return SyncResult({"changed_nodes": changed, "changed_edges": []})

    def fetch_body(self, native_id: str) -> str | None:
        result = self._run_himalaya("read", native_id)
        if result.returncode != 0:
            return None
        return result.stdout

    def dispatch(self, native_id: str, method: str | None = None, params: dict | None = None) -> Any:
        if method == "send":
            result = self._run_himalaya("send", stdin_data=params.get("body", "") if params else "")
            if result.returncode != 0:
                raise RuntimeError(f"Send failed: {result.stderr}")
            return {"status": "sent"}
        raise NotImplementedError(f"Himalaya adapter does not support dispatch method: {method}")
