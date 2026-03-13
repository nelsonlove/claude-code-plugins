"""PIM MCP server — exposes ontology tools via FastMCP."""

import os
from pathlib import Path

from fastmcp import FastMCP

from src.constants import DATA_DIR, DB_PATH, OBJECT_TYPES, REGISTERS, RELATION_TYPES, CLOSE_MODES
from src.db import init_db
from src.uri import parse_uri
from src.adapters.internal import InternalAdapter
from src.orchestrator import Orchestrator


def create_server() -> FastMCP:
    data_dir = Path(os.environ.get("PIM_DATA_DIR", str(DATA_DIR))).expanduser()
    db_path = data_dir / "pim.db"
    conn = init_db(db_path)
    internal = InternalAdapter(conn, data_dir)
    orch = Orchestrator(conn=conn, internal_adapter=internal, data_dir=data_dir)

    mcp = FastMCP(
        "PIM",
        instructions=(
            "Personal Information Management system. "
            "8 object types: note, entry, task, event, message, contact, resource, topic. "
            "4 registers: scratch (inbox), working (active), reference (filed), log (historical). "
            "Directed edges connect nodes. See docs/ontology.md for the full model."
        ),
    )

    # --- Node lifecycle tools ---

    @mcp.tool()
    def pim_create_node(
        type: str,
        attributes: dict,
        body: str | None = None,
        register: str = "scratch",
    ) -> dict:
        """Create a new node in the PIM graph.

        Args:
            type: One of: note, entry, task, event, message, contact, resource, topic
            attributes: Type-specific attributes (see ontology for schemas)
            body: Content body for unstructured types (note, entry, message, resource)
            register: Initial register: scratch, working, reference, or log
        """
        node = orch.create_node(type, attributes, body, register)
        return dict(node)

    @mcp.tool()
    def pim_query_nodes(
        type: str,
        register: str | None = None,
        attributes: dict | None = None,
        text_search: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Query nodes by type, register, attributes, or full-text search.

        Args:
            type: Object type to search
            register: Filter by register (scratch, working, reference, log)
            attributes: Filter by attribute values (e.g. {"status": "open"})
            text_search: Full-text search across attributes and body
            limit: Max results (default 20)
        """
        filters = {"limit": limit}
        if register:
            filters["register"] = register
        if attributes:
            filters["attributes"] = attributes
        if text_search:
            filters["text_search"] = text_search
        nodes = orch.query_nodes(type, filters)
        return [dict(n) for n in nodes]

    @mcp.tool()
    def pim_update_node(
        id: str,
        attributes: dict | None = None,
        body: str | None = None,
        register: str | None = None,
    ) -> dict:
        """Update a node's attributes, body, or register.

        Args:
            id: PIM URI of the node (e.g. pim://note/internal/n-20260312-abc123)
            attributes: Attribute changes to merge
            body: New body content (unstructured types only)
            register: New register (scratch, working, reference, log)
        """
        changes = {}
        if attributes:
            changes["attributes"] = attributes
        if body is not None:
            changes["body"] = body
        if register:
            changes["register"] = register
        node = orch.update_node(id, changes)
        return dict(node)

    @mcp.tool()
    def pim_close_node(
        id: str,
        mode: str = "archive",
    ) -> dict | str:
        """Close a node — complete, archive, cancel, or delete.

        Delete mode is high-risk and requires confirmation via pim_confirm.

        Args:
            id: PIM URI of the node
            mode: One of: complete, archive, cancel, delete
        """
        result = orch.close_node(id, mode)
        if result and result.get("status") == "pending_confirmation":
            return result
        return f"Node {id} closed with mode: {mode}"

    @mcp.tool()
    def pim_confirm(
        log_id: str,
    ) -> dict:
        """Confirm and execute a pending high-risk operation.

        When a high-risk operation (e.g. delete) is requested, it returns a
        pending confirmation with a log_id. Pass that log_id here to execute.

        Args:
            log_id: Decision log ID from the pending confirmation response
        """
        return orch.confirm_operation(log_id)

    # --- Bulk throughput tools ---

    @mcp.tool()
    def pim_create_nodes(
        nodes: list[dict],
    ) -> list[dict]:
        """Create multiple nodes in a single call. Atomic — all succeed or all fail.

        Each element: {type, attributes, body?, register?}
        Use this instead of looping pim_create_node for bulk ingestion.

        Args:
            nodes: Array of node specs, each with type, attributes, and optional body/register
        """
        results = orch.create_nodes(nodes)
        return [dict(n) for n in results]

    @mcp.tool()
    def pim_create_edges(
        edges: list[dict],
    ) -> list[dict]:
        """Create multiple edges in a single call. Atomic — all succeed or all fail.

        Each element: {source, target, type, metadata?}
        Use this instead of looping pim_create_edge for bulk ingestion.

        Args:
            edges: Array of edge specs, each with source, target, type, and optional metadata
        """
        results = orch.create_edges(edges)
        return [dict(e) for e in results]

    # --- Batch confirmation tools ---

    @mcp.tool()
    def pim_batch_propose(
        operations: list[dict],
    ) -> dict:
        """Propose a batch of operations for user review before execution.

        Required for any operation creating more than 5 nodes, and for initial
        import. The interpreter presents the summary; the user approves or
        excludes specific operations.

        Each operation: {action: "create_node"|"create_edge"|"update_node"|"close_node", ...params}

        Args:
            operations: Array of operation specs to propose
        """
        return orch.batch_propose(operations)

    @mcp.tool()
    def pim_batch_commit(
        batch_id: str,
        exclusions: list[int] | None = None,
    ) -> dict:
        """Execute a previously proposed batch. Uses bulk throughput tools internally.

        Args:
            batch_id: Batch ID from pim_batch_propose
            exclusions: Optional list of operation indexes (0-based) to skip
        """
        return orch.batch_commit(batch_id, exclusions)

    @mcp.tool()
    def pim_batch_discard(
        batch_id: str,
    ) -> str:
        """Discard a proposed batch without executing.

        Args:
            batch_id: Batch ID from pim_batch_propose
        """
        orch.batch_discard(batch_id)
        return f"Batch {batch_id} discarded"

    # --- Edge lifecycle tools ---

    @mcp.tool()
    def pim_create_edge(
        source: str,
        target: str,
        type: str,
        metadata: dict | None = None,
    ) -> dict:
        """Create a directed edge between two nodes.

        Direction: source bears on target.
        Relation families: structural (-> topic), agency (-> contact),
        temporal (diachronic -> diachronic), annotation (note/entry -> any),
        derivation (any -> any), generic (references, related-to).

        Args:
            source: PIM URI of the source node
            target: PIM URI of the target node
            type: Relation type (belongs-to, derived-from, from, to, involves, etc.)
            metadata: Optional key-value metadata on the edge
        """
        edge = orch.create_edge(source, target, type, metadata)
        return dict(edge)

    @mcp.tool()
    def pim_query_edges(
        source: str | None = None,
        target: str | None = None,
        type: str | None = None,
        direction: str = "both",
    ) -> list[dict]:
        """Query edges by source, target, type, or direction.

        Args:
            source: PIM URI to find outbound edges from
            target: PIM URI to find inbound edges to
            type: Filter by relation type
            direction: outbound, inbound, or both
        """
        edges = orch.query_edges(source=source, target=target, edge_type=type, direction=direction)
        return [dict(e) for e in edges]

    @mcp.tool()
    def pim_update_edge(
        id: str,
        type: str | None = None,
        target: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        """Update an edge's type, target, or metadata.

        Args:
            id: Edge ID
            type: New relation type
            target: New target PIM URI (re-file)
            metadata: New metadata to set
        """
        changes = {}
        if type:
            changes["type"] = type
        if target:
            changes["target"] = target
        if metadata:
            changes["metadata"] = metadata
        edge = orch.update_edge(id, changes)
        return dict(edge)

    @mcp.tool()
    def pim_close_edge(id: str) -> str:
        """Dissolve an edge. The nodes persist; only the connection is removed.

        Args:
            id: Edge ID
        """
        orch.close_edge(id)
        return f"Edge {id} dissolved"

    # --- Boundary tools (stubs for Tier 1) ---

    @mcp.tool()
    def pim_capture(
        input: str,
        source: str | None = None,
    ) -> dict:
        """Capture raw input — decompose into typed objects and relations.

        In Tier 1 this creates a single note in scratch. Full decomposition
        will be implemented when the agent constellation is available.

        Args:
            input: Raw content to capture
            source: Optional origin hint (email, voice, clipboard, url)
        """
        node = orch.create_node("note", {"title": f"Capture: {input[:50]}"}, body=input)
        return {"nodes_created": [node["id"]], "edges_created": [], "suggestions": []}

    @mcp.tool()
    def pim_dispatch(
        target: str,
        method: str | None = None,
        params: dict | None = None,
    ) -> dict:
        """Dispatch a node outward across the sovereignty boundary.

        Stub for Tier 1 — full dispatch requires external adapters.

        Args:
            target: PIM URI of the node to dispatch
            method: Optional dispatch method
            params: Optional dispatch parameters
        """
        return {"status": "not_implemented", "message": "Dispatch requires external adapters (Tier 3+)"}

    # --- Convenience tools ---

    @mcp.tool()
    def pim_resolve(
        type: str,
        hints: dict,
    ) -> dict:
        """Identity resolution — find an existing node matching the hints.

        Tier 1: deterministic lookup only (exact attribute match).
        Semantic search added in Tier 8.

        Args:
            type: Object type to search
            hints: Attribute hints (name, email, title, etc.)
        """
        results = orch.query_nodes(type, {"attributes": hints, "limit": 5})
        if not results:
            return {"outcome": "not_found", "candidates": []}
        if len(results) == 1:
            return {"outcome": "found", "node": dict(results[0]), "confidence": 1.0}
        return {
            "outcome": "ambiguous",
            "candidates": [dict(r) for r in results],
            "confidence": 0.5,
        }

    @mcp.tool()
    def pim_review(
        register: str | None = None,
        type: str | None = None,
        topic: str | None = None,
        contact: str | None = None,
    ) -> dict:
        """Assemble a contextual review — fan out queries across the graph.

        Args:
            register: Review a specific register (e.g. "scratch" for inbox)
            type: Filter by object type
            topic: PIM URI of a topic to review
            contact: PIM URI of a contact to review
        """
        results = {}
        if register:
            for t in OBJECT_TYPES:
                nodes = orch.query_nodes(t, {"register": register, "limit": 10})
                if nodes:
                    results[t] = [dict(n) for n in nodes]
        elif type:
            nodes = orch.query_nodes(type, {"limit": 20})
            results[type] = [dict(n) for n in nodes]
        elif topic:
            edges = orch.query_edges(target=topic, edge_type="belongs-to")
            node_ids = [e["source"] for e in edges]
            for nid in node_ids[:20]:
                parts = parse_uri(nid)
                adapter = orch.adapters.get(parts["adapter"], orch.internal)
                native_id = adapter.reverse_resolve(nid)
                if native_id:
                    node = adapter.resolve(native_id)
                    if node:
                        t = node["type"]
                        results.setdefault(t, []).append(dict(node))
        elif contact:
            edges = orch.query_edges(target=contact)
            for e in edges[:20]:
                parts = parse_uri(e["source"])
                adapter = orch.adapters.get(parts["adapter"], orch.internal)
                native_id = adapter.reverse_resolve(e["source"])
                if native_id:
                    node = adapter.resolve(native_id)
                    if node:
                        t = node["type"]
                        results.setdefault(t, []).append(dict(node))
        return {"scope": {"register": register, "type": type, "topic": topic, "contact": contact}, "results": results}

    @mcp.tool()
    def pim_decision_log(
        target: str | None = None,
        operation: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Retrieve decision log entries for auditing and undo.

        Args:
            target: Filter by PIM URI
            operation: Filter by operation type
            limit: Max results (default 50)
        """
        return orch.get_decision_log(target=target, operation=operation, limit=limit)

    return mcp


# Entry point for MCP runner (lazy — only creates server when this module is run directly)
mcp = create_server()

if __name__ == "__main__":
    mcp.run()
