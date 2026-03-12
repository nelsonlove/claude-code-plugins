# tests/test_internal_adapter.py
import pytest
from src.db import init_db
from src.adapters.internal import InternalAdapter

@pytest.fixture
def adapter(tmp_data_dir):
    db_path = tmp_data_dir / "pim.db"
    conn = init_db(db_path)
    return InternalAdapter(conn, tmp_data_dir)

def test_create_node(adapter):
    node = adapter.create_node("note", {"title": "Test note"}, body="Hello world")
    assert node["type"] == "note"
    assert node["attributes"]["title"] == "Test note"
    assert node["id"].startswith("pim://note/internal/")

def test_query_nodes_by_type(adapter):
    adapter.create_node("note", {"title": "Note 1"})
    adapter.create_node("note", {"title": "Note 2"})
    adapter.create_node("task", {"title": "Task 1", "status": "open"})

    notes = adapter.query_nodes("note")
    assert len(notes) == 2
    tasks = adapter.query_nodes("task")
    assert len(tasks) == 1

def test_query_nodes_text_search(adapter):
    adapter.create_node("note", {"title": "Quantum physics"}, body="Schrodinger's cat is both alive and dead")
    adapter.create_node("note", {"title": "Grocery list"}, body="Buy milk and eggs")

    results = adapter.query_nodes("note", {"text_search": "quantum"})
    assert len(results) == 1
    assert results[0]["attributes"]["title"] == "Quantum physics"

def test_update_node(adapter):
    node = adapter.create_node("task", {"title": "Old title", "status": "open"})
    native_id = node["native_id"]

    updated = adapter.update_node(native_id, {"attributes": {"title": "New title"}})
    assert updated["attributes"]["title"] == "New title"

def test_close_node_delete(adapter):
    node = adapter.create_node("note", {"title": "Doomed"})
    native_id = node["native_id"]

    adapter.close_node(native_id, "delete")
    results = adapter.query_nodes("note")
    assert len(results) == 0

def test_resolve_and_reverse_resolve(adapter):
    node = adapter.create_node("contact", {"name": "Sarah Chen"})
    native_id = node["native_id"]
    pim_id = node["id"]

    resolved = adapter.resolve(native_id)
    assert resolved["id"] == pim_id

    reverse = adapter.reverse_resolve(pim_id)
    assert reverse == native_id

def test_fetch_body(adapter):
    node = adapter.create_node("note", {"title": "Test"}, body="The body content")
    body = adapter.fetch_body(node["native_id"])
    assert body == "The body content"

def test_body_externalization(adapter):
    big_body = "x" * 200_000  # over 100KB threshold
    node = adapter.create_node("note", {"title": "Big"}, body=big_body)
    assert node.get("body_path") is not None
    fetched = adapter.fetch_body(node["native_id"])
    assert fetched == big_body

def test_enumerate(adapter):
    for i in range(5):
        adapter.create_node("note", {"title": f"Note {i}"})
    page = adapter.enumerate("note", limit=3, offset=0)
    assert len(page) == 3
    page2 = adapter.enumerate("note", limit=3, offset=3)
    assert len(page2) == 2

def test_register_default_scratch(adapter):
    node = adapter.create_node("note", {"title": "New"})
    assert node["register"] == "scratch"

def test_update_register(adapter):
    node = adapter.create_node("note", {"title": "New"})
    updated = adapter.update_node(node["native_id"], {"register": "working"})
    assert updated["register"] == "working"
