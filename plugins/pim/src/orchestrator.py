"""Orchestrator — routes operations to adapters and enforces write policy."""

import json
import sqlite3
from pathlib import Path

from src.adapter import Adapter, Node, Edge
from src.uri import parse_uri, generate_id
from src.constants import RISK_LOW, RISK_MEDIUM, RISK_HIGH


class Orchestrator:
    """
    Central orchestration layer. Routes operations to adapters via the routing table.
    Enforces write policy and logs decisions.

    For Tier 1, only the internal adapter is available. The routing table and
    external adapter support will be added in later tiers.
    """

    def __init__(self, conn: sqlite3.Connection, internal_adapter: Adapter, data_dir: Path):
        self.conn = conn
        self.internal = internal_adapter
        self.data_dir = data_dir
        self.adapters: dict[str, Adapter] = {"internal": internal_adapter}
        self.routing: dict = {}

    def register_adapter(self, adapter: Adapter) -> None:
        self.adapters[adapter.adapter_id] = adapter

    def set_routing(self, routing: dict) -> None:
        self.routing = routing

    def _resolve_adapter(self, obj_type: str, register: str = "scratch") -> Adapter:
        route = self.routing.get(obj_type)
        if route is None:
            return self.internal
        if isinstance(route, str):
            return self.adapters.get(route, self.internal)
        if isinstance(route, dict):
            adapter_id = route.get(register, "internal")
            return self.adapters.get(adapter_id, self.internal)
        return self.internal

    def _log_decision(self, operation: str, target: str | None, risk_tier: str,
                      approval: str = "automatic", evidence: dict | None = None) -> str:
        log_id = f"dl-{generate_id('log')}"
        self.conn.execute(
            """INSERT INTO decision_log (id, operation, target, risk_tier, approval, evidence)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (log_id, operation, target, risk_tier, approval, json.dumps(evidence or {}))
        )
        self.conn.commit()
        return log_id

    def _classify_risk(self, operation: str, obj_type: str | None = None, changes: dict | None = None) -> str:
        if operation == "update_register":
            return RISK_LOW
        if operation == "create_edge" and changes and changes.get("type") in ("references", "related-to", "belongs-to"):
            return RISK_LOW
        if operation == "close_node" and changes and changes.get("mode") == "delete":
            return RISK_HIGH
        if operation == "merge":
            return RISK_HIGH
        return RISK_MEDIUM

    def create_node(self, obj_type: str, attributes: dict, body: str | None = None,
                    register: str = "scratch") -> Node:
        adapter = self._resolve_adapter(obj_type, register)
        risk = self._classify_risk("create_node", obj_type)
        node = adapter.create_node(obj_type, attributes, body)
        if register != "scratch":
            adapter.update_node(node["native_id"], {"register": register})
            node = adapter.resolve(node["native_id"])
        log_id = self._log_decision("create_node", node["id"], risk)
        self.conn.execute("UPDATE nodes SET source_op = ? WHERE id = ?", (log_id, node["id"]))
        self.conn.commit()
        return adapter.resolve(node["native_id"])

    def query_nodes(self, obj_type: str, filters: dict | None = None) -> list[Node]:
        filters = filters or {}
        register = filters.get("register")
        if register:
            adapter = self._resolve_adapter(obj_type, register)
            return adapter.query_nodes(obj_type, filters)
        else:
            return self.internal.query_nodes(obj_type, filters)

    def update_node(self, pim_uri: str, changes: dict) -> Node:
        parts = parse_uri(pim_uri)
        adapter = self.adapters.get(parts["adapter"], self.internal)
        native_id = adapter.reverse_resolve(pim_uri)
        if native_id is None:
            raise ValueError(f"Node not found: {pim_uri}")
        if "register" in changes:
            risk = self._classify_risk("update_register")
        else:
            risk = self._classify_risk("update_node", parts["type"])
        self._log_decision("update_node", pim_uri, risk, evidence={"changes": changes})
        return adapter.update_node(native_id, changes)

    def close_node(self, pim_uri: str, mode: str) -> None:
        parts = parse_uri(pim_uri)
        adapter = self.adapters.get(parts["adapter"], self.internal)
        native_id = adapter.reverse_resolve(pim_uri)
        if native_id is None:
            raise ValueError(f"Node not found: {pim_uri}")
        risk = self._classify_risk("close_node", changes={"mode": mode})
        self._log_decision("close_node", pim_uri, risk, evidence={"mode": mode})
        adapter.close_node(native_id, mode)

    def create_edge(self, source: str, target: str, edge_type: str, metadata: dict | None = None) -> Edge:
        risk = self._classify_risk("create_edge", changes={"type": edge_type})
        edge = self.internal.create_edge(source, target, edge_type, metadata)
        self._log_decision("create_edge", edge["id"], risk, evidence={"source": source, "target": target, "type": edge_type})
        return edge

    def query_edges(self, source: str | None = None, target: str | None = None,
                    edge_type: str | None = None, direction: str = "both") -> list[Edge]:
        if source and target:
            raise ValueError("Specify source or target, not both. Use direction to control traversal.")
        node_id = source or target
        if source:
            direction = "outbound"
        elif target:
            direction = "inbound"
        return self.internal.query_edges(node_id, direction, edge_type)

    def update_edge(self, edge_id: str, changes: dict) -> Edge:
        self._log_decision("update_edge", edge_id, RISK_MEDIUM, evidence={"changes": changes})
        return self.internal.update_edge(edge_id, changes)

    def close_edge(self, edge_id: str) -> None:
        self._log_decision("close_edge", edge_id, RISK_LOW)
        self.internal.close_edge(edge_id)

    def get_decision_log(self, target: str | None = None, operation: str | None = None,
                         limit: int = 50) -> list[dict]:
        query = "SELECT * FROM decision_log WHERE 1=1"
        params: list = []
        if target:
            query += " AND target = ?"
            params.append(target)
        if operation:
            query += " AND operation = ?"
            params.append(operation)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
