"""Agent constellation — backing logic for the 6 PIM agents."""

import sqlite3
from typing import Any

from src.orchestrator import Orchestrator
from src.semantic import SemanticIndex
from src.identity import IdentityResolver


class InterpreterAgent:
    """Decomposes raw input into typed objects and relations.

    Takes unstructured text and identifies:
    - Object types to create (notes, tasks, events, contacts, etc.)
    - Relations between them
    - Register assignments
    """

    def __init__(self, orch: Orchestrator):
        self.orch = orch

    def decompose(self, text: str, source: str | None = None) -> dict:
        """Decompose raw input into a structured capture plan.

        Returns a plan dict with nodes_to_create and edges_to_create.
        In Tier 1, this is a simple heuristic. Full NLP decomposition
        comes when the agent constellation has LLM access.
        """
        plan: dict[str, Any] = {
            "source": source,
            "nodes_to_create": [],
            "edges_to_create": [],
            "suggestions": [],
        }

        # Simple heuristics for type detection
        text_lower = text.lower()

        # Task detection
        if any(kw in text_lower for kw in ["todo", "task:", "action:", "need to", "should"]):
            plan["nodes_to_create"].append({
                "type": "task",
                "attributes": {"title": text[:100], "status": "open"},
                "register": "scratch",
            })
        # Event detection
        elif any(kw in text_lower for kw in ["meeting", "appointment", "event:", "calendar"]):
            plan["nodes_to_create"].append({
                "type": "event",
                "attributes": {"title": text[:100], "status": "confirmed"},
                "register": "working",
            })
        # Contact detection
        elif any(kw in text_lower for kw in ["contact:", "person:", "email:", "phone:"]):
            plan["nodes_to_create"].append({
                "type": "contact",
                "attributes": {"name": text[:100]},
                "register": "reference",
            })
        # Default: create a note
        else:
            plan["nodes_to_create"].append({
                "type": "note",
                "attributes": {"title": f"Capture: {text[:50]}"},
                "body": text,
                "register": "scratch",
            })

        return plan

    def execute_plan(self, plan: dict) -> dict:
        """Execute a decomposition plan, creating nodes and edges."""
        created_nodes = []
        created_edges = []

        for node_spec in plan.get("nodes_to_create", []):
            node = self.orch.create_node(
                node_spec["type"],
                node_spec["attributes"],
                body=node_spec.get("body"),
                register=node_spec.get("register", "scratch"),
            )
            created_nodes.append(node["id"])

        for edge_spec in plan.get("edges_to_create", []):
            edge = self.orch.create_edge(
                edge_spec["source"],
                edge_spec["target"],
                edge_spec["type"],
                edge_spec.get("metadata"),
            )
            created_edges.append(edge["id"])

        return {
            "nodes_created": created_nodes,
            "edges_created": created_edges,
            "suggestions": plan.get("suggestions", []),
        }


class ExecutorAgent:
    """Carries out operations on the PIM graph.

    Wraps orchestrator operations with additional logic for
    batch operations, undo support, and operation chaining.
    """

    def __init__(self, orch: Orchestrator):
        self.orch = orch

    def batch_create(self, specs: list[dict]) -> list[dict]:
        """Create multiple nodes in a batch using bulk throughput."""
        nodes = self.orch.create_nodes(specs)
        return [{"status": "created", "id": n["id"]} for n in nodes]

    def batch_update(self, updates: list[dict]) -> list[dict]:
        """Update multiple nodes in a batch."""
        results = []
        for update in updates:
            try:
                node = self.orch.update_node(
                    update["id"],
                    update["changes"],
                )
                results.append({"status": "updated", "id": node["id"]})
            except Exception as e:
                results.append({"status": "error", "error": str(e)})
        return results

    def move_register(self, node_ids: list[str], target_register: str) -> list[dict]:
        """Move multiple nodes to a different register."""
        results = []
        for nid in node_ids:
            try:
                node = self.orch.update_node(nid, {"register": target_register})
                results.append({"status": "moved", "id": node["id"]})
            except Exception as e:
                results.append({"status": "error", "error": str(e)})
        return results


class BriefingAgent:
    """Assembles contextual reviews and briefings.

    Gathers information across the graph to produce structured
    briefings: inbox review, topic deep-dive, contact dossier, etc.
    """

    def __init__(self, orch: Orchestrator):
        self.orch = orch

    def inbox_review(self) -> dict:
        """Review all scratch register items across types."""
        from src.constants import OBJECT_TYPES
        results: dict[str, list] = {}
        total = 0
        for obj_type in OBJECT_TYPES:
            nodes = self.orch.query_nodes(obj_type, {"register": "scratch", "limit": 20})
            if nodes:
                results[obj_type] = [dict(n) for n in nodes]
                total += len(nodes)
        return {"register": "scratch", "total": total, "items": results}

    def topic_briefing(self, topic_uri: str) -> dict:
        """Deep dive on a topic — all related nodes."""
        edges = self.orch.query_edges(target=topic_uri, edge_type="belongs-to")
        related_nodes = []
        for e in edges[:50]:
            try:
                from src.uri import parse_uri
                parts = parse_uri(e["source"])
                adapter = self.orch.adapters.get(parts["adapter"], self.orch.internal)
                native_id = adapter.reverse_resolve(e["source"])
                if native_id:
                    node = adapter.resolve(native_id)
                    if node:
                        related_nodes.append(dict(node))
            except Exception:
                continue
        return {
            "topic": topic_uri,
            "related_count": len(related_nodes),
            "related_nodes": related_nodes,
        }

    def contact_dossier(self, contact_uri: str) -> dict:
        """Compile all information related to a contact."""
        edges = self.orch.query_edges(target=contact_uri)
        items_by_type: dict[str, list] = {}
        for e in edges[:50]:
            try:
                from src.uri import parse_uri
                parts = parse_uri(e["source"])
                adapter = self.orch.adapters.get(parts["adapter"], self.orch.internal)
                native_id = adapter.reverse_resolve(e["source"])
                if native_id:
                    node = adapter.resolve(native_id)
                    if node:
                        t = node["type"]
                        items_by_type.setdefault(t, []).append(dict(node))
            except Exception:
                continue
        return {
            "contact": contact_uri,
            "items_by_type": items_by_type,
            "total_relations": sum(len(v) for v in items_by_type.values()),
        }


class ResearchAgent:
    """Performs deep research across the graph.

    Combines text search, semantic search, and graph traversal
    to find relevant information.
    """

    def __init__(self, orch: Orchestrator, semantic: SemanticIndex | None = None):
        self.orch = orch
        self.semantic = semantic

    def search(self, query: str, obj_type: str | None = None,
               limit: int = 20) -> dict:
        """Multi-strategy search across the graph."""
        results: dict[str, list] = {"text_results": [], "semantic_results": []}

        # Text search across types
        from src.constants import OBJECT_TYPES
        types_to_search = [obj_type] if obj_type else OBJECT_TYPES
        for t in types_to_search:
            nodes = self.orch.query_nodes(t, {"text_search": query, "limit": limit})
            for n in nodes:
                results["text_results"].append(dict(n))

        # Semantic search — requires LLM-provided query embedding (future tier)
        # self.semantic is available but _query_embedding needs an embedding
        # model to convert text queries to vectors, which is a Tier 2+ feature.

        return {
            "query": query,
            "total_text": len(results["text_results"]),
            "total_semantic": len(results["semantic_results"]),
            "results": results,
        }

    def trace_connections(self, node_id: str, depth: int = 2) -> dict:
        """Trace the connection graph from a node to a given depth."""
        visited = set()
        layers: list[list[dict]] = []

        current = [node_id]
        for d in range(depth):
            next_layer = []
            layer_edges = []
            for nid in current:
                if nid in visited:
                    continue
                visited.add(nid)
                edges = self.orch.query_edges(source=nid)
                edges.extend(self.orch.query_edges(target=nid))
                for e in edges:
                    layer_edges.append(dict(e))
                    other = e["target"] if e["source"] == nid else e["source"]
                    if other not in visited:
                        next_layer.append(other)
            layers.append(layer_edges)
            current = next_layer

        return {
            "root": node_id,
            "depth": depth,
            "layers": layers,
            "total_edges": sum(len(l) for l in layers),
        }


class DiscoveryAgent:
    """Finds connections and suggests relations.

    Analyzes the graph to discover implicit relationships
    between nodes.
    """

    def __init__(self, orch: Orchestrator, resolver: IdentityResolver | None = None):
        self.orch = orch
        self.resolver = resolver

    def find_orphans(self, obj_type: str | None = None) -> list[dict]:
        """Find nodes with no edges (orphans)."""
        from src.constants import OBJECT_TYPES
        types = [obj_type] if obj_type else OBJECT_TYPES
        orphans = []

        for t in types:
            nodes = self.orch.query_nodes(t, {"limit": 100})
            for n in nodes:
                edges = self.orch.query_edges(source=n["id"])
                edges.extend(self.orch.query_edges(target=n["id"]))
                if not edges:
                    orphans.append(dict(n))

        return orphans

    def suggest_relations(self, node_id: str) -> list[dict]:
        """Suggest potential relations for a node."""
        suggestions = []

        # Identity matches
        if self.resolver:
            try:
                matches = self.resolver.find_matches(node_id, min_confidence=0.5)
                for m in matches:
                    suggestions.append({
                        "type": "identity_match",
                        "target": m["candidate_id"],
                        "confidence": m["confidence"],
                        "reason": f"Potential duplicate ({m['match_type']})",
                    })
            except Exception:
                pass

        return suggestions

    def find_duplicates(self, obj_type: str, min_confidence: float = 0.7) -> list[dict]:
        """Find potential duplicate nodes of a type."""
        if not self.resolver:
            return []

        nodes = self.orch.query_nodes(obj_type, {"limit": 100})
        duplicates = []
        checked = set()

        for n in nodes:
            if n["id"] in checked:
                continue
            matches = self.resolver.find_matches(
                n["id"], obj_type=obj_type, min_confidence=min_confidence
            )
            for m in matches:
                if m["candidate_id"] not in checked:
                    duplicates.append({
                        "source": n["id"],
                        "candidate": m["candidate_id"],
                        "confidence": m["confidence"],
                        "match_type": m["match_type"],
                    })
            checked.add(n["id"])

        return duplicates


class ConfigAgent:
    """Manages PIM configuration and adapter setup."""

    def __init__(self, orch: Orchestrator, conn: sqlite3.Connection):
        self.orch = orch
        self.conn = conn

    def list_adapters(self) -> list[dict]:
        """List all registered adapters with their capabilities."""
        adapters = []
        for adapter_id, adapter in self.orch.adapters.items():
            adapters.append({
                "id": adapter_id,
                "types": list(adapter.supported_types),
                "operations": list(adapter.supported_operations),
                "registers": list(adapter.supported_registers),
                "healthy": adapter.health_check(),
            })
        return adapters

    def get_routing(self) -> dict:
        """Get the current routing table."""
        return self.orch.routing

    def set_routing(self, routing: dict) -> dict:
        """Update the routing table."""
        self.orch.set_routing(routing)
        return routing

    def get_stats(self) -> dict:
        """Get overall PIM statistics."""
        from src.constants import OBJECT_TYPES, REGISTERS

        stats: dict[str, Any] = {"types": {}, "registers": {}}

        for t in OBJECT_TYPES:
            count = self.conn.execute(
                "SELECT COUNT(*) FROM nodes WHERE type = ?", (t,)
            ).fetchone()[0]
            stats["types"][t] = count

        for r in REGISTERS:
            count = self.conn.execute(
                "SELECT COUNT(*) FROM nodes WHERE register = ?", (r,)
            ).fetchone()[0]
            stats["registers"][r] = count

        stats["total_nodes"] = self.conn.execute(
            "SELECT COUNT(*) FROM nodes"
        ).fetchone()[0]
        stats["total_edges"] = self.conn.execute(
            "SELECT COUNT(*) FROM edges"
        ).fetchone()[0]
        stats["total_decisions"] = self.conn.execute(
            "SELECT COUNT(*) FROM decision_log"
        ).fetchone()[0]

        return stats
