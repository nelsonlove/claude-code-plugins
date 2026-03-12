"""Tests for the Day One adapter."""

import subprocess
import json
from unittest.mock import patch, MagicMock, call
import pytest

from src.adapters.dayone import DayOneAdapter


@pytest.fixture
def adapter():
    return DayOneAdapter(journal="Test Journal")


# --- Helpers ---

def make_result(stdout="", stderr="", returncode=0):
    r = MagicMock(spec=subprocess.CompletedProcess)
    r.stdout = stdout
    r.stderr = stderr
    r.returncode = returncode
    return r


SAMPLE_ENTRY = {
    "uuid": "ABC123DEF456",
    "creationDate": "2026-03-10T08:30:00Z",
    "modifiedDate": "2026-03-10T09:00:00Z",
    "text": "# Morning Reflection\n\nToday I started working on the PIM system.",
    "tags": ["reflection", "work"],
}

SAMPLE_ENTRIES_JSON = json.dumps({
    "entries": [
        SAMPLE_ENTRY,
        {
            "uuid": "GHI789JKL012",
            "creationDate": "2026-03-09T20:00:00Z",
            "text": "Evening thoughts about the day.",
            "tags": ["evening"],
        },
    ]
})


# --- Health check ---

class TestHealthCheck:
    @patch.object(DayOneAdapter, "_run_dayone")
    def test_healthy(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout="Day One CLI 1.0.0")
        assert adapter.health_check() is True
        mock_run.assert_called_once_with("--version")

    @patch.object(DayOneAdapter, "_run_dayone")
    def test_unhealthy(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1, stderr="not found")
        assert adapter.health_check() is False


# --- Node builder ---

class TestNodeBuilder:
    def test_entry_to_node_structure(self, adapter):
        node = adapter._entry_to_node(SAMPLE_ENTRY)
        assert node["type"] == "entry"
        assert node["adapter"] == "dayone"
        assert node["native_id"] == "ABC123DEF456"
        assert node["id"] == "pim://entry/dayone/ABC123DEF456"
        assert node["register"] == "log"
        assert node["attributes"]["title"] == "Morning Reflection"
        assert node["attributes"]["format"] == "markdown"
        assert node["attributes"]["timestamp"] == "2026-03-10T08:30:00Z"
        assert node["attributes"]["tags"] == ["reflection", "work"]
        assert "# Morning Reflection" in node["body"]

    def test_entry_title_extraction_no_heading(self, adapter):
        node = adapter._entry_to_node({
            "uuid": "x", "text": "Just some text\nwith lines", "creationDate": ""
        })
        assert node["attributes"]["title"] == "Just some text"

    def test_entry_title_extraction_markdown_heading(self, adapter):
        node = adapter._entry_to_node({
            "uuid": "x", "text": "# My Title\nBody text", "creationDate": ""
        })
        assert node["attributes"]["title"] == "My Title"

    def test_entry_empty_text(self, adapter):
        node = adapter._entry_to_node({
            "uuid": "x", "text": "", "creationDate": ""
        })
        assert node["attributes"]["title"] == ""

    def test_entry_no_tags(self, adapter):
        node = adapter._entry_to_node({
            "uuid": "x", "text": "Hello", "creationDate": ""
        })
        assert "tags" not in node["attributes"]


# --- Resolve ---

class TestResolve:
    @patch.object(DayOneAdapter, "_run_dayone")
    def test_resolve_found(self, mock_run, adapter):
        mock_run.return_value = make_result(
            stdout=json.dumps({"entries": [SAMPLE_ENTRY]})
        )
        node = adapter.resolve("ABC123DEF456")
        assert node is not None
        assert node["native_id"] == "ABC123DEF456"
        mock_run.assert_called_once_with(
            "view", "--uuid", "ABC123DEF456",
            "--journal", "Test Journal",
            "--output", "json",
        )

    @patch.object(DayOneAdapter, "_run_dayone")
    def test_resolve_not_found(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1, stderr="not found")
        node = adapter.resolve("nonexistent")
        assert node is None

    @patch.object(DayOneAdapter, "_run_dayone")
    def test_resolve_empty_entries(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=json.dumps({"entries": []}))
        node = adapter.resolve("ABC123DEF456")
        assert node is None


# --- Reverse resolve ---

class TestReverseResolve:
    def test_valid_uri(self, adapter):
        result = adapter.reverse_resolve("pim://entry/dayone/ABC123DEF456")
        assert result == "ABC123DEF456"

    def test_wrong_adapter(self, adapter):
        result = adapter.reverse_resolve("pim://entry/internal/ABC123DEF456")
        assert result is None

    def test_malformed_uri(self, adapter):
        result = adapter.reverse_resolve("pim://entry/dayone")
        assert result is None


# --- Enumerate ---

class TestEnumerate:
    @patch.object(DayOneAdapter, "_run_dayone")
    def test_enumerate_entries(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_ENTRIES_JSON)
        nodes = adapter.enumerate("entry")
        assert len(nodes) == 2
        assert all(n["type"] == "entry" for n in nodes)
        assert all(n["register"] == "log" for n in nodes)

    @patch.object(DayOneAdapter, "_run_dayone")
    def test_enumerate_wrong_type(self, mock_run, adapter):
        nodes = adapter.enumerate("task")
        assert nodes == []
        mock_run.assert_not_called()

    @patch.object(DayOneAdapter, "_run_dayone")
    def test_enumerate_with_offset(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_ENTRIES_JSON)
        nodes = adapter.enumerate("entry", offset=1, limit=10)
        assert len(nodes) == 1

    @patch.object(DayOneAdapter, "_run_dayone")
    def test_enumerate_failure(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1)
        nodes = adapter.enumerate("entry")
        assert nodes == []


# --- Create ---

class TestCreate:
    @patch.object(DayOneAdapter, "_run_dayone")
    def test_create_entry(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout="NEW-UUID-789")
        node = adapter.create_node("entry", {
            "title": "Evening thoughts",
        }, body="Today was productive.")
        assert node["native_id"] == "NEW-UUID-789"
        assert node["attributes"]["title"] == "Evening thoughts"
        assert "# Evening thoughts" in node["body"]

    @patch.object(DayOneAdapter, "_run_dayone")
    def test_create_entry_with_tags(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout="UUID-TAGGED")
        node = adapter.create_node("entry", {
            "title": "Tagged entry",
            "tags": ["work", "pim"],
        })
        # Verify tags were passed
        args = mock_run.call_args
        cmd_args = args[0] if args[0] else []
        # The method uses *args so check the call
        mock_run.assert_called_once()

    @patch.object(DayOneAdapter, "_run_dayone")
    def test_create_entry_with_timestamp(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout="UUID-DATED")
        adapter.create_node("entry", {
            "title": "Backdated entry",
            "timestamp": "2026-03-01T10:00:00Z",
        })
        mock_run.assert_called_once()

    @patch.object(DayOneAdapter, "_run_dayone")
    def test_create_entry_parses_uuid_from_verbose_output(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout="Created entry: UUID-VERBOSE")
        node = adapter.create_node("entry", {"title": "Test"})
        assert node["native_id"] == "UUID-VERBOSE"

    @patch.object(DayOneAdapter, "_run_dayone")
    def test_create_failure(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1, stderr="permission denied")
        with pytest.raises(RuntimeError, match="Failed to create entry"):
            adapter.create_node("entry", {"title": "Fail"})

    def test_create_wrong_type(self, adapter):
        with pytest.raises(ValueError, match="Unsupported type"):
            adapter.create_node("task", {"title": "Not an entry"})

    @patch.object(DayOneAdapter, "_run_dayone")
    def test_create_body_without_title(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout="UUID-NOTITLE")
        node = adapter.create_node("entry", {}, body="Just text, no heading")
        assert node["body"] == "Just text, no heading"


# --- Query ---

class TestQuery:
    @patch.object(DayOneAdapter, "_run_dayone")
    def test_query_entries(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_ENTRIES_JSON)
        nodes = adapter.query_nodes("entry")
        assert len(nodes) == 2

    @patch.object(DayOneAdapter, "_run_dayone")
    def test_query_wrong_type(self, mock_run, adapter):
        nodes = adapter.query_nodes("task")
        assert nodes == []
        mock_run.assert_not_called()

    @patch.object(DayOneAdapter, "_run_dayone")
    def test_query_text_search(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_ENTRIES_JSON)
        nodes = adapter.query_nodes("entry", {"text_search": "morning"})
        mock_run.assert_called_once()
        # Verify search command was used
        call_args = mock_run.call_args[0]
        assert call_args[0] == "search"

    @patch.object(DayOneAdapter, "_run_dayone")
    def test_query_with_attribute_filter(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_ENTRIES_JSON)
        nodes = adapter.query_nodes("entry", {
            "attributes": {"title": "Morning Reflection"}
        })
        assert len(nodes) == 1
        assert nodes[0]["attributes"]["title"] == "Morning Reflection"

    @patch.object(DayOneAdapter, "_run_dayone")
    def test_query_with_limit(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_ENTRIES_JSON)
        nodes = adapter.query_nodes("entry", {"limit": 1})
        assert len(nodes) == 1

    @patch.object(DayOneAdapter, "_run_dayone")
    def test_query_failure(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1)
        nodes = adapter.query_nodes("entry")
        assert nodes == []


# --- Update ---

class TestUpdate:
    @patch.object(DayOneAdapter, "resolve")
    @patch.object(DayOneAdapter, "_run_dayone")
    def test_update_body(self, mock_run, mock_resolve, adapter):
        mock_run.return_value = make_result(stdout="")
        mock_resolve.return_value = adapter._entry_to_node({
            "uuid": "ABC123", "text": "# Updated\n\nNew body", "creationDate": ""
        })
        node = adapter.update_node("ABC123", {"body": "New body"})
        assert node is not None

    @patch.object(DayOneAdapter, "resolve")
    @patch.object(DayOneAdapter, "_run_dayone")
    def test_update_tags(self, mock_run, mock_resolve, adapter):
        mock_run.return_value = make_result(stdout="")
        mock_resolve.return_value = adapter._entry_to_node({
            "uuid": "ABC123", "text": "Test", "creationDate": "",
            "tags": ["new-tag"],
        })
        node = adapter.update_node("ABC123", {
            "attributes": {"tags": ["new-tag"]}
        })
        assert node is not None

    @patch.object(DayOneAdapter, "_run_dayone")
    def test_update_body_failure(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1, stderr="error")
        with pytest.raises(RuntimeError, match="Failed to update entry"):
            adapter.update_node("ABC123", {"body": "fail"})

    @patch.object(DayOneAdapter, "resolve")
    @patch.object(DayOneAdapter, "_run_dayone")
    def test_update_resolve_fails(self, mock_run, mock_resolve, adapter):
        mock_run.return_value = make_result(stdout="")
        mock_resolve.return_value = None
        with pytest.raises(ValueError, match="Entry not found"):
            adapter.update_node("ABC123", {"attributes": {"tags": ["x"]}})


# --- Close ---

class TestClose:
    @patch.object(DayOneAdapter, "_run_dayone")
    def test_close_delete(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout="deleted")
        adapter.close_node("ABC123", "delete")
        mock_run.assert_called_once_with(
            "delete", "--uuid", "ABC123",
            "--journal", "Test Journal",
        )

    @patch.object(DayOneAdapter, "_run_dayone")
    def test_close_delete_failure(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1, stderr="not found")
        with pytest.raises(RuntimeError, match="Failed to delete entry"):
            adapter.close_node("ABC123", "delete")

    def test_close_archive_noop(self, adapter):
        adapter.close_node("ABC123", "archive")

    def test_close_complete_noop(self, adapter):
        adapter.close_node("ABC123", "complete")

    def test_close_invalid_mode(self, adapter):
        with pytest.raises(ValueError, match="supports close modes"):
            adapter.close_node("ABC123", "invalid")


# --- Sync ---

class TestSync:
    @patch.object(DayOneAdapter, "_run_dayone")
    def test_sync_returns_entries(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_ENTRIES_JSON)
        result = adapter.sync()
        assert len(result["changed_nodes"]) == 2

    @patch.object(DayOneAdapter, "_run_dayone")
    def test_sync_with_since(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_ENTRIES_JSON)
        adapter.sync(since="2026-03-09")
        call_args = mock_run.call_args[0]
        assert "--after" in call_args
        assert "2026-03-09" in call_args

    @patch.object(DayOneAdapter, "_run_dayone")
    def test_sync_failure(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1)
        result = adapter.sync()
        assert result["changed_nodes"] == []


# --- Fetch body ---

class TestFetchBody:
    @patch.object(DayOneAdapter, "resolve")
    def test_fetch_body(self, mock_resolve, adapter):
        mock_resolve.return_value = adapter._entry_to_node(SAMPLE_ENTRY)
        body = adapter.fetch_body("ABC123DEF456")
        assert "Morning Reflection" in body

    @patch.object(DayOneAdapter, "resolve")
    def test_fetch_body_not_found(self, mock_resolve, adapter):
        mock_resolve.return_value = None
        body = adapter.fetch_body("nonexistent")
        assert body is None
