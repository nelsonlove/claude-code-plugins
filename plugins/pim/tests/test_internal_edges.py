# tests/test_internal_edges.py
import pytest
from src.db import init_db
from src.adapters.internal import InternalAdapter

@pytest.fixture
def adapter(tmp_data_dir):
    conn = init_db(tmp_data_dir / "pim.db")
    return InternalAdapter(conn, tmp_data_dir)

@pytest.fixture
def two_nodes(adapter):
    note = adapter.create_node("note", {"title": "Design doc"})
    topic = adapter.create_node("topic", {"title": "PIM Project", "status": "active"})
    return note, topic

def test_create_edge(adapter, two_nodes):
    note, topic = two_nodes
    edge = adapter.create_edge(note["id"], topic["id"], "belongs-to")
    assert edge is not None
    assert edge["source"] == note["id"]
    assert edge["target"] == topic["id"]
    assert edge["type"] == "belongs-to"

def test_query_edges_outbound(adapter, two_nodes):
    note, topic = two_nodes
    adapter.create_edge(note["id"], topic["id"], "belongs-to")

    edges = adapter.query_edges(note["id"], direction="outbound")
    assert len(edges) == 1
    assert edges[0]["target"] == topic["id"]

def test_query_edges_inbound(adapter, two_nodes):
    note, topic = two_nodes
    adapter.create_edge(note["id"], topic["id"], "belongs-to")

    edges = adapter.query_edges(topic["id"], direction="inbound")
    assert len(edges) == 1
    assert edges[0]["source"] == note["id"]

def test_query_edges_by_type(adapter, two_nodes):
    note, topic = two_nodes
    adapter.create_edge(note["id"], topic["id"], "belongs-to")
    adapter.create_edge(note["id"], topic["id"], "annotation-of")

    edges = adapter.query_edges(note["id"], direction="outbound", edge_type="belongs-to")
    assert len(edges) == 1

def test_close_edge(adapter, two_nodes):
    note, topic = two_nodes
    edge = adapter.create_edge(note["id"], topic["id"], "belongs-to")
    adapter.close_edge(edge["id"])

    edges = adapter.query_edges(note["id"], direction="outbound")
    assert len(edges) == 0

def test_duplicate_edge_idempotent(adapter, two_nodes):
    note, topic = two_nodes
    edge1 = adapter.create_edge(note["id"], topic["id"], "belongs-to")
    edge2 = adapter.create_edge(note["id"], topic["id"], "belongs-to")
    assert edge1["id"] == edge2["id"]  # same edge returned
