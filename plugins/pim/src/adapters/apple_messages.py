"""Apple Messages adapter — iMessage/SMS via chat.db (read-only)."""

import sqlite3
from pathlib import Path
from typing import Any

from src.adapter import Adapter, Node, SyncResult
from src.uri import pim_uri


# Default chat.db location
DEFAULT_CHAT_DB = Path.home() / "Library" / "Messages" / "chat.db"


class AppleMessagesAdapter(Adapter):
    """Read-only adapter for Apple Messages.

    Reads the iMessage/SMS database at ~/Library/Messages/chat.db.
    Writing is not supported — Messages doesn't support programmatic sending.
    """
    adapter_id = "apple-messages"
    supported_types = ("message",)
    supported_operations = ("query",)
    supported_registers = ("log",)

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DEFAULT_CHAT_DB

    def _connect(self) -> sqlite3.Connection:
        """Open a read-only connection to chat.db."""
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def _is_available(self) -> bool:
        return self.db_path.exists()

    # --- Node builder ---

    def _message_to_node(self, row: dict) -> Node:
        rowid = str(row.get("ROWID", ""))
        text = row.get("text", "") or ""
        date_val = row.get("date", 0)
        is_from_me = row.get("is_from_me", 0)
        handle_id = row.get("handle_id", "")
        chat_id = row.get("chat_identifier", "")

        # Apple Messages stores dates as nanoseconds since 2001-01-01
        # Convert to ISO format (approximate)
        date_str = ""
        if date_val and isinstance(date_val, (int, float)):
            import datetime
            epoch_2001 = datetime.datetime(2001, 1, 1)
            try:
                dt = epoch_2001 + datetime.timedelta(seconds=date_val / 1_000_000_000)
                date_str = dt.isoformat()
            except (OverflowError, ValueError):
                date_str = ""

        direction = "outbound" if is_from_me else "inbound"
        channel = "imessage"  # Default; could be SMS

        # Extract first line as subject/preview
        first_line = text.split("\n", 1)[0][:100] if text else ""

        attrs: dict[str, Any] = {
            "subject": first_line,
            "sent_at": date_str,
            "channel": channel,
            "direction": direction,
        }
        if handle_id:
            attrs["handle_id"] = str(handle_id)
        if chat_id:
            attrs["thread_id"] = chat_id

        return Node({
            "id": pim_uri("message", "apple-messages", rowid),
            "type": "message",
            "register": "log",  # Messages are historical
            "adapter": "apple-messages",
            "native_id": rowid,
            "attributes": attrs,
            "body": text,
            "body_path": None,
            "source_op": None,
            "created_at": date_str,
            "modified_at": None,
        })

    # --- Adapter interface ---

    def health_check(self) -> bool:
        return self._is_available()

    def resolve(self, native_id: str) -> Node | None:
        if not self._is_available():
            return None
        try:
            conn = self._connect()
            row = conn.execute(
                """SELECT m.ROWID, m.text, m.date, m.is_from_me, m.handle_id,
                          c.chat_identifier
                   FROM message m
                   LEFT JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
                   LEFT JOIN chat c ON cmj.chat_id = c.ROWID
                   WHERE m.ROWID = ?""",
                (int(native_id),)
            ).fetchone()
            conn.close()
            if row is None:
                return None
            return self._message_to_node(dict(row))
        except (sqlite3.Error, ValueError):
            return None

    def reverse_resolve(self, uri: str) -> str | None:
        if "apple-messages" not in uri:
            return None
        parts = uri.replace("pim://", "").split("/")
        if len(parts) == 3:
            return parts[2]
        return None

    def enumerate(self, obj_type: str, filters: dict | None = None,
                  limit: int = 100, offset: int = 0) -> list[Node]:
        if obj_type != "message" or not self._is_available():
            return []
        try:
            conn = self._connect()
            rows = conn.execute(
                """SELECT m.ROWID, m.text, m.date, m.is_from_me, m.handle_id,
                          c.chat_identifier
                   FROM message m
                   LEFT JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
                   LEFT JOIN chat c ON cmj.chat_id = c.ROWID
                   ORDER BY m.date DESC
                   LIMIT ? OFFSET ?""",
                (limit, offset)
            ).fetchall()
            conn.close()
            return [self._message_to_node(dict(r)) for r in rows]
        except sqlite3.Error:
            return []

    def create_node(self, obj_type: str, attributes: dict, body: str | None = None) -> Node:
        raise NotImplementedError(
            "Apple Messages adapter is read-only. Use himalaya or another adapter to send messages."
        )

    def query_nodes(self, obj_type: str, filters: dict | None = None) -> list[Node]:
        if obj_type != "message" or not self._is_available():
            return []
        filters = filters or {}

        text_search = filters.get("text_search")
        limit = filters.get("limit", 100)

        try:
            conn = self._connect()

            if text_search:
                rows = conn.execute(
                    """SELECT m.ROWID, m.text, m.date, m.is_from_me, m.handle_id,
                              c.chat_identifier
                       FROM message m
                       LEFT JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
                       LEFT JOIN chat c ON cmj.chat_id = c.ROWID
                       WHERE m.text LIKE ?
                       ORDER BY m.date DESC
                       LIMIT ?""",
                    (f"%{text_search}%", limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT m.ROWID, m.text, m.date, m.is_from_me, m.handle_id,
                              c.chat_identifier
                       FROM message m
                       LEFT JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
                       LEFT JOIN chat c ON cmj.chat_id = c.ROWID
                       ORDER BY m.date DESC
                       LIMIT ?""",
                    (limit,)
                ).fetchall()

            conn.close()
            nodes = [self._message_to_node(dict(r)) for r in rows]

            # Apply attribute filters client-side
            if "attributes" in filters:
                for key, value in filters["attributes"].items():
                    nodes = [n for n in nodes if n["attributes"].get(key) == value]

            return nodes
        except sqlite3.Error:
            return []

    def update_node(self, native_id: str, changes: dict) -> Node:
        raise NotImplementedError("Apple Messages adapter is read-only.")

    def close_node(self, native_id: str, mode: str) -> None:
        raise NotImplementedError("Apple Messages adapter is read-only.")

    def sync(self, since: str | None = None) -> SyncResult:
        if not self._is_available():
            return SyncResult({"changed_nodes": [], "changed_edges": []})
        try:
            conn = self._connect()
            query = """SELECT m.ROWID, m.text, m.date, m.is_from_me, m.handle_id,
                              c.chat_identifier
                       FROM message m
                       LEFT JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
                       LEFT JOIN chat c ON cmj.chat_id = c.ROWID
                       ORDER BY m.date DESC LIMIT 50"""
            rows = conn.execute(query).fetchall()
            conn.close()
            changed = [self._message_to_node(dict(r)) for r in rows]
            return SyncResult({"changed_nodes": changed, "changed_edges": []})
        except sqlite3.Error:
            return SyncResult({"changed_nodes": [], "changed_edges": []})

    def fetch_body(self, native_id: str) -> str | None:
        node = self.resolve(native_id)
        if node is None:
            return None
        return node.get("body")
