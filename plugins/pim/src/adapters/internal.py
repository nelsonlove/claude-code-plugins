"""Internal adapter — SQLite-backed storage for all 8 types."""

import json
import sqlite3
from pathlib import Path

from src.adapter import Adapter, Node, Edge, SyncResult
from src.uri import pim_uri, parse_uri, generate_id
from src.constants import OBJECT_TYPES, REGISTERS, BODY_SIZE_THRESHOLD


class InternalAdapter(Adapter):
    adapter_id = "internal"
    supported_types = OBJECT_TYPES
    supported_operations = ("create", "query", "update", "close")
    supported_registers = REGISTERS

    def __init__(self, conn: sqlite3.Connection, data_dir: Path):
        self.conn = conn
        self.data_dir = data_dir
        self.blobs_dir = data_dir / "blobs"

    def resolve(self, native_id: str) -> Node | None:
        row = self.conn.execute(
            "SELECT * FROM nodes WHERE native_id = ?", (native_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_node(row)

    def reverse_resolve(self, uri: str) -> str | None:
        row = self.conn.execute(
            "SELECT native_id FROM nodes WHERE id = ?", (uri,)
        ).fetchone()
        return row["native_id"] if row else None

    def enumerate(self, obj_type: str, filters: dict | None = None, limit: int = 100, offset: int = 0) -> list[Node]:
        rows = self.conn.execute(
            "SELECT * FROM nodes WHERE type = ? AND adapter = 'internal' ORDER BY modified_at DESC LIMIT ? OFFSET ?",
            (obj_type, limit, offset)
        ).fetchall()
        return [self._row_to_node(r) for r in rows]

    def create_node(self, obj_type: str, attributes: dict, body: str | None = None) -> Node:
        native_id = generate_id(obj_type)
        uri = pim_uri(obj_type, "internal", native_id)

        body_field = None
        body_path = None
        if body is not None:
            if len(body.encode("utf-8")) > BODY_SIZE_THRESHOLD:
                self.blobs_dir.mkdir(parents=True, exist_ok=True)
                blob_path = self.blobs_dir / native_id
                blob_path.write_text(body, encoding="utf-8")
                body_path = str(blob_path)
            else:
                body_field = body

        self.conn.execute(
            """INSERT INTO nodes (id, type, register, adapter, native_id, attributes, body, body_path)
               VALUES (?, ?, 'scratch', 'internal', ?, ?, ?, ?)""",
            (uri, obj_type, native_id, json.dumps(attributes), body_field, body_path)
        )
        # Commit managed by orchestrator for transaction control

        return self.resolve(native_id)

    def query_nodes(self, obj_type: str, filters: dict | None = None) -> list[Node]:
        filters = filters or {}
        text_search = filters.get("text_search")

        if text_search:
            rows = self.conn.execute(
                """SELECT nodes.* FROM nodes
                   JOIN nodes_fts ON nodes.rowid = nodes_fts.rowid
                   WHERE nodes.type = ? AND nodes.adapter = 'internal'
                   AND nodes_fts MATCH ?
                   ORDER BY rank""",
                (obj_type, text_search)
            ).fetchall()
        else:
            query = "SELECT * FROM nodes WHERE type = ? AND adapter = 'internal'"
            params: list = [obj_type]

            if "register" in filters:
                query += " AND register = ?"
                params.append(filters["register"])

            if "attributes" in filters:
                for key, value in filters["attributes"].items():
                    query += " AND json_extract(attributes, ?) = ?"
                    params.extend([f"$.{key}", value])

            query += " ORDER BY modified_at DESC"

            if "limit" in filters:
                query += " LIMIT ?"
                params.append(filters["limit"])

            rows = self.conn.execute(query, params).fetchall()

        return [self._row_to_node(r) for r in rows]

    def update_node(self, native_id: str, changes: dict) -> Node:
        node = self.resolve(native_id)
        if node is None:
            raise ValueError(f"Node not found: {native_id}")

        if "attributes" in changes:
            current_attrs = node["attributes"]
            current_attrs.update(changes["attributes"])
            self.conn.execute(
                "UPDATE nodes SET attributes = ?, modified_at = CURRENT_TIMESTAMP WHERE native_id = ?",
                (json.dumps(current_attrs), native_id)
            )

        if "register" in changes:
            self.conn.execute(
                "UPDATE nodes SET register = ?, modified_at = CURRENT_TIMESTAMP WHERE native_id = ?",
                (changes["register"], native_id)
            )

        if "body" in changes:
            body = changes["body"]
            if len(body.encode("utf-8")) > BODY_SIZE_THRESHOLD:
                self.blobs_dir.mkdir(parents=True, exist_ok=True)
                blob_path = self.blobs_dir / native_id
                blob_path.write_text(body, encoding="utf-8")
                self.conn.execute(
                    "UPDATE nodes SET body = NULL, body_path = ?, modified_at = CURRENT_TIMESTAMP WHERE native_id = ?",
                    (str(blob_path), native_id)
                )
            else:
                self.conn.execute(
                    "UPDATE nodes SET body = ?, body_path = NULL, modified_at = CURRENT_TIMESTAMP WHERE native_id = ?",
                    (body, native_id)
                )

        # Commit managed by orchestrator for transaction control
        return self.resolve(native_id)

    def close_node(self, native_id: str, mode: str) -> None:
        node = self.resolve(native_id)
        if node is None:
            raise ValueError(f"Node not found: {native_id}")

        if mode == "delete":
            uri = node["id"]
            self.conn.execute("DELETE FROM edges WHERE source = ? OR target = ?", (uri, uri))
            if node.get("body_path"):
                blob = Path(node["body_path"])
                if blob.exists():
                    blob.unlink()
            self.conn.execute("DELETE FROM nodes WHERE native_id = ?", (native_id,))
        elif mode == "complete":
            self.conn.execute(
                "UPDATE nodes SET register = 'log', modified_at = CURRENT_TIMESTAMP WHERE native_id = ?",
                (native_id,)
            )
            attrs = node["attributes"]
            if "status" in attrs:
                attrs["status"] = "completed"
                self.conn.execute(
                    "UPDATE nodes SET attributes = ? WHERE native_id = ?",
                    (json.dumps(attrs), native_id)
                )
        elif mode == "archive":
            self.conn.execute(
                "UPDATE nodes SET register = 'reference', modified_at = CURRENT_TIMESTAMP WHERE native_id = ?",
                (native_id,)
            )
        elif mode == "cancel":
            self.conn.execute(
                "UPDATE nodes SET register = 'log', modified_at = CURRENT_TIMESTAMP WHERE native_id = ?",
                (native_id,)
            )
            attrs = node["attributes"]
            if "status" in attrs:
                attrs["status"] = "cancelled"
                self.conn.execute(
                    "UPDATE nodes SET attributes = ? WHERE native_id = ?",
                    (json.dumps(attrs), native_id)
                )

        # Commit managed by orchestrator for transaction control

    def sync(self, since: str | None = None) -> SyncResult:
        return SyncResult({"changed_nodes": [], "changed_edges": []})

    def fetch_body(self, native_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT body, body_path FROM nodes WHERE native_id = ?", (native_id,)
        ).fetchone()
        if row is None:
            return None
        if row["body_path"]:
            return Path(row["body_path"]).read_text(encoding="utf-8")
        return row["body"]

    def create_edge(self, source: str, target: str, edge_type: str, metadata: dict | None = None) -> Edge:
        existing = self.conn.execute(
            "SELECT * FROM edges WHERE source = ? AND target = ? AND type = ?",
            (source, target, edge_type)
        ).fetchone()
        if existing:
            return self._row_to_edge(existing)

        edge_id = f"e-{generate_id('edge')}"
        self.conn.execute(
            "INSERT INTO edges (id, source, target, type, metadata) VALUES (?, ?, ?, ?, ?)",
            (edge_id, source, target, edge_type, json.dumps(metadata or {}))
        )
        # Commit managed by orchestrator for transaction control
        row = self.conn.execute("SELECT * FROM edges WHERE id = ?", (edge_id,)).fetchone()
        return self._row_to_edge(row)

    def query_edges(self, node_id: str, direction: str = "both", edge_type: str | None = None) -> list[Edge]:
        if direction not in ("outbound", "inbound", "both"):
            raise ValueError(f"Invalid direction: {direction!r}")

        conditions = []
        params: list = []

        if direction in ("outbound", "both"):
            conditions.append("source = ?")
            params.append(node_id)
        if direction in ("inbound", "both"):
            conditions.append("target = ?")
            params.append(node_id)

        where = " OR ".join(conditions)
        if edge_type:
            where = f"({where}) AND type = ?"
            params.append(edge_type)

        rows = self.conn.execute(f"SELECT * FROM edges WHERE {where}", params).fetchall()
        return [self._row_to_edge(r) for r in rows]

    def update_edge(self, edge_id: str, changes: dict) -> Edge:
        sets = []
        params: list = []
        if "type" in changes:
            sets.append("type = ?")
            params.append(changes["type"])
        if "target" in changes:
            sets.append("target = ?")
            params.append(changes["target"])
        if "metadata" in changes:
            sets.append("metadata = ?")
            params.append(json.dumps(changes["metadata"]))
        if not sets:
            row = self.conn.execute("SELECT * FROM edges WHERE id = ?", (edge_id,)).fetchone()
            return self._row_to_edge(row)
        params.append(edge_id)
        self.conn.execute(f"UPDATE edges SET {', '.join(sets)} WHERE id = ?", params)
        # Commit managed by orchestrator for transaction control
        row = self.conn.execute("SELECT * FROM edges WHERE id = ?", (edge_id,)).fetchone()
        return self._row_to_edge(row)

    def close_edge(self, edge_id: str) -> None:
        self.conn.execute("DELETE FROM edges WHERE id = ?", (edge_id,))
        # Commit managed by orchestrator for transaction control

    def _row_to_edge(self, row: sqlite3.Row) -> Edge:
        return Edge({
            "id": row["id"],
            "source": row["source"],
            "target": row["target"],
            "type": row["type"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
            "source_op": row["source_op"],
            "created_at": row["created_at"],
        })

    def _row_to_node(self, row: sqlite3.Row) -> Node:
        return Node({
            "id": row["id"],
            "type": row["type"],
            "register": row["register"],
            "adapter": row["adapter"],
            "native_id": row["native_id"],
            "attributes": json.loads(row["attributes"]),
            "body": row["body"],
            "body_path": row["body_path"],
            "source_op": row["source_op"],
            "created_at": row["created_at"],
            "modified_at": row["modified_at"],
        })
