"""Tests for the Himalaya adapter — all subprocess calls are mocked."""

import json
import pytest
from unittest.mock import patch, MagicMock

from src.adapters.himalaya import HimalayaAdapter


@pytest.fixture
def adapter():
    return HimalayaAdapter()


@pytest.fixture
def mock_himalaya():
    with patch("src.adapters.himalaya.subprocess.run") as mock_run:
        yield mock_run


# --- health_check ---

def test_health_check_success(adapter, mock_himalaya):
    mock_himalaya.return_value = MagicMock(returncode=0, stdout="account1", stderr="")
    assert adapter.health_check() is True


def test_health_check_failure(adapter, mock_himalaya):
    mock_himalaya.return_value = MagicMock(returncode=1, stdout="", stderr="error")
    assert adapter.health_check() is False


# --- query_nodes ---

def test_query_messages(adapter, mock_himalaya):
    mock_himalaya.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps([
            {"id": "1", "subject": "Hello", "from": {"name": "Alice", "addr": "alice@test.com"}, "date": "2026-03-12"},
            {"id": "2", "subject": "Re: Hello", "from": {"name": "Bob", "addr": "bob@test.com"}, "date": "2026-03-12"},
        ]),
        stderr="",
    )
    messages = adapter.query_nodes("message")
    assert len(messages) == 2
    assert messages[0]["attributes"]["subject"] == "Hello"


def test_query_messages_with_folder(adapter, mock_himalaya):
    mock_himalaya.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps([
            {"id": "5", "subject": "Archived", "from": {"name": "X", "addr": "x@y.com"}, "date": "2026-01-01"},
        ]),
        stderr="",
    )
    messages = adapter.query_nodes("message", {"folder": "Archive"})
    assert len(messages) == 1
    # Archive maps to log register
    assert messages[0]["register"] == "log"


def test_query_messages_with_search(adapter, mock_himalaya):
    mock_himalaya.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps([
            {"id": "3", "subject": "Meeting", "from": {"name": "C", "addr": "c@d.com"}, "date": "2026-02-15"},
        ]),
        stderr="",
    )
    messages = adapter.query_nodes("message", {"text_search": "meeting"})
    assert len(messages) == 1
    # Verify himalaya search was called
    call_args = mock_himalaya.call_args[0][0]
    assert "search" in call_args


def test_query_unsupported_type(adapter, mock_himalaya):
    assert adapter.query_nodes("task") == []


# --- fetch_body ---

def test_fetch_body(adapter, mock_himalaya):
    mock_himalaya.return_value = MagicMock(
        returncode=0,
        stdout="This is the email body content.",
        stderr="",
    )
    body = adapter.fetch_body("1")
    assert "email body" in body


def test_fetch_body_not_found(adapter, mock_himalaya):
    mock_himalaya.return_value = MagicMock(returncode=1, stdout="", stderr="not found")
    body = adapter.fetch_body("999")
    assert body is None


# --- create_node ---

def test_create_message_sends(adapter, mock_himalaya):
    mock_himalaya.return_value = MagicMock(returncode=0, stdout="", stderr="")
    node = adapter.create_node("message", {
        "subject": "Test",
        "to": "bob@test.com",
        "direction": "outbound",
    }, body="Hello world")
    assert mock_himalaya.called
    assert node["type"] == "message"
    assert node["attributes"]["subject"] == "Test"
    assert node["attributes"]["direction"] == "outbound"


def test_create_message_with_from(adapter, mock_himalaya):
    mock_himalaya.return_value = MagicMock(returncode=0, stdout="", stderr="")
    node = adapter.create_node("message", {
        "subject": "From test",
        "to": "bob@test.com",
        "from": "alice@test.com",
    }, body="Hi")
    # Verify the composed message includes From header
    call_kwargs = mock_himalaya.call_args
    stdin = call_kwargs.kwargs.get("input") or call_kwargs[1].get("input", "")
    assert "alice@test.com" in stdin


def test_create_unsupported_type(adapter, mock_himalaya):
    with pytest.raises(ValueError, match="Unsupported type"):
        adapter.create_node("task", {"title": "Nope"})


def test_create_message_failure(adapter, mock_himalaya):
    mock_himalaya.return_value = MagicMock(returncode=1, stdout="", stderr="SMTP error")
    with pytest.raises(RuntimeError, match="Failed to send"):
        adapter.create_node("message", {"subject": "Fail"}, body="x")


# --- resolve ---

def test_resolve_message(adapter, mock_himalaya):
    mock_himalaya.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({"id": "42", "subject": "Test", "from": {"name": "A", "addr": "a@b.com"}, "date": "2026-03-12"}),
        stderr="",
    )
    node = adapter.resolve("42")
    assert node is not None
    assert node["native_id"] == "42"


def test_resolve_not_found(adapter, mock_himalaya):
    mock_himalaya.return_value = MagicMock(returncode=1, stdout="", stderr="not found")
    assert adapter.resolve("999") is None


# --- supported_types ---

def test_supported_types(adapter):
    assert "message" in adapter.supported_types
    assert "task" not in adapter.supported_types


# --- dispatch ---

def test_dispatch_send(adapter, mock_himalaya):
    mock_himalaya.return_value = MagicMock(returncode=0, stdout="", stderr="")
    result = adapter.dispatch("42", "send", {"body": "test message"})
    assert result["status"] == "sent"


def test_dispatch_unsupported_method(adapter, mock_himalaya):
    with pytest.raises(NotImplementedError):
        adapter.dispatch("42", "unsupported_method")


# --- close_node ---

def test_close_delete(adapter, mock_himalaya):
    mock_himalaya.return_value = MagicMock(returncode=0, stdout="", stderr="")
    adapter.close_node("1", "delete")
    call_args = mock_himalaya.call_args[0][0]
    assert "delete" in call_args


def test_close_archive(adapter, mock_himalaya):
    mock_himalaya.return_value = MagicMock(returncode=0, stdout="", stderr="")
    adapter.close_node("1", "archive")
    call_args = mock_himalaya.call_args[0][0]
    assert "move" in call_args
    assert "Archive" in call_args


def test_close_unsupported_mode(adapter, mock_himalaya):
    with pytest.raises(ValueError, match="delete, archive"):
        adapter.close_node("1", "complete")


def test_close_delete_failure(adapter, mock_himalaya):
    mock_himalaya.return_value = MagicMock(returncode=1, stdout="", stderr="err")
    with pytest.raises(RuntimeError, match="Failed to delete"):
        adapter.close_node("1", "delete")


# --- enumerate ---

def test_enumerate_messages(adapter, mock_himalaya):
    msgs = [
        {"id": str(i), "subject": f"Msg {i}", "from": {"name": "X", "addr": "x@y.com"}, "date": "2026-03-12"}
        for i in range(5)
    ]
    mock_himalaya.return_value = MagicMock(
        returncode=0, stdout=json.dumps(msgs), stderr=""
    )
    page = adapter.enumerate("message", limit=3)
    assert len(page) == 5  # himalaya does its own pagination; we pass page-size
    # Default folder is INBOX → scratch register
    assert all(m["register"] == "scratch" for m in page)
    # Verify --folder INBOX was passed to himalaya
    call_args = mock_himalaya.call_args[0][0]
    assert "--folder" in call_args
    assert "INBOX" in call_args


def test_enumerate_messages_with_folder(adapter, mock_himalaya):
    msgs = [
        {"id": "1", "subject": "Archived", "from": {"name": "X", "addr": "x@y.com"}, "date": "2026-03-12"}
    ]
    mock_himalaya.return_value = MagicMock(
        returncode=0, stdout=json.dumps(msgs), stderr=""
    )
    page = adapter.enumerate("message", filters={"folder": "Archive"}, limit=10)
    assert len(page) == 1
    assert page[0]["register"] == "log"


def test_enumerate_unsupported_type(adapter, mock_himalaya):
    assert adapter.enumerate("task") == []


# --- reverse_resolve ---

def test_reverse_resolve(adapter):
    assert adapter.reverse_resolve("pim://message/himalaya/42") == "42"
    assert adapter.reverse_resolve("pim://task/internal/x") is None


# --- sync ---

def test_sync(adapter, mock_himalaya):
    mock_himalaya.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps([
            {"id": "1", "subject": "New", "from": {"name": "A", "addr": "a@b.com"}, "date": "2026-03-12"},
        ]),
        stderr="",
    )
    result = adapter.sync()
    assert len(result["changed_nodes"]) == 1
    # Sync pulls from INBOX → scratch register
    assert result["changed_nodes"][0]["register"] == "scratch"


# --- register mapping ---

def test_register_inbox_is_scratch(adapter):
    assert adapter._register_for_folder("INBOX") == "scratch"
    assert adapter._register_for_folder("inbox") == "scratch"
    assert adapter._register_for_folder(None) == "scratch"


def test_register_sent_is_log(adapter):
    assert adapter._register_for_folder("Sent") == "log"
    assert adapter._register_for_folder("Archive") == "log"


def test_register_custom_folder_is_working(adapter):
    assert adapter._register_for_folder("Projects") == "working"
    assert adapter._register_for_folder("Work") == "working"


# --- update_node ---

def test_update_node_move_folder(adapter, mock_himalaya):
    # First call: move; second call: re-read
    move_result = MagicMock(returncode=0, stdout="", stderr="")
    read_result = MagicMock(
        returncode=0,
        stdout=json.dumps({"id": "1", "subject": "Moved", "from": {"name": "A", "addr": "a@b.com"}, "date": "2026-03-12"}),
        stderr="",
    )
    mock_himalaya.side_effect = [move_result, read_result]
    node = adapter.update_node("1", {"folder": "Work"})
    assert node["native_id"] == "1"
    # "Work" is a custom folder → working register
    assert node["register"] == "working"


def test_update_node_move_by_register(adapter, mock_himalaya):
    move_result = MagicMock(returncode=0, stdout="", stderr="")
    read_result = MagicMock(
        returncode=0,
        stdout=json.dumps({"id": "2", "subject": "Test", "from": {"name": "B", "addr": "b@c.com"}, "date": "2026-03-12"}),
        stderr="",
    )
    mock_himalaya.side_effect = [move_result, read_result]
    node = adapter.update_node("2", {"register": "log"})
    assert node is not None
    # register=log maps to Archive folder → log register
    assert node["register"] == "log"


# --- adapter_id ---

def test_adapter_id(adapter):
    assert adapter.adapter_id == "himalaya"
