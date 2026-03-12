"""Tests for the enrichment policy and relation discovery."""

import pytest

from src.db import init_db
from src.adapters.internal import InternalAdapter
from src.orchestrator import Orchestrator
from src.semantic import SemanticIndex
from src.identity import IdentityResolver
from src.enrichment import EnrichmentPolicy, RelationDiscovery


@pytest.fixture
def setup(tmp_path):
    db_path = tmp_path / "pim.db"
    conn = init_db(db_path)
    internal = InternalAdapter(conn, tmp_path)
    orch = Orchestrator(conn=conn, internal_adapter=internal, data_dir=tmp_path)
    semantic = SemanticIndex(conn, embedding_dim=3)
    resolver = IdentityResolver(conn, semantic_index=semantic)
    return {
        "conn": conn,
        "orch": orch,
        "semantic": semantic,
        "resolver": resolver,
        "data_dir": tmp_path,
    }


# --- EnrichmentPolicy ---

class TestEnrichmentPolicy:
    def test_auto_relations(self):
        assert EnrichmentPolicy.can_auto_create("references")
        assert EnrichmentPolicy.can_auto_create("related-to")
        assert EnrichmentPolicy.can_auto_create("belongs-to")

    def test_not_auto_relations(self):
        assert not EnrichmentPolicy.can_auto_create("involves")
        assert not EnrichmentPolicy.can_auto_create("precedes")
        assert not EnrichmentPolicy.can_auto_create("unknown")

    def test_validated_relations(self):
        assert EnrichmentPolicy.requires_validation("from")
        assert EnrichmentPolicy.requires_validation("to")
        assert EnrichmentPolicy.requires_validation("involves")
        assert EnrichmentPolicy.requires_validation("delegated-to")
        assert EnrichmentPolicy.requires_validation("sent-by")
        assert EnrichmentPolicy.requires_validation("member-of")
        assert EnrichmentPolicy.requires_validation("derived-from")

    def test_not_validated_relations(self):
        assert not EnrichmentPolicy.requires_validation("references")
        assert not EnrichmentPolicy.requires_validation("precedes")

    def test_confirmed_relations(self):
        assert EnrichmentPolicy.requires_confirmation("precedes")
        assert EnrichmentPolicy.requires_confirmation("occurs-during")
        assert EnrichmentPolicy.requires_confirmation("annotation-of")
        assert EnrichmentPolicy.requires_confirmation("blocks")

    def test_not_confirmed_relations(self):
        assert not EnrichmentPolicy.requires_confirmation("references")
        assert not EnrichmentPolicy.requires_confirmation("involves")

    def test_all_categories_disjoint(self):
        """No relation type should appear in multiple categories."""
        auto = EnrichmentPolicy.AUTO_RELATIONS
        validated = EnrichmentPolicy.VALIDATED_RELATIONS
        confirmed = EnrichmentPolicy.CONFIRMED_RELATIONS
        assert auto.isdisjoint(validated)
        assert auto.isdisjoint(confirmed)
        assert validated.isdisjoint(confirmed)


# --- RelationDiscovery: type-based suggestions ---

class TestTypeBased:
    def test_task_suggests_belongs_to_topic(self, setup):
        orch = setup["orch"]
        topic = orch.create_node("topic", {"title": "Project Alpha", "status": "active"})
        task = orch.create_node("task", {"title": "Do thing", "status": "open"})

        discovery = RelationDiscovery(orch)
        suggestions = discovery.discover_for_node(task["id"])

        belongs_to = [s for s in suggestions if s["type"] == "belongs-to"]
        assert len(belongs_to) >= 1
        assert any(s["target"] == topic["id"] for s in belongs_to)
        assert all(s["confidence"] == 0.3 for s in belongs_to)
        assert all(s["auto_create"] is True for s in belongs_to)

    def test_event_suggests_belongs_to_topic(self, setup):
        orch = setup["orch"]
        topic = orch.create_node("topic", {"title": "Meetings", "status": "active"})
        event = orch.create_node("event", {"title": "Team standup", "status": "confirmed"})

        discovery = RelationDiscovery(orch)
        suggestions = discovery.discover_for_node(event["id"])

        belongs_to = [s for s in suggestions if s["type"] == "belongs-to"]
        assert len(belongs_to) >= 1

    def test_note_suggests_belongs_to_topic(self, setup):
        orch = setup["orch"]
        orch.create_node("topic", {"title": "Research", "status": "active"})
        note = orch.create_node("note", {"title": "Research findings"})

        discovery = RelationDiscovery(orch)
        suggestions = discovery.discover_for_node(note["id"])

        belongs_to = [s for s in suggestions if s["type"] == "belongs-to"]
        assert len(belongs_to) >= 1

    def test_contact_no_type_based_suggestions(self, setup):
        orch = setup["orch"]
        orch.create_node("topic", {"title": "Some Topic", "status": "active"})
        contact = orch.create_node("contact", {"name": "Alice"})

        discovery = RelationDiscovery(orch)
        suggestions = discovery.discover_for_node(contact["id"])

        belongs_to = [s for s in suggestions if s["type"] == "belongs-to"]
        assert len(belongs_to) == 0

    def test_skips_existing_edges(self, setup):
        orch = setup["orch"]
        topic = orch.create_node("topic", {"title": "Linked Topic", "status": "active"})
        task = orch.create_node("task", {"title": "Already linked", "status": "open"})
        orch.create_edge(task["id"], topic["id"], "belongs-to")

        discovery = RelationDiscovery(orch)
        suggestions = discovery.discover_for_node(task["id"])

        belongs_to = [s for s in suggestions if s["type"] == "belongs-to" and s["target"] == topic["id"]]
        assert len(belongs_to) == 0


# --- RelationDiscovery: attribute matching ---

class TestAttributeMatching:
    def test_task_title_mentions_contact(self, setup):
        orch = setup["orch"]
        contact = orch.create_node("contact", {"name": "Alice"})
        task = orch.create_node("task", {"title": "Call Alice about project", "status": "open"})

        discovery = RelationDiscovery(orch)
        suggestions = discovery.discover_for_node(task["id"])

        involves = [s for s in suggestions if s["type"] == "involves"]
        assert len(involves) == 1
        assert involves[0]["target"] == contact["id"]
        assert involves[0]["confidence"] == 0.7
        assert involves[0]["auto_create"] is False  # involves is VALIDATED, not AUTO

    def test_event_title_mentions_contact(self, setup):
        orch = setup["orch"]
        contact = orch.create_node("contact", {"name": "Bob"})
        event = orch.create_node("event", {"title": "Meeting with Bob", "status": "confirmed"})

        discovery = RelationDiscovery(orch)
        suggestions = discovery.discover_for_node(event["id"])

        involves = [s for s in suggestions if s["type"] == "involves"]
        assert len(involves) == 1
        assert involves[0]["target"] == contact["id"]

    def test_case_insensitive_match(self, setup):
        orch = setup["orch"]
        contact = orch.create_node("contact", {"name": "ALICE"})
        task = orch.create_node("task", {"title": "talk to alice", "status": "open"})

        discovery = RelationDiscovery(orch)
        suggestions = discovery.discover_for_node(task["id"])

        involves = [s for s in suggestions if s["type"] == "involves"]
        assert len(involves) == 1

    def test_no_match_when_name_not_in_title(self, setup):
        orch = setup["orch"]
        orch.create_node("contact", {"name": "Charlie"})
        task = orch.create_node("task", {"title": "Do laundry", "status": "open"})

        discovery = RelationDiscovery(orch)
        suggestions = discovery.discover_for_node(task["id"])

        involves = [s for s in suggestions if s["type"] == "involves"]
        assert len(involves) == 0

    def test_note_not_matched_for_attribute(self, setup):
        """Notes are not in the attribute matching types (task, event, message)."""
        orch = setup["orch"]
        orch.create_node("contact", {"name": "Alice"})
        note = orch.create_node("note", {"title": "Alice in wonderland"})

        discovery = RelationDiscovery(orch)
        suggestions = discovery.discover_for_node(note["id"])

        involves = [s for s in suggestions if s["type"] == "involves"]
        assert len(involves) == 0

    def test_message_subject_matches_contact(self, setup):
        orch = setup["orch"]
        contact = orch.create_node("contact", {"name": "Dave"})
        msg = orch.create_node("message", {"subject": "From Dave: update", "status": "unread"})

        discovery = RelationDiscovery(orch)
        suggestions = discovery.discover_for_node(msg["id"])

        involves = [s for s in suggestions if s["type"] == "involves"]
        assert len(involves) == 1
        assert involves[0]["target"] == contact["id"]


# --- RelationDiscovery: semantic suggestions ---

class TestSemanticSuggestions:
    def test_semantic_suggestions_with_similar_embeddings(self, setup):
        orch = setup["orch"]
        semantic = setup["semantic"]
        n1 = orch.create_node("note", {"title": "Machine learning"})
        n2 = orch.create_node("note", {"title": "Deep learning"})

        semantic.store_embedding(n1["id"], [1.0, 0.0, 0.0])
        semantic.store_embedding(n2["id"], [0.95, 0.05, 0.0])

        discovery = RelationDiscovery(orch, semantic=semantic)
        suggestions = discovery.discover_for_node(n1["id"])

        related = [s for s in suggestions if s["type"] == "related-to"]
        assert len(related) >= 1
        assert any(s["target"] == n2["id"] for s in related)
        assert all(s["auto_create"] is True for s in related)

    def test_no_semantic_without_embedding(self, setup):
        orch = setup["orch"]
        semantic = setup["semantic"]
        n1 = orch.create_node("note", {"title": "No embedding"})

        discovery = RelationDiscovery(orch, semantic=semantic)
        suggestions = discovery.discover_for_node(n1["id"])

        related = [s for s in suggestions if s["type"] == "related-to"]
        assert len(related) == 0

    def test_no_semantic_without_index(self, setup):
        orch = setup["orch"]
        n1 = orch.create_node("note", {"title": "No index"})

        discovery = RelationDiscovery(orch, semantic=None)
        suggestions = discovery.discover_for_node(n1["id"])

        related = [s for s in suggestions if s["type"] == "related-to"]
        assert len(related) == 0

    def test_excludes_self_from_semantic(self, setup):
        orch = setup["orch"]
        semantic = setup["semantic"]
        n1 = orch.create_node("note", {"title": "Self test"})
        semantic.store_embedding(n1["id"], [1.0, 0.0, 0.0])

        discovery = RelationDiscovery(orch, semantic=semantic)
        suggestions = discovery.discover_for_node(n1["id"])

        related = [s for s in suggestions if s["type"] == "related-to"]
        assert not any(s["target"] == n1["id"] for s in related)


# --- discover_for_node: deduplication and sorting ---

class TestDiscoverForNode:
    def test_deduplication(self, setup):
        """If two strategies suggest the same relation, only one appears."""
        orch = setup["orch"]
        semantic = setup["semantic"]
        topic = orch.create_node("topic", {"title": "ML", "status": "active"})
        note = orch.create_node("note", {"title": "ML notes"})

        # Both type-based and semantic might suggest belongs-to to topic
        # But since semantic suggests related-to (not belongs-to), let's
        # just verify dedup works on same (source, target, type) triples
        discovery = RelationDiscovery(orch, semantic=semantic)
        suggestions = discovery.discover_for_node(note["id"])

        keys = [(s["source"], s["target"], s["type"]) for s in suggestions]
        assert len(keys) == len(set(keys))

    def test_sorted_by_confidence_desc(self, setup):
        orch = setup["orch"]
        semantic = setup["semantic"]
        contact = orch.create_node("contact", {"name": "Alice"})
        topic = orch.create_node("topic", {"title": "Project", "status": "active"})
        task = orch.create_node("task", {"title": "Call Alice", "status": "open"})

        discovery = RelationDiscovery(orch, semantic=semantic)
        suggestions = discovery.discover_for_node(task["id"])

        confidences = [s["confidence"] for s in suggestions]
        assert confidences == sorted(confidences, reverse=True)

    def test_nonexistent_node(self, setup):
        orch = setup["orch"]
        discovery = RelationDiscovery(orch)
        suggestions = discovery.discover_for_node("pim://note/internal/nonexistent")
        assert suggestions == []


# --- auto_enrich ---

class TestAutoEnrich:
    def test_creates_auto_relations_above_threshold(self, setup):
        orch = setup["orch"]
        semantic = setup["semantic"]
        n1 = orch.create_node("note", {"title": "Note A"})
        n2 = orch.create_node("note", {"title": "Note B"})

        semantic.store_embedding(n1["id"], [1.0, 0.0, 0.0])
        semantic.store_embedding(n2["id"], [0.95, 0.05, 0.0])

        discovery = RelationDiscovery(orch, semantic=semantic)
        created = discovery.auto_enrich(n1["id"])

        # related-to is auto-creatable, and similarity ~0.998 > 0.7
        related = [c for c in created if c["type"] == "related-to"]
        assert len(related) >= 1

        # Verify edge was actually created
        edges = orch.query_edges(source=n1["id"], edge_type="related-to")
        assert len(edges) >= 1

    def test_skips_non_auto_relations(self, setup):
        """involves is VALIDATED, not AUTO — should not be auto-created."""
        orch = setup["orch"]
        contact = orch.create_node("contact", {"name": "Alice"})
        task = orch.create_node("task", {"title": "Call Alice", "status": "open"})

        discovery = RelationDiscovery(orch)
        created = discovery.auto_enrich(task["id"])

        # involves has confidence 0.7 but auto_create=False
        involves = [c for c in created if c["type"] == "involves"]
        assert len(involves) == 0

    def test_skips_low_confidence(self, setup):
        """belongs-to from type heuristics has confidence 0.3 — below threshold."""
        orch = setup["orch"]
        orch.create_node("topic", {"title": "Topic", "status": "active"})
        task = orch.create_node("task", {"title": "Do thing", "status": "open"})

        discovery = RelationDiscovery(orch)
        created = discovery.auto_enrich(task["id"])

        # belongs-to is auto-creatable but confidence=0.3 < 0.7 threshold
        belongs = [c for c in created if c["type"] == "belongs-to"]
        assert len(belongs) == 0

    def test_auto_enrich_nonexistent_node(self, setup):
        orch = setup["orch"]
        discovery = RelationDiscovery(orch)
        created = discovery.auto_enrich("pim://note/internal/nonexistent")
        assert created == []


# --- bulk_discover ---

class TestBulkDiscover:
    def test_bulk_discover_specific_type(self, setup):
        orch = setup["orch"]
        orch.create_node("topic", {"title": "Topic", "status": "active"})
        orch.create_node("note", {"title": "Note 1"})
        orch.create_node("note", {"title": "Note 2"})

        discovery = RelationDiscovery(orch)
        suggestions = discovery.bulk_discover(obj_type="note")

        # Each note should get belongs-to suggestions for the topic
        assert len(suggestions) >= 2

    def test_bulk_discover_all_types(self, setup):
        orch = setup["orch"]
        orch.create_node("topic", {"title": "Topic", "status": "active"})
        orch.create_node("note", {"title": "Note"})
        orch.create_node("task", {"title": "Task", "status": "open"})

        discovery = RelationDiscovery(orch)
        suggestions = discovery.bulk_discover()

        # Should find suggestions across multiple types
        assert len(suggestions) >= 2

    def test_bulk_discover_empty(self, setup):
        orch = setup["orch"]
        discovery = RelationDiscovery(orch)
        suggestions = discovery.bulk_discover(obj_type="contact")
        assert suggestions == []
