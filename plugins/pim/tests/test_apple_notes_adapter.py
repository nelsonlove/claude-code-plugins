"""Tests for the Apple Notes adapter."""

import subprocess
from unittest.mock import patch, MagicMock
import pytest

from src.adapters.apple_notes import AppleNotesAdapter


@pytest.fixture
def adapter():
    return AppleNotesAdapter()


def make_result(stdout="", stderr="", returncode=0):
    r = MagicMock(spec=subprocess.CompletedProcess)
    r.stdout = stdout
    r.stderr = stderr
    r.returncode = returncode
    return r


# Sample AppleScript-like record output (JSON format for testing)
import json

SAMPLE_NOTES_JSON = json.dumps([
    {
        "id": "x-coredata://123/Note/p1",
        "name": "Meeting Notes",
        "body": "Discussed Q1 goals and timeline.",
        "folderName": "Work",
        "creationDate": "2026-03-10T10:00:00",
        "modificationDate": "2026-03-10T11:00:00",
    },
    {
        "id": "x-coredata://123/Note/p2",
        "name": "Shopping List",
        "body": "Milk, eggs, bread",
        "folderName": "Notes",
        "creationDate": "2026-03-09T08:00:00",
        "modificationDate": "2026-03-09T08:00:00",
    },
])

SAMPLE_SINGLE_NOTE = json.dumps([{
    "id": "x-coredata://123/Note/p1",
    "name": "Meeting Notes",
    "body": "Discussed Q1 goals and timeline.",
    "htmlBody": "<div>Discussed Q1 goals and timeline.</div>",
    "folderName": "Work",
    "creationDate": "2026-03-10T10:00:00",
    "modificationDate": "2026-03-10T11:00:00",
}])


# --- Health check ---

class TestHealthCheck:
    @patch.object(AppleNotesAdapter, "_run_osascript")
    def test_healthy(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout="Notes")
        assert adapter.health_check() is True

    @patch.object(AppleNotesAdapter, "_run_osascript")
    def test_unhealthy(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1)
        assert adapter.health_check() is False


# --- Node builder ---

class TestNodeBuilder:
    def test_note_to_node_structure(self, adapter):
        data = {
            "id": "x-coredata://123/Note/p1",
            "name": "Test Note",
            "body": "Content here",
            "folderName": "Work",
            "creationDate": "2026-03-10T10:00:00",
        }
        node = adapter._note_to_node(data)
        assert node["type"] == "note"
        assert node["adapter"] == "apple-notes"
        assert node["native_id"] == "x-coredata://123/Note/p1"
        assert node["attributes"]["title"] == "Test Note"
        assert node["body"] == "Content here"

    def test_note_register_work_folder(self, adapter):
        data = {"id": "x", "name": "T", "folderName": "Work"}
        node = adapter._note_to_node(data)
        assert node["register"] == "reference"

    def test_note_register_default_folder(self, adapter):
        data = {"id": "x", "name": "T", "folderName": "Notes"}
        node = adapter._note_to_node(data)
        assert node["register"] == "scratch"

    def test_note_register_empty_folder(self, adapter):
        data = {"id": "x", "name": "T", "folderName": ""}
        node = adapter._note_to_node(data)
        assert node["register"] == "scratch"

    def test_note_with_html_body(self, adapter):
        data = {"id": "x", "name": "T", "htmlBody": "<div>Rich</div>"}
        node = adapter._note_to_node(data)
        assert node["attributes"]["format"] == "richtext"

    def test_note_without_html_body(self, adapter):
        data = {"id": "x", "name": "T", "body": "Plain text"}
        node = adapter._note_to_node(data)
        assert node["attributes"]["format"] == "plaintext"


# --- Parsing ---

class TestParsing:
    def test_parse_json_list(self, adapter):
        records = adapter._parse_as_records(SAMPLE_NOTES_JSON)
        assert len(records) == 2
        assert records[0]["name"] == "Meeting Notes"

    def test_parse_empty(self, adapter):
        records = adapter._parse_as_records("")
        assert records == []

    def test_parse_applescript_records(self, adapter):
        output = '{id:"abc", |name|:"Title"}, {id:"def", |name|:"Other"}'
        records = adapter._parse_applescript_records(output)
        assert len(records) == 2
        assert records[0]["name"] == "Title"

    def test_split_as_fields(self, adapter):
        fields = adapter._split_as_fields('id:"abc", |name|:"Hello, World"')
        assert len(fields) == 2


# --- Resolve ---

class TestResolve:
    @patch.object(AppleNotesAdapter, "_run_osascript_json")
    def test_resolve_found(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_SINGLE_NOTE)
        node = adapter.resolve("x-coredata://123/Note/p1")
        assert node is not None
        assert node["attributes"]["title"] == "Meeting Notes"

    @patch.object(AppleNotesAdapter, "_run_osascript_json")
    def test_resolve_not_found(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1)
        node = adapter.resolve("nonexistent")
        assert node is None

    @patch.object(AppleNotesAdapter, "_run_osascript_json")
    def test_resolve_empty(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout="[]")
        node = adapter.resolve("x")
        assert node is None


# --- Reverse resolve ---

class TestReverseResolve:
    def test_valid_uri(self, adapter):
        result = adapter.reverse_resolve("pim://note/apple-notes/x-coredata://123")
        assert result == "x-coredata://123"

    def test_wrong_adapter(self, adapter):
        result = adapter.reverse_resolve("pim://note/internal/abc")
        assert result is None

    def test_malformed_uri(self, adapter):
        result = adapter.reverse_resolve("pim://note/apple-notes")
        assert result is None


# --- Enumerate ---

class TestEnumerate:
    @patch.object(AppleNotesAdapter, "_run_osascript_json")
    def test_enumerate_notes(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_NOTES_JSON)
        nodes = adapter.enumerate("note")
        assert len(nodes) == 2
        assert all(n["type"] == "note" for n in nodes)

    @patch.object(AppleNotesAdapter, "_run_osascript_json")
    def test_enumerate_wrong_type(self, mock_run, adapter):
        nodes = adapter.enumerate("task")
        assert nodes == []

    @patch.object(AppleNotesAdapter, "_run_osascript_json")
    def test_enumerate_with_offset(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_NOTES_JSON)
        nodes = adapter.enumerate("note", offset=1, limit=10)
        assert len(nodes) == 1

    @patch.object(AppleNotesAdapter, "_run_osascript_json")
    def test_enumerate_failure(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1)
        nodes = adapter.enumerate("note")
        assert nodes == []


# --- Create ---

class TestCreate:
    @patch.object(AppleNotesAdapter, "_run_osascript")
    def test_create_note(self, mock_run, adapter):
        mock_run.return_value = make_result(
            stdout=json.dumps([{"id": "new-note-id", "name": "New Note"}])
        )
        node = adapter.create_node("note", {"title": "New Note"}, body="Content")
        assert node["attributes"]["title"] == "New Note"
        assert node["body"] == "Content"

    @patch.object(AppleNotesAdapter, "_run_osascript")
    def test_create_note_in_folder(self, mock_run, adapter):
        mock_run.return_value = make_result(
            stdout=json.dumps([{"id": "x", "name": "Filed"}])
        )
        adapter.create_node("note", {"title": "Filed", "folder": "Work"})
        mock_run.assert_called_once()

    @patch.object(AppleNotesAdapter, "_run_osascript")
    def test_create_failure(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1, stderr="error")
        with pytest.raises(RuntimeError, match="Failed to create note"):
            adapter.create_node("note", {"title": "Fail"})

    def test_create_wrong_type(self, adapter):
        with pytest.raises(ValueError, match="Unsupported type"):
            adapter.create_node("task", {"title": "Not a note"})


# --- Query ---

class TestQuery:
    @patch.object(AppleNotesAdapter, "_run_osascript_json")
    def test_query_all(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_NOTES_JSON)
        nodes = adapter.query_nodes("note")
        assert len(nodes) == 2

    @patch.object(AppleNotesAdapter, "_run_osascript_json")
    def test_query_wrong_type(self, mock_run, adapter):
        nodes = adapter.query_nodes("task")
        assert nodes == []

    @patch.object(AppleNotesAdapter, "_run_osascript_json")
    def test_query_by_register(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_NOTES_JSON)
        nodes = adapter.query_nodes("note", {"register": "reference"})
        assert len(nodes) == 1
        assert nodes[0]["attributes"]["title"] == "Meeting Notes"

    @patch.object(AppleNotesAdapter, "_run_osascript_json")
    def test_query_text_search(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_NOTES_JSON)
        nodes = adapter.query_nodes("note", {"text_search": "goals"})
        mock_run.assert_called_once()

    @patch.object(AppleNotesAdapter, "_run_osascript_json")
    def test_query_with_attribute_filter(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_NOTES_JSON)
        nodes = adapter.query_nodes("note", {
            "attributes": {"title": "Shopping List"}
        })
        assert len(nodes) == 1

    @patch.object(AppleNotesAdapter, "_run_osascript_json")
    def test_query_with_limit(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_NOTES_JSON)
        nodes = adapter.query_nodes("note", {"limit": 1})
        assert len(nodes) == 1

    @patch.object(AppleNotesAdapter, "_run_osascript_json")
    def test_query_failure(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1)
        nodes = adapter.query_nodes("note")
        assert nodes == []


# --- Update ---

class TestUpdate:
    @patch.object(AppleNotesAdapter, "resolve")
    @patch.object(AppleNotesAdapter, "_run_osascript")
    def test_update_title(self, mock_run, mock_resolve, adapter):
        mock_run.return_value = make_result(stdout="")
        mock_resolve.return_value = adapter._note_to_node({
            "id": "x", "name": "Updated", "body": "Body"
        })
        node = adapter.update_node("x", {"attributes": {"title": "Updated"}})
        assert node["attributes"]["title"] == "Updated"

    @patch.object(AppleNotesAdapter, "_run_osascript")
    def test_update_failure(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1, stderr="error")
        with pytest.raises(RuntimeError, match="Failed to update note"):
            adapter.update_node("x", {"attributes": {"title": "Fail"}})

    @patch.object(AppleNotesAdapter, "resolve")
    @patch.object(AppleNotesAdapter, "_run_osascript")
    def test_update_resolve_fails(self, mock_run, mock_resolve, adapter):
        mock_run.return_value = make_result(stdout="")
        mock_resolve.return_value = None
        with pytest.raises(ValueError, match="Note not found"):
            adapter.update_node("x", {"attributes": {"title": "X"}})


# --- Close ---

class TestClose:
    @patch.object(AppleNotesAdapter, "_run_osascript")
    def test_close_delete(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout="")
        adapter.close_node("x", "delete")
        mock_run.assert_called_once()

    @patch.object(AppleNotesAdapter, "_run_osascript")
    def test_close_delete_failure(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1, stderr="error")
        with pytest.raises(RuntimeError, match="Failed to delete note"):
            adapter.close_node("x", "delete")

    def test_close_archive_noop(self, adapter):
        adapter.close_node("x", "archive")

    def test_close_complete_noop(self, adapter):
        adapter.close_node("x", "complete")

    def test_close_invalid_mode(self, adapter):
        with pytest.raises(ValueError, match="supports close modes"):
            adapter.close_node("x", "cancel")


# --- Sync ---

class TestSync:
    @patch.object(AppleNotesAdapter, "_run_osascript_json")
    def test_sync_returns_notes(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_NOTES_JSON)
        result = adapter.sync()
        assert len(result["changed_nodes"]) == 2

    @patch.object(AppleNotesAdapter, "_run_osascript_json")
    def test_sync_failure(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1)
        result = adapter.sync()
        assert result["changed_nodes"] == []


# --- Fetch body ---

class TestFetchBody:
    @patch.object(AppleNotesAdapter, "resolve")
    def test_fetch_body(self, mock_resolve, adapter):
        mock_resolve.return_value = adapter._note_to_node({
            "id": "x", "name": "Test", "body": "Content"
        })
        body = adapter.fetch_body("x")
        assert body == "Content"

    @patch.object(AppleNotesAdapter, "resolve")
    def test_fetch_body_not_found(self, mock_resolve, adapter):
        mock_resolve.return_value = None
        body = adapter.fetch_body("nonexistent")
        assert body is None
