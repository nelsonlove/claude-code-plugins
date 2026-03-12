"""Orchestrator — routes operations to adapters and enforces write policy."""

import json
import sqlite3
from pathlib import Path

from src.adapter import Adapter, Node, Edge
from src.uri import parse_uri, generate_id
from src.constants import (
    RISK_LOW, RISK_MEDIUM, RISK_HIGH,
    OBJECT_TYPES, REGISTERS, CLOSE_MODES, RELATION_TYPES,
)


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

    @staticmethod
    def _validate_type(obj_type: str) -> None:
        if obj_type not in OBJECT_TYPES:
            raise ValueError(f"Invalid type: {obj_type!r}. Valid types: {', '.join(OBJECT_TYPES)}")

    @staticmethod
    def _validate_register(register: str) -> None:
        if register not in REGISTERS:
            raise ValueError(f"Invalid register: {register!r}. Valid registers: {', '.join(REGISTERS)}")

    @staticmethod
    def _validate_close_mode(mode: str) -> None:
        if mode not in CLOSE_MODES:
            raise ValueError(f"Invalid mode: {mode!r}. Valid modes: {', '.join(CLOSE_MODES)}")

    @staticmethod
    def _validate_edge_type(edge_type: str) -> None:
        if edge_type not in RELATION_TYPES:
            raise ValueError(f"Invalid edge_type: {edge_type!r}. Valid types: {', '.join(RELATION_TYPES)}")

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

    # Edge types considered associative (low risk to create)
    _ASSOCIATIVE_EDGES = frozenset({"references", "related-to", "belongs-to"})
    # Edge types considered agency or derivation (medium risk)
    _AGENCY_EDGES = frozenset({"from", "to", "involves", "delegated-to", "sent-by", "member-of"})
    _DERIVATION_EDGES = frozenset({"derived-from"})

    def _classify_risk(self, operation: str, obj_type: str | None = None, changes: dict | None = None) -> str:
        # --- Low risk (autonomous) ---
        # Creating entries is append-only
        if operation == "create_node" and obj_type == "entry":
            return RISK_LOW
        # Register transitions
        if operation == "update_register":
            return RISK_LOW
        # Associative relations
        if operation == "create_edge" and changes and changes.get("type") in self._ASSOCIATIVE_EDGES:
            return RISK_LOW
        # Read/query operations
        if operation in ("query_nodes", "query_edges"):
            return RISK_LOW

        # --- High risk (confirmed) ---
        # Deleting any node
        if operation == "close_node" and changes and changes.get("mode") == "delete":
            return RISK_HIGH
        # Overwriting existing body content
        if operation == "overwrite_body":
            return RISK_HIGH
        # Merging nodes
        if operation == "merge":
            return RISK_HIGH
        # Ambiguous identity resolution
        if operation == "ambiguous_resolution":
            return RISK_HIGH

        # --- Medium risk (validated) ---
        # Creating typed nodes (note, task, event, resource, contact, topic)
        if operation == "create_node":
            return RISK_MEDIUM
        # Agency or derivation edges
        if operation == "create_edge" and changes:
            edge_t = changes.get("type", "")
            if edge_t in self._AGENCY_EDGES or edge_t in self._DERIVATION_EDGES:
                return RISK_MEDIUM
        # Updating node attributes
        if operation == "update_node":
            return RISK_MEDIUM

        # Default to medium for anything unrecognized
        return RISK_MEDIUM

    def create_node(self, obj_type: str, attributes: dict, body: str | None = None,
                    register: str = "scratch") -> Node:
        self._validate_type(obj_type)
        self._validate_register(register)
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
        self._validate_type(obj_type)
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
            self._validate_register(changes["register"])
            risk = self._classify_risk("update_register")
        else:
            risk = self._classify_risk("update_node", parts["type"])
        self._log_decision("update_node", pim_uri, risk, evidence={"changes": changes})
        return adapter.update_node(native_id, changes)

    def close_node(self, pim_uri: str, mode: str) -> dict | None:
        self._validate_close_mode(mode)
        parts = parse_uri(pim_uri)
        adapter = self.adapters.get(parts["adapter"], self.internal)
        native_id = adapter.reverse_resolve(pim_uri)
        if native_id is None:
            raise ValueError(f"Node not found: {pim_uri}")
        risk = self._classify_risk("close_node", changes={"mode": mode})
        if risk == RISK_HIGH:
            log_id = self._log_decision(
                "close_node", pim_uri, risk,
                approval="pending_confirmation",
                evidence={"mode": mode, "operation": "close_node", "target": pim_uri},
            )
            return {
                "status": "pending_confirmation",
                "log_id": log_id,
                "operation": "close_node",
                "target": pim_uri,
                "mode": mode,
            }
        self._log_decision("close_node", pim_uri, risk, evidence={"mode": mode})
        adapter.close_node(native_id, mode)
        return None

    def create_edge(self, source: str, target: str, edge_type: str, metadata: dict | None = None) -> Edge:
        self._validate_edge_type(edge_type)
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

    def confirm_operation(self, log_id: str) -> dict:
        """Execute a pending high-risk operation after user confirmation."""
        row = self.conn.execute(
            "SELECT * FROM decision_log WHERE id = ? AND approval = 'pending_confirmation'",
            (log_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"No pending operation found for log_id: {log_id!r}")
        entry = dict(row)
        evidence = json.loads(entry["evidence"]) if entry["evidence"] else {}
        operation = entry["operation"]
        target = entry["target"]

        # Execute the stored operation
        if operation == "close_node":
            mode = evidence.get("mode")
            parts = parse_uri(target)
            adapter = self.adapters.get(parts["adapter"], self.internal)
            native_id = adapter.reverse_resolve(target)
            if native_id is None:
                raise ValueError(f"Node not found: {target}")
            adapter.close_node(native_id, mode)

        # Mark as confirmed
        self.conn.execute(
            "UPDATE decision_log SET approval = 'confirmed' WHERE id = ?",
            (log_id,),
        )
        self.conn.commit()
        return {"status": "confirmed", "log_id": log_id, "operation": operation, "target": target}

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
