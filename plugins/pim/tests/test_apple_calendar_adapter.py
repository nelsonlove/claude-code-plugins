"""Tests for the Apple Calendar adapter."""

import subprocess
from unittest.mock import patch, MagicMock
import pytest

from src.adapters.apple_calendar import AppleCalendarAdapter


@pytest.fixture
def adapter():
    return AppleCalendarAdapter(calendar_name="Test Calendar")


# --- Helpers ---

def make_result(stdout="", stderr="", returncode=0):
    r = MagicMock(spec=subprocess.CompletedProcess)
    r.stdout = stdout
    r.stderr = stderr
    r.returncode = returncode
    return r


SAMPLE_ICALBUDDY_OUTPUT = """\
Team Standup
    location: Zoom
    notes: Daily standup
    uid: abc-123
    datetime: Jan 15, 2026 at 10:00 - 10:30
Sprint Planning
    location: Conference Room A
    uid: def-456
    datetime: Jan 16, 2026 at 14:00 - 15:00"""


SAMPLE_SINGLE_EVENT = """\
Team Standup
    location: Zoom
    notes: Daily standup
    uid: abc-123
    datetime: Jan 15, 2026 at 10:00 - 10:30"""


# --- Health check ---

class TestHealthCheck:
    @patch.object(AppleCalendarAdapter, "_run_icalbuddy")
    def test_healthy(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout="icalBuddy version 1.10")
        assert adapter.health_check() is True
        mock_run.assert_called_once_with("-V")

    @patch.object(AppleCalendarAdapter, "_run_icalbuddy")
    def test_unhealthy(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1, stderr="not found")
        assert adapter.health_check() is False


# --- Parsing ---

class TestParsing:
    def test_parse_multiple_events(self, adapter):
        events = adapter._parse_icalbuddy_events(SAMPLE_ICALBUDDY_OUTPUT)
        assert len(events) == 2
        assert events[0]["title"] == "Team Standup"
        assert events[0]["location"] == "Zoom"
        assert events[0]["uid"] == "abc-123"
        assert events[1]["title"] == "Sprint Planning"
        assert events[1]["uid"] == "def-456"

    def test_parse_single_event(self, adapter):
        events = adapter._parse_icalbuddy_events(SAMPLE_SINGLE_EVENT)
        assert len(events) == 1
        assert events[0]["notes"] == "Daily standup"

    def test_parse_empty_output(self, adapter):
        events = adapter._parse_icalbuddy_events("")
        assert events == []

    def test_parse_event_block_no_title(self, adapter):
        result = adapter._parse_event_block("")
        assert result is None


# --- Node builder ---

class TestNodeBuilder:
    def test_event_to_node_structure(self, adapter):
        data = {
            "uid": "abc-123",
            "title": "Meeting",
            "start": "2026-01-15T10:00:00",
            "end": "2026-01-15T11:00:00",
            "location": "Office",
            "notes": "Agenda items",
            "status": "confirmed",
        }
        node = adapter._event_to_node(data)
        assert node["type"] == "event"
        assert node["adapter"] == "apple-calendar"
        assert node["native_id"] == "abc-123"
        assert node["id"] == "pim://event/apple-calendar/abc-123"
        assert node["attributes"]["title"] == "Meeting"
        assert node["attributes"]["location"] == "Office"
        assert node["attributes"]["start"] == "2026-01-15T10:00:00"
        assert node["body"] == "Agenda items"

    def test_event_register_future(self, adapter):
        data = {"uid": "x", "title": "Future", "start": "2030-01-01T10:00:00"}
        node = adapter._event_to_node(data)
        assert node["register"] == "working"

    def test_event_register_past(self, adapter):
        data = {"uid": "x", "title": "Past", "start": "2020-01-01T10:00:00"}
        node = adapter._event_to_node(data)
        assert node["register"] == "log"

    def test_event_register_no_start(self, adapter):
        data = {"uid": "x", "title": "No date"}
        node = adapter._event_to_node(data)
        assert node["register"] == "working"


# --- Resolve ---

class TestResolve:
    @patch.object(AppleCalendarAdapter, "_run_icalbuddy")
    def test_resolve_found(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_SINGLE_EVENT)
        node = adapter.resolve("abc-123")
        assert node is not None
        assert node["native_id"] == "abc-123"
        assert node["type"] == "event"

    @patch.object(AppleCalendarAdapter, "_run_icalbuddy")
    def test_resolve_not_found(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1)
        node = adapter.resolve("nonexistent")
        assert node is None

    @patch.object(AppleCalendarAdapter, "_run_icalbuddy")
    def test_resolve_empty_output(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout="")
        node = adapter.resolve("abc-123")
        assert node is None


# --- Reverse resolve ---

class TestReverseResolve:
    def test_valid_uri(self, adapter):
        result = adapter.reverse_resolve("pim://event/apple-calendar/abc-123")
        assert result == "abc-123"

    def test_wrong_adapter(self, adapter):
        result = adapter.reverse_resolve("pim://event/omnifocus/abc-123")
        assert result is None

    def test_malformed_uri(self, adapter):
        result = adapter.reverse_resolve("pim://event/apple-calendar")
        assert result is None


# --- Enumerate ---

class TestEnumerate:
    @patch.object(AppleCalendarAdapter, "_run_icalbuddy")
    def test_enumerate_events(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_ICALBUDDY_OUTPUT)
        nodes = adapter.enumerate("event")
        assert len(nodes) == 2
        assert all(n["type"] == "event" for n in nodes)

    @patch.object(AppleCalendarAdapter, "_run_icalbuddy")
    def test_enumerate_wrong_type(self, mock_run, adapter):
        nodes = adapter.enumerate("task")
        assert nodes == []
        mock_run.assert_not_called()

    @patch.object(AppleCalendarAdapter, "_run_icalbuddy")
    def test_enumerate_with_offset(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_ICALBUDDY_OUTPUT)
        nodes = adapter.enumerate("event", offset=1, limit=10)
        assert len(nodes) == 1

    @patch.object(AppleCalendarAdapter, "_run_icalbuddy")
    def test_enumerate_cli_failure(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1)
        nodes = adapter.enumerate("event")
        assert nodes == []


# --- Create ---

class TestCreate:
    @patch.object(AppleCalendarAdapter, "_run_osascript")
    def test_create_event(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout="new-uid-789")
        node = adapter.create_node("event", {
            "title": "New Meeting",
            "start": "2026-03-15T10:00:00",
            "end": "2026-03-15T11:00:00",
            "location": "Board Room",
        }, body="Discussion items")
        assert node["native_id"] == "new-uid-789"
        assert node["attributes"]["title"] == "New Meeting"
        assert node["body"] == "Discussion items"

    @patch.object(AppleCalendarAdapter, "_run_osascript")
    def test_create_event_default_end(self, mock_run, adapter):
        """When no end time, defaults to 1 hour after start."""
        mock_run.return_value = make_result(stdout="uid-auto-end")
        node = adapter.create_node("event", {
            "title": "Quick sync",
            "start": "2026-03-15T10:00:00",
        })
        assert node["native_id"] == "uid-auto-end"
        # Verify osascript was called
        mock_run.assert_called_once()

    @patch.object(AppleCalendarAdapter, "_run_osascript")
    def test_create_failure(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1, stderr="permission denied")
        with pytest.raises(RuntimeError, match="Failed to create event"):
            adapter.create_node("event", {"title": "Fail"})

    def test_create_wrong_type(self, adapter):
        with pytest.raises(ValueError, match="Unsupported type"):
            adapter.create_node("task", {"title": "Not an event"})


# --- Query ---

class TestQuery:
    @patch.object(AppleCalendarAdapter, "_run_icalbuddy")
    def test_query_upcoming(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_ICALBUDDY_OUTPUT)
        nodes = adapter.query_nodes("event")
        assert len(nodes) == 2

    @patch.object(AppleCalendarAdapter, "_run_icalbuddy")
    def test_query_wrong_type(self, mock_run, adapter):
        nodes = adapter.query_nodes("task")
        assert nodes == []
        mock_run.assert_not_called()

    @patch.object(AppleCalendarAdapter, "_run_icalbuddy")
    def test_query_with_text_search(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_ICALBUDDY_OUTPUT)
        nodes = adapter.query_nodes("event", {"text_search": "standup"})
        assert len(nodes) == 1
        assert nodes[0]["attributes"]["title"] == "Team Standup"

    @patch.object(AppleCalendarAdapter, "_run_icalbuddy")
    def test_query_with_attribute_filter(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_ICALBUDDY_OUTPUT)
        nodes = adapter.query_nodes("event", {
            "attributes": {"title": "Sprint Planning"}
        })
        assert len(nodes) == 1
        assert nodes[0]["attributes"]["title"] == "Sprint Planning"

    @patch.object(AppleCalendarAdapter, "_run_icalbuddy")
    def test_query_with_limit(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_ICALBUDDY_OUTPUT)
        nodes = adapter.query_nodes("event", {"limit": 1})
        assert len(nodes) == 1

    @patch.object(AppleCalendarAdapter, "_run_icalbuddy")
    def test_query_failure(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1)
        nodes = adapter.query_nodes("event")
        assert nodes == []


# --- Update ---

class TestUpdate:
    @patch.object(AppleCalendarAdapter, "resolve")
    @patch.object(AppleCalendarAdapter, "_run_osascript")
    def test_update_title(self, mock_run, mock_resolve, adapter):
        mock_run.return_value = make_result(stdout="abc-123")
        mock_resolve.return_value = adapter._event_to_node({
            "uid": "abc-123", "title": "Updated Title", "status": "confirmed"
        })
        node = adapter.update_node("abc-123", {
            "attributes": {"title": "Updated Title"}
        })
        assert node["attributes"]["title"] == "Updated Title"

    @patch.object(AppleCalendarAdapter, "_run_osascript")
    def test_update_failure(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1, stderr="error")
        with pytest.raises(RuntimeError, match="Failed to update event"):
            adapter.update_node("abc-123", {"attributes": {"title": "X"}})

    @patch.object(AppleCalendarAdapter, "resolve")
    @patch.object(AppleCalendarAdapter, "_run_osascript")
    def test_update_resolve_fails(self, mock_run, mock_resolve, adapter):
        mock_run.return_value = make_result(stdout="abc-123")
        mock_resolve.return_value = None
        with pytest.raises(ValueError, match="Event not found"):
            adapter.update_node("abc-123", {"attributes": {"title": "X"}})


# --- Close ---

class TestClose:
    @patch.object(AppleCalendarAdapter, "_run_osascript")
    def test_close_delete(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout="deleted")
        adapter.close_node("abc-123", "delete")
        mock_run.assert_called_once()

    @patch.object(AppleCalendarAdapter, "_run_osascript")
    def test_close_delete_failure(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1, stderr="not found")
        with pytest.raises(RuntimeError, match="Failed to delete event"):
            adapter.close_node("abc-123", "delete")

    @patch.object(AppleCalendarAdapter, "update_node")
    def test_close_cancel(self, mock_update, adapter):
        mock_update.return_value = adapter._event_to_node({
            "uid": "abc-123", "title": "Cancelled", "status": "cancelled"
        })
        adapter.close_node("abc-123", "cancel")
        mock_update.assert_called_once_with("abc-123", {
            "attributes": {"status": "cancelled"}
        })

    def test_close_archive_noop(self, adapter):
        # Archive is a no-op for events
        adapter.close_node("abc-123", "archive")

    def test_close_complete_noop(self, adapter):
        adapter.close_node("abc-123", "complete")

    def test_close_invalid_mode(self, adapter):
        with pytest.raises(ValueError, match="supports close modes"):
            adapter.close_node("abc-123", "invalid")


# --- Sync ---

class TestSync:
    @patch.object(AppleCalendarAdapter, "_run_icalbuddy")
    def test_sync_returns_events(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_ICALBUDDY_OUTPUT)
        result = adapter.sync()
        assert len(result["changed_nodes"]) == 2

    @patch.object(AppleCalendarAdapter, "_run_icalbuddy")
    def test_sync_failure(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1)
        result = adapter.sync()
        assert result["changed_nodes"] == []


# --- Fetch body ---

class TestFetchBody:
    @patch.object(AppleCalendarAdapter, "resolve")
    def test_fetch_body_with_notes(self, mock_resolve, adapter):
        mock_resolve.return_value = adapter._event_to_node({
            "uid": "abc-123", "title": "Meeting", "notes": "Agenda"
        })
        body = adapter.fetch_body("abc-123")
        assert body == "Agenda"

    @patch.object(AppleCalendarAdapter, "resolve")
    def test_fetch_body_not_found(self, mock_resolve, adapter):
        mock_resolve.return_value = None
        body = adapter.fetch_body("nonexistent")
        assert body is None
