"""Tests for the PIM agent constellation."""

import json
import sqlite3
from pathlib import Path
import pytest

from src.db import init_db
from src.adapters.internal import InternalAdapter
from src.orchestrator import Orchestrator
from src.semantic import SemanticIndex
from src.identity import IdentityResolver
from src.agents import (
    InterpreterAgent, ExecutorAgent, BriefingAgent,
    ResearchAgent, DiscoveryAgent, ConfigAgent,
)


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


# --- Interpreter Agent ---

class TestInterpreterAgent:
    def test_decompose_task(self, setup):
        agent = InterpreterAgent(setup["orch"])
        plan = agent.decompose("todo: buy groceries")
        assert len(plan["nodes_to_create"]) == 1
        assert plan["nodes_to_create"][0]["type"] == "task"

    def test_decompose_event(self, setup):
        agent = InterpreterAgent(setup["orch"])
        plan = agent.decompose("meeting with team at 3pm")
        assert plan["nodes_to_create"][0]["type"] == "event"

    def test_decompose_contact(self, setup):
        agent = InterpreterAgent(setup["orch"])
        plan = agent.decompose("contact: John Doe, john@example.com")
        assert plan["nodes_to_create"][0]["type"] == "contact"

    def test_decompose_default_note(self, setup):
        agent = InterpreterAgent(setup["orch"])
        plan = agent.decompose("random thoughts about the universe")
        assert plan["nodes_to_create"][0]["type"] == "note"

    def test_execute_plan(self, setup):
        agent = InterpreterAgent(setup["orch"])
        plan = agent.decompose("todo: test the system")
        result = agent.execute_plan(plan)
        assert len(result["nodes_created"]) == 1
        assert result["nodes_created"][0].startswith("pim://task/")

    def test_execute_empty_plan(self, setup):
        agent = InterpreterAgent(setup["orch"])
        result = agent.execute_plan({"nodes_to_create": [], "edges_to_create": []})
        assert result["nodes_created"] == []


# --- Executor Agent ---

class TestExecutorAgent:
    def test_batch_create(self, setup):
        agent = ExecutorAgent(setup["orch"])
        results = agent.batch_create([
            {"type": "note", "attributes": {"title": "Note 1"}},
            {"type": "task", "attributes": {"title": "Task 1", "status": "open"}},
        ])
        assert len(results) == 2
        assert all(r["status"] == "created" for r in results)

    def test_batch_create_with_error(self, setup):
        agent = ExecutorAgent(setup["orch"])
        count_before = setup["conn"].execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        # Bulk create is atomic — invalid type rolls back entire batch
        with pytest.raises(ValueError, match="Invalid type"):
            agent.batch_create([
                {"type": "note", "attributes": {"title": "Good"}},
                {"type": "invalid_type", "attributes": {"title": "Bad"}},
            ])
        # Verify nothing persisted — atomicity guarantee
        count_after = setup["conn"].execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        assert count_after == count_before

    def test_batch_update(self, setup):
        agent = ExecutorAgent(setup["orch"])
        node = setup["orch"].create_node("note", {"title": "Original"})
        results = agent.batch_update([
            {"id": node["id"], "changes": {"attributes": {"title": "Updated"}}},
        ])
        assert results[0]["status"] == "updated"

    def test_move_register(self, setup):
        agent = ExecutorAgent(setup["orch"])
        node = setup["orch"].create_node("note", {"title": "Move me"})
        results = agent.move_register([node["id"]], "working")
        assert results[0]["status"] == "moved"


# --- Briefing Agent ---

class TestBriefingAgent:
    def test_inbox_review_empty(self, setup):
        agent = BriefingAgent(setup["orch"])
        review = agent.inbox_review()
        assert review["register"] == "scratch"
        assert review["total"] == 0

    def test_inbox_review_with_items(self, setup):
        agent = BriefingAgent(setup["orch"])
        setup["orch"].create_node("note", {"title": "Inbox note"})
        setup["orch"].create_node("task", {"title": "Inbox task", "status": "open"})
        review = agent.inbox_review()
        assert review["total"] >= 2

    def test_topic_briefing(self, setup):
        agent = BriefingAgent(setup["orch"])
        topic = setup["orch"].create_node("topic", {"title": "Test Topic", "status": "active"})
        note = setup["orch"].create_node("note", {"title": "Related note"})
        setup["orch"].create_edge(note["id"], topic["id"], "belongs-to")

        briefing = agent.topic_briefing(topic["id"])
        assert briefing["topic"] == topic["id"]
        assert briefing["related_count"] >= 1

    def test_contact_dossier(self, setup):
        agent = BriefingAgent(setup["orch"])
        contact = setup["orch"].create_node("contact", {"name": "Alice"})
        task = setup["orch"].create_node("task", {"title": "Call Alice", "status": "open"})
        setup["orch"].create_edge(task["id"], contact["id"], "involves")

        dossier = agent.contact_dossier(contact["id"])
        assert dossier["contact"] == contact["id"]
        assert dossier["total_relations"] >= 1


# --- Research Agent ---

class TestResearchAgent:
    def test_text_search(self, setup):
        agent = ResearchAgent(setup["orch"])
        setup["orch"].create_node("entry", {"title": "PIM research notes"}, body="PIM research findings")
        result = agent.search("PIM")
        assert result["total_text"] >= 1

    def test_search_no_results(self, setup):
        agent = ResearchAgent(setup["orch"])
        result = agent.search("nonexistent_xyz_12345")
        assert result["total_text"] == 0

    def test_search_with_type_filter(self, setup):
        agent = ResearchAgent(setup["orch"])
        setup["orch"].create_node("note", {"title": "Note about test"}, body="test content")
        setup["orch"].create_node("entry", {"title": "Entry about test"}, body="test content")
        result = agent.search("test", obj_type="note")
        for n in result["results"]["text_results"]:
            assert n["type"] == "note"

    def test_trace_connections(self, setup):
        agent = ResearchAgent(setup["orch"])
        n1 = setup["orch"].create_node("note", {"title": "Root"})
        n2 = setup["orch"].create_node("note", {"title": "Connected"})
        setup["orch"].create_edge(n1["id"], n2["id"], "references")

        trace = agent.trace_connections(n1["id"], depth=1)
        assert trace["root"] == n1["id"]
        assert trace["total_edges"] >= 1


# --- Discovery Agent ---

class TestDiscoveryAgent:
    def test_find_orphans(self, setup):
        agent = DiscoveryAgent(setup["orch"])
        setup["orch"].create_node("note", {"title": "Orphan note"})
        orphans = agent.find_orphans("note")
        assert len(orphans) >= 1

    def test_find_orphans_excludes_connected(self, setup):
        agent = DiscoveryAgent(setup["orch"])
        n1 = setup["orch"].create_node("note", {"title": "Connected"})
        n2 = setup["orch"].create_node("topic", {"title": "Topic", "status": "active"})
        setup["orch"].create_edge(n1["id"], n2["id"], "belongs-to")
        orphans = agent.find_orphans("note")
        orphan_ids = [o["id"] for o in orphans]
        assert n1["id"] not in orphan_ids

    def test_suggest_relations(self, setup):
        agent = DiscoveryAgent(setup["orch"], resolver=setup["resolver"])
        setup["orch"].create_node("contact", {"name": "John Doe"})
        c2 = setup["orch"].create_node("contact", {"name": "John Doe"})
        suggestions = agent.suggest_relations(c2["id"])
        # Should suggest the duplicate
        assert len(suggestions) >= 1

    def test_find_duplicates(self, setup):
        agent = DiscoveryAgent(setup["orch"], resolver=setup["resolver"])
        setup["orch"].create_node("contact", {"name": "Alice"})
        setup["orch"].create_node("contact", {"name": "Alice"})
        dupes = agent.find_duplicates("contact", min_confidence=0.5)
        assert len(dupes) >= 1

    def test_find_duplicates_no_resolver(self, setup):
        agent = DiscoveryAgent(setup["orch"])
        dupes = agent.find_duplicates("contact")
        assert dupes == []


# --- Config Agent ---

class TestConfigAgent:
    def test_list_adapters(self, setup):
        agent = ConfigAgent(setup["orch"], setup["conn"])
        adapters = agent.list_adapters()
        assert len(adapters) >= 1
        assert adapters[0]["id"] == "internal"

    def test_get_routing(self, setup):
        agent = ConfigAgent(setup["orch"], setup["conn"])
        routing = agent.get_routing()
        assert isinstance(routing, dict)

    def test_set_routing(self, setup):
        agent = ConfigAgent(setup["orch"], setup["conn"])
        new_routing = {"task": "omnifocus"}
        result = agent.set_routing(new_routing)
        assert result == new_routing
        assert agent.get_routing() == new_routing

    def test_get_stats(self, setup):
        agent = ConfigAgent(setup["orch"], setup["conn"])
        setup["orch"].create_node("note", {"title": "Stat test"})
        stats = agent.get_stats()
        assert stats["total_nodes"] >= 1
        assert "note" in stats["types"]
        assert "scratch" in stats["registers"]
