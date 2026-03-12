# tests/test_orchestrator.py
import pytest
from src.db import init_db
from src.adapters.internal import InternalAdapter
from src.orchestrator import Orchestrator

@pytest.fixture
def orchestrator(tmp_data_dir):
    conn = init_db(tmp_data_dir / "pim.db")
    internal = InternalAdapter(conn, tmp_data_dir)
    return Orchestrator(conn=conn, internal_adapter=internal, data_dir=tmp_data_dir)

def test_create_node_routes_to_internal(orchestrator):
    node = orchestrator.create_node("note", {"title": "Test"}, register="scratch")
    assert node["adapter"] == "internal"
    assert node["type"] == "note"

def test_create_node_logs_decision(orchestrator):
    node = orchestrator.create_node("note", {"title": "Test"})
    log = orchestrator.get_decision_log(target=node["id"])
    assert len(log) == 1
    assert log[0]["operation"] == "create_node"
    assert log[0]["risk_tier"] == "medium"

def test_query_nodes(orchestrator):
    orchestrator.create_node("note", {"title": "A"})
    orchestrator.create_node("note", {"title": "B"})
    orchestrator.create_node("task", {"title": "T", "status": "open"})
    notes = orchestrator.query_nodes("note")
    assert len(notes) == 2

def test_update_node(orchestrator):
    node = orchestrator.create_node("task", {"title": "Old", "status": "open"})
    updated = orchestrator.update_node(node["id"], {"attributes": {"title": "New"}})
    assert updated["attributes"]["title"] == "New"

def test_close_node(orchestrator):
    node = orchestrator.create_node("task", {"title": "Doomed", "status": "open"})
    orchestrator.close_node(node["id"], "complete")
    results = orchestrator.query_nodes("task", {"register": "log"})
    assert len(results) == 1

def test_create_edge(orchestrator):
    note = orchestrator.create_node("note", {"title": "Doc"})
    topic = orchestrator.create_node("topic", {"title": "Project", "status": "active"})
    edge = orchestrator.create_edge(note["id"], topic["id"], "belongs-to")
    assert edge["type"] == "belongs-to"

def test_query_edges(orchestrator):
    note = orchestrator.create_node("note", {"title": "Doc"})
    topic = orchestrator.create_node("topic", {"title": "Project", "status": "active"})
    orchestrator.create_edge(note["id"], topic["id"], "belongs-to")
    edges = orchestrator.query_edges(source=note["id"])
    assert len(edges) == 1

def test_register_transition_logged(orchestrator):
    node = orchestrator.create_node("note", {"title": "Test"})
    orchestrator.update_node(node["id"], {"register": "working"})
    log = orchestrator.get_decision_log(target=node["id"])
    assert len(log) == 2  # create + update
