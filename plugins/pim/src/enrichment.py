"""Relation discovery and enrichment policy."""

from src.orchestrator import Orchestrator
from src.semantic import SemanticIndex
from src.identity import IdentityResolver
from src.constants import OBJECT_TYPES


class EnrichmentPolicy:
    """Defines rules for automatic relation creation and enrichment.

    Controls which relations can be auto-created (low risk) vs
    which require confirmation (medium/high risk).
    """

    # Relations that can be auto-created without confirmation
    AUTO_RELATIONS = frozenset({"references", "related-to", "belongs-to"})

    # Relations requiring validation before creation
    VALIDATED_RELATIONS = frozenset({
        "from", "to", "involves", "delegated-to", "sent-by",
        "member-of", "derived-from",
    })

    # Relations requiring explicit confirmation
    CONFIRMED_RELATIONS = frozenset({"precedes", "occurs-during", "annotation-of", "blocks"})

    @classmethod
    def can_auto_create(cls, relation_type: str) -> bool:
        return relation_type in cls.AUTO_RELATIONS

    @classmethod
    def requires_validation(cls, relation_type: str) -> bool:
        return relation_type in cls.VALIDATED_RELATIONS

    @classmethod
    def requires_confirmation(cls, relation_type: str) -> bool:
        return relation_type in cls.CONFIRMED_RELATIONS


class RelationDiscovery:
    """Discovers implicit relations between nodes.

    Analyzes node attributes and content to suggest new relations.
    Uses heuristics and semantic similarity when available.
    """

    def __init__(self, orch: Orchestrator,
                 semantic: SemanticIndex | None = None,
                 resolver: IdentityResolver | None = None):
        self.orch = orch
        self.semantic = semantic
        self.resolver = resolver
        self.policy = EnrichmentPolicy()

    def discover_for_node(self, node_id: str) -> list[dict]:
        """Discover potential relations for a specific node.

        Returns a list of suggested relations with confidence scores.
        """
        suggestions = []

        # Get node details
        from src.uri import parse_uri
        parts = parse_uri(node_id)
        adapter = self.orch.adapters.get(parts["adapter"], self.orch.internal)
        native_id = adapter.reverse_resolve(node_id)
        if native_id is None:
            return suggestions

        node = adapter.resolve(native_id)
        if node is None:
            return suggestions

        # Strategy 1: Type-based heuristics
        suggestions.extend(self._type_based_suggestions(node))

        # Strategy 2: Attribute matching
        suggestions.extend(self._attribute_matching(node))

        # Strategy 3: Semantic similarity (if available)
        if self.semantic:
            suggestions.extend(self._semantic_suggestions(node))

        # Deduplicate
        seen = set()
        unique = []
        for s in suggestions:
            key = (s["source"], s["target"], s["type"])
            if key not in seen:
                seen.add(key)
                unique.append(s)

        return sorted(unique, key=lambda x: x["confidence"], reverse=True)

    def _type_based_suggestions(self, node: dict) -> list[dict]:
        """Suggest relations based on type conventions."""
        suggestions = []
        node_type = node["type"]
        node_id = node["id"]

        # Tasks and events often belong to topics
        if node_type in ("task", "event", "note"):
            topics = self.orch.query_nodes("topic", {"limit": 10})
            for topic in topics:
                # Check if there's already a belongs-to edge
                existing = self.orch.query_edges(source=node_id)
                existing_targets = {e["target"] for e in existing}
                if topic["id"] not in existing_targets:
                    suggestions.append({
                        "source": node_id,
                        "target": topic["id"],
                        "type": "belongs-to",
                        "confidence": 0.3,
                        "reason": f"{node_type} may belong to topic '{topic['attributes'].get('title', '')}'",
                        "auto_create": self.policy.can_auto_create("belongs-to"),
                    })

        return suggestions

    def _attribute_matching(self, node: dict) -> list[dict]:
        """Suggest relations based on shared attribute values."""
        suggestions = []
        node_id = node["id"]
        attrs = node.get("attributes", {})

        # If a task/event mentions a contact name, suggest 'involves'
        if node["type"] in ("task", "event", "message"):
            title = attrs.get("title", "") or attrs.get("subject", "")
            if title:
                contacts = self.orch.query_nodes("contact", {"limit": 50})
                for contact in contacts:
                    contact_name = contact["attributes"].get("name", "")
                    if contact_name and contact_name.lower() in title.lower():
                        suggestions.append({
                            "source": node_id,
                            "target": contact["id"],
                            "type": "involves",
                            "confidence": 0.7,
                            "reason": f"Title mentions contact '{contact_name}'",
                            "auto_create": self.policy.can_auto_create("involves"),
                        })

        return suggestions

    def _semantic_suggestions(self, node: dict) -> list[dict]:
        """Suggest relations using embedding similarity."""
        if not self.semantic:
            return []

        embedding = self.semantic.get_embedding(node["id"])
        if embedding is None:
            return []

        suggestions = []
        results = self.semantic.search(embedding, limit=5, min_similarity=0.8)

        for r in results:
            if r["node_id"] != node["id"]:
                suggestions.append({
                    "source": node["id"],
                    "target": r["node_id"],
                    "type": "related-to",
                    "confidence": r["similarity"],
                    "reason": f"Semantic similarity: {r['similarity']:.2f}",
                    "auto_create": self.policy.can_auto_create("related-to"),
                })

        return suggestions

    def auto_enrich(self, node_id: str) -> list[dict]:
        """Automatically create low-risk relations for a node.

        Only creates relations that pass the enrichment policy
        auto-create check.
        """
        suggestions = self.discover_for_node(node_id)
        created = []

        for s in suggestions:
            if s.get("auto_create") and s["confidence"] >= 0.7:
                try:
                    edge = self.orch.create_edge(
                        s["source"], s["target"], s["type"]
                    )
                    created.append({
                        "edge_id": edge["id"],
                        "source": s["source"],
                        "target": s["target"],
                        "type": s["type"],
                        "confidence": s["confidence"],
                    })
                except Exception:
                    continue

        return created

    def bulk_discover(self, obj_type: str | None = None,
                      limit: int = 50) -> list[dict]:
        """Run discovery across multiple nodes."""
        all_suggestions = []
        types = [obj_type] if obj_type else list(OBJECT_TYPES)

        for t in types:
            nodes = self.orch.query_nodes(t, {"limit": limit})
            for node in nodes:
                suggestions = self.discover_for_node(node["id"])
                all_suggestions.extend(suggestions)

        return all_suggestions
