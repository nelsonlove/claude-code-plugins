"""Tests for the OmniFocus adapter — all subprocess calls are mocked."""

import json
import pytest
from unittest.mock import patch, MagicMock

from src.adapters.omnifocus import OmniFocusAdapter


@pytest.fixture
def adapter():
    return OmniFocusAdapter()


@pytest.fixture
def mock_jxa():
    with patch("src.adapters.omnifocus.subprocess.run") as mock_run:
        yield mock_run


# --- health_check ---

def test_health_check_success(adapter, mock_jxa):
    mock_jxa.return_value = MagicMock(returncode=0, stdout="OmniFocus", stderr="")
    assert adapter.health_check() is True


def test_health_check_failure(adapter, mock_jxa):
    mock_jxa.return_value = MagicMock(returncode=1, stdout="", stderr="error")
    assert adapter.health_check() is False


# --- create_node (task) ---

def test_create_task(adapter, mock_jxa):
    mock_jxa.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({"id": "abc123", "name": "Buy milk", "completed": False}),
        stderr="",
    )
    node = adapter.create_node("task", {"title": "Buy milk", "status": "open"})
    assert node["type"] == "task"
    assert node["native_id"] == "abc123"
    assert node["attributes"]["title"] == "Buy milk"


def test_create_task_in_project(adapter, mock_jxa):
    mock_jxa.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({"id": "t99", "name": "Subtask", "completed": False}),
        stderr="",
    )
    node = adapter.create_node("task", {"title": "Subtask", "project_id": "proj1"})
    assert node["native_id"] == "t99"
    # Verify JXA script references the project ID
    call_args = mock_jxa.call_args[0][0]
    assert "proj1" in call_args[4]  # -e script


def test_create_task_flagged(adapter, mock_jxa):
    mock_jxa.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({"id": "f1", "name": "Urgent", "completed": False}),
        stderr="",
    )
    node = adapter.create_node("task", {"title": "Urgent", "flagged": True})
    assert node["native_id"] == "f1"
    call_script = mock_jxa.call_args[0][0][4]
    assert "true" in call_script  # flagged: true


# --- query_nodes ---

def test_query_tasks(adapter, mock_jxa):
    mock_jxa.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps([
            {"id": "t1", "name": "Task 1", "completed": False, "flagged": False, "inInbox": False, "tags": []},
            {"id": "t2", "name": "Task 2", "completed": False, "flagged": True, "inInbox": False, "tags": []},
        ]),
        stderr="",
    )
    tasks = adapter.query_nodes("task")
    assert len(tasks) == 2


def test_query_tasks_by_register(adapter, mock_jxa):
    mock_jxa.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps([
            {"id": "t1", "name": "Inbox task", "completed": False, "flagged": False, "inInbox": True, "tags": []},
        ]),
        stderr="",
    )
    tasks = adapter.query_nodes("task", {"register": "scratch"})
    assert len(tasks) == 1
    assert tasks[0]["register"] == "scratch"


def test_query_projects(adapter, mock_jxa):
    mock_jxa.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps([
            {"id": "p1", "name": "Project A", "status": "active", "sequential": False},
            {"id": "p2", "name": "Project B", "status": "active", "sequential": True},
        ]),
        stderr="",
    )
    topics = adapter.query_nodes("topic")
    assert len(topics) == 2
    assert topics[0]["type"] == "topic"


# --- update_node ---

def test_update_task(adapter, mock_jxa):
    mock_jxa.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({"id": "t1", "name": "Updated", "completed": False}),
        stderr="",
    )
    updated = adapter.update_node("t1", {"attributes": {"title": "Updated"}})
    assert updated["attributes"]["title"] == "Updated"


# --- close_node ---

def test_close_task_complete(adapter, mock_jxa):
    mock_jxa.return_value = MagicMock(returncode=0, stdout="", stderr="")
    adapter.close_node("t1", "complete")  # should not raise


def test_close_task_delete(adapter, mock_jxa):
    mock_jxa.return_value = MagicMock(returncode=0, stdout="", stderr="")
    adapter.close_node("t1", "delete")  # should not raise


def test_close_unsupported_mode(adapter, mock_jxa):
    with pytest.raises(ValueError, match="complete, delete"):
        adapter.close_node("t1", "archive")


def test_close_complete_fallback_to_project(adapter, mock_jxa):
    """If task complete fails, try project complete."""
    fail = MagicMock(returncode=1, stdout="", stderr="not a task")
    ok = MagicMock(returncode=0, stdout="", stderr="")
    mock_jxa.side_effect = [fail, ok]
    adapter.close_node("p1", "complete")
    assert mock_jxa.call_count == 2


def test_close_complete_both_fail(adapter, mock_jxa):
    fail = MagicMock(returncode=1, stdout="", stderr="not found")
    mock_jxa.return_value = fail
    with pytest.raises(RuntimeError, match="Failed to complete"):
        adapter.close_node("x", "complete")


# --- create_node (topic/project) ---

def test_create_topic(adapter, mock_jxa):
    """Topics map to OmniFocus projects."""
    mock_jxa.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({"id": "proj1", "name": "Q3 Review"}),
        stderr="",
    )
    node = adapter.create_node("topic", {"title": "Q3 Review", "status": "active"})
    assert node["type"] == "topic"
    assert node["native_id"] == "proj1"


def test_create_unsupported_type(adapter, mock_jxa):
    with pytest.raises(ValueError, match="Unsupported type"):
        adapter.create_node("note", {"title": "Nope"})


# --- resolve ---

def test_resolve_task(adapter, mock_jxa):
    mock_jxa.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({
            "id": "t1", "name": "Task 1", "completed": False,
            "flagged": False, "inInbox": False, "tags": [],
            "note": "some notes", "deferDate": None, "dueDate": None,
            "containingProject": None,
        }),
        stderr="",
    )
    node = adapter.resolve("t1")
    assert node is not None
    assert node["native_id"] == "t1"


def test_resolve_project(adapter, mock_jxa):
    """If task resolve returns null, fall through to project."""
    task_result = MagicMock(returncode=0, stdout="null", stderr="")
    proj_result = MagicMock(
        returncode=0,
        stdout=json.dumps({"id": "p1", "name": "Project", "status": "active"}),
        stderr="",
    )
    mock_jxa.side_effect = [task_result, proj_result]
    node = adapter.resolve("p1")
    assert node is not None
    assert node["type"] == "topic"


def test_resolve_not_found(adapter, mock_jxa):
    mock_jxa.return_value = MagicMock(returncode=0, stdout="null", stderr="")
    node = adapter.resolve("nonexistent")
    assert node is None


# --- enumerate ---

def test_enumerate_with_pagination(adapter, mock_jxa):
    tasks = [
        {"id": f"t{i}", "name": f"Task {i}", "completed": False, "flagged": False, "inInbox": False, "tags": []}
        for i in range(5)
    ]
    mock_jxa.return_value = MagicMock(
        returncode=0, stdout=json.dumps(tasks), stderr=""
    )
    page = adapter.enumerate("task", limit=3, offset=0)
    assert len(page) == 3


def test_enumerate_with_offset(adapter, mock_jxa):
    tasks = [
        {"id": f"t{i}", "name": f"Task {i}", "completed": False, "flagged": False, "inInbox": False, "tags": []}
        for i in range(5)
    ]
    mock_jxa.return_value = MagicMock(
        returncode=0, stdout=json.dumps(tasks), stderr=""
    )
    page = adapter.enumerate("task", limit=3, offset=3)
    assert len(page) == 2  # only 2 left after offset 3


def test_enumerate_unsupported_type(adapter, mock_jxa):
    assert adapter.enumerate("note") == []


# --- supported_types ---

def test_supported_types(adapter):
    assert "task" in adapter.supported_types
    assert "topic" in adapter.supported_types
    assert "note" not in adapter.supported_types


# --- reverse_resolve ---

def test_reverse_resolve(adapter):
    assert adapter.reverse_resolve("pim://task/omnifocus/t1") == "t1"
    assert adapter.reverse_resolve("pim://task/internal/x") is None


# --- sync ---

def test_sync(adapter, mock_jxa):
    mock_jxa.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps([
            {"id": "t1", "name": "Changed", "completed": False, "flagged": False, "inInbox": False},
        ]),
        stderr="",
    )
    result = adapter.sync("2026-03-01T00:00:00Z")
    assert len(result["changed_nodes"]) == 1


# --- fetch_body ---

def test_fetch_body(adapter, mock_jxa):
    mock_jxa.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({
            "id": "t1", "name": "Task", "completed": False, "note": "Body text",
            "flagged": False, "inInbox": False, "tags": [],
            "deferDate": None, "dueDate": None, "containingProject": None,
        }),
        stderr="",
    )
    body = adapter.fetch_body("t1")
    assert body == "Body text"


# --- register mapping ---

def test_register_inbox_is_scratch(adapter):
    assert adapter._register_for_task({"inInbox": True, "completed": False}) == "scratch"


def test_register_completed_is_log(adapter):
    assert adapter._register_for_task({"completed": True, "inInbox": False}) == "log"


def test_register_active_is_working(adapter):
    assert adapter._register_for_task({"completed": False, "inInbox": False}) == "working"


def test_register_project_done_is_log(adapter):
    assert adapter._register_for_project({"status": "done"}) == "log"


def test_register_project_active_is_working(adapter):
    assert adapter._register_for_project({"status": "active"}) == "working"


# --- dispatch ---

def test_dispatch_raises(adapter):
    with pytest.raises(NotImplementedError):
        adapter.dispatch("t1", "some_method")


# --- edge stubs ---

def test_create_edge_returns_none(adapter):
    assert adapter.create_edge("a", "b", "belongs-to") is None


def test_query_edges_returns_empty(adapter):
    assert adapter.query_edges("a") == []
