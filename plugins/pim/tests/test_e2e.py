"""End-to-end test: create objects, link them, query the graph."""
import pytest
from src.db import init_db
from src.adapters.internal import InternalAdapter
from src.orchestrator import Orchestrator

@pytest.fixture
def orch(tmp_data_dir):
    conn = init_db(tmp_data_dir / "pim.db")
    internal = InternalAdapter(conn, tmp_data_dir)
    return Orchestrator(conn=conn, internal_adapter=internal, data_dir=tmp_data_dir)

def test_full_workflow(orch):
    """Simulate the architecture doc's end-to-end example (simplified)."""
    sarah = orch.create_node("contact", {"name": "Sarah Chen", "email": "sarah@acme.com"})
    q3 = orch.create_node("topic", {"title": "Q3 Review", "status": "active"}, register="working")
    msg = orch.create_node("message", {
        "subject": "Q3 review meeting",
        "sent_at": "2026-03-12T10:00:00",
        "channel": "email",
        "direction": "inbound",
    }, body="Hi, can we meet Thursday at 2pm? I need the revenue report by Wednesday.")
    event = orch.create_node("event", {
        "title": "Q3 Review Meeting",
        "start": "2026-03-14T14:00:00",
        "end": "2026-03-14T15:00:00",
        "status": "confirmed",
    }, register="working")
    task = orch.create_node("task", {
        "title": "Send revenue report",
        "status": "open",
        "due_date": "2026-03-13",
    }, register="working")

    orch.create_edge(msg["id"], sarah["id"], "from")
    orch.create_edge(event["id"], sarah["id"], "involves")
    orch.create_edge(event["id"], msg["id"], "derived-from")
    orch.create_edge(task["id"], msg["id"], "derived-from")
    orch.create_edge(msg["id"], q3["id"], "belongs-to")
    orch.create_edge(event["id"], q3["id"], "belongs-to")
    orch.create_edge(task["id"], q3["id"], "belongs-to")

    q3_edges = orch.query_edges(target=q3["id"], edge_type="belongs-to")
    assert len(q3_edges) == 3

    sarah_edges = orch.query_edges(target=sarah["id"])
    assert len(sarah_edges) == 2

    working_tasks = orch.query_nodes("task", {"register": "working"})
    assert len(working_tasks) == 1
    assert working_tasks[0]["attributes"]["title"] == "Send revenue report"

    orch.close_node(task["id"], "complete")
    log_tasks = orch.query_nodes("task", {"register": "log"})
    assert len(log_tasks) == 1
    assert log_tasks[0]["attributes"]["status"] == "completed"

    log = orch.get_decision_log()
    assert len(log) > 0

def test_text_search_across_bodies(orch):
    """Verify FTS works across node bodies."""
    orch.create_node("note", {"title": "API Design"}, body="REST endpoints for the billing system")
    orch.create_node("note", {"title": "Meeting Notes"}, body="Discussed the new billing flow with the team")
    orch.create_node("note", {"title": "Recipe"}, body="Chocolate chip cookies need butter and sugar")

    results = orch.query_nodes("note", {"text_search": "billing"})
    assert len(results) == 2

    results = orch.query_nodes("note", {"text_search": "cookies"})
    assert len(results) == 1
