"""Tests for the Safari adapter."""

import json
import subprocess
from unittest.mock import patch, MagicMock
import pytest

from src.adapters.safari import SafariAdapter


@pytest.fixture
def adapter():
    return SafariAdapter()


def make_result(stdout="", stderr="", returncode=0):
    r = MagicMock(spec=subprocess.CompletedProcess)
    r.stdout = stdout
    r.stderr = stderr
    r.returncode = returncode
    return r


SAMPLE_READING_LIST = json.dumps([
    {
        "url": "https://example.com/article1",
        "title": "Interesting Article",
        "description": "An article about PIM systems",
        "dateAdded": "2026-03-10T10:00:00",
        "hasBeenRead": False,
    },
    {
        "url": "https://example.com/article2",
        "title": "Already Read",
        "description": "Old article",
        "dateAdded": "2026-03-01T08:00:00",
        "hasBeenRead": True,
    },
])

SAMPLE_BOOKMARKS = json.dumps([
    {
        "url": "https://example.com/tool",
        "title": "Useful Tool",
    },
    {
        "url": "https://docs.example.com",
        "title": "Documentation",
    },
])


# --- Health check ---

class TestHealthCheck:
    @patch.object(SafariAdapter, "_run_osascript")
    def test_healthy(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout="Safari")
        assert adapter.health_check() is True

    @patch.object(SafariAdapter, "_run_osascript")
    def test_unhealthy(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1)
        assert adapter.health_check() is False


# --- Register mapping ---

class TestRegisterMapping:
    def test_reading_list_unread(self, adapter):
        assert adapter._register_for_item({"hasBeenRead": False}) == "scratch"

    def test_reading_list_read(self, adapter):
        assert adapter._register_for_item({"hasBeenRead": True}) == "reference"

    def test_bookmark(self, adapter):
        assert adapter._register_for_item({}, "bookmark") == "reference"


# --- Node builder ---

class TestNodeBuilder:
    def test_reading_list_item(self, adapter):
        data = {
            "url": "https://example.com",
            "title": "Example",
            "description": "A site",
            "dateAdded": "2026-03-10T10:00:00",
            "hasBeenRead": False,
        }
        node = adapter._item_to_node(data, "reading_list")
        assert node["type"] == "resource"
        assert node["adapter"] == "safari"
        assert node["native_id"] == "https://example.com"
        assert node["attributes"]["uri"] == "https://example.com"
        assert node["attributes"]["title"] == "Example"
        assert node["attributes"]["read_status"] == "unread"
        assert node["register"] == "scratch"

    def test_bookmark_item(self, adapter):
        data = {"url": "https://example.com", "title": "Bookmarked"}
        node = adapter._item_to_node(data, "bookmark")
        assert node["register"] == "reference"
        assert node["attributes"]["read_status"] == "unread"

    def test_node_uses_url_as_native_id(self, adapter):
        data = {"url": "https://long.example.com/path/to/page"}
        node = adapter._item_to_node(data)
        assert node["native_id"] == "https://long.example.com/path/to/page"


# --- Resolve ---

class TestResolve:
    @patch.object(SafariAdapter, "_run_osascript")
    def test_resolve_from_reading_list(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_READING_LIST)
        node = adapter.resolve("https://example.com/article1")
        assert node is not None
        assert node["attributes"]["title"] == "Interesting Article"

    @patch.object(SafariAdapter, "_run_osascript")
    def test_resolve_from_bookmarks(self, mock_run, adapter):
        # First call (reading list) returns no match, second (bookmarks) finds it
        mock_run.side_effect = [
            make_result(stdout="[]"),  # reading list
            make_result(stdout=SAMPLE_BOOKMARKS),  # bookmarks
        ]
        node = adapter.resolve("https://example.com/tool")
        assert node is not None
        assert node["attributes"]["title"] == "Useful Tool"

    @patch.object(SafariAdapter, "_run_osascript")
    def test_resolve_not_found(self, mock_run, adapter):
        mock_run.side_effect = [
            make_result(stdout="[]"),
            make_result(stdout="[]"),
        ]
        node = adapter.resolve("https://nonexistent.com")
        assert node is None


# --- Reverse resolve ---

class TestReverseResolve:
    def test_valid_uri(self, adapter):
        result = adapter.reverse_resolve("pim://resource/safari/https://example.com/path")
        assert result == "https://example.com/path"

    def test_wrong_adapter(self, adapter):
        result = adapter.reverse_resolve("pim://resource/internal/abc")
        assert result is None

    def test_malformed_uri(self, adapter):
        result = adapter.reverse_resolve("pim://resource/safari")
        assert result is None


# --- Enumerate ---

class TestEnumerate:
    @patch.object(SafariAdapter, "_run_osascript")
    def test_enumerate_resources(self, mock_run, adapter):
        mock_run.side_effect = [
            make_result(stdout=SAMPLE_READING_LIST),
            make_result(stdout=SAMPLE_BOOKMARKS),
        ]
        nodes = adapter.enumerate("resource")
        assert len(nodes) == 4
        assert all(n["type"] == "resource" for n in nodes)

    @patch.object(SafariAdapter, "_run_osascript")
    def test_enumerate_wrong_type(self, mock_run, adapter):
        nodes = adapter.enumerate("task")
        assert nodes == []

    @patch.object(SafariAdapter, "_run_osascript")
    def test_enumerate_with_offset(self, mock_run, adapter):
        mock_run.side_effect = [
            make_result(stdout=SAMPLE_READING_LIST),
            make_result(stdout=SAMPLE_BOOKMARKS),
        ]
        nodes = adapter.enumerate("resource", offset=2, limit=10)
        assert len(nodes) == 2  # bookmarks only


# --- Create ---

class TestCreate:
    @patch.object(SafariAdapter, "_run_osascript")
    def test_create_reading_list_item(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout="")
        node = adapter.create_node("resource", {
            "uri": "https://new.example.com",
            "title": "New Item",
        })
        assert node["attributes"]["uri"] == "https://new.example.com"
        assert node["register"] == "scratch"

    @patch.object(SafariAdapter, "_run_osascript")
    def test_create_bookmark(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout="")
        node = adapter.create_node("resource", {
            "uri": "https://bookmark.example.com",
            "title": "Bookmarked",
            "target": "bookmark",
        })
        assert node["register"] == "reference"

    @patch.object(SafariAdapter, "_run_osascript")
    def test_create_failure(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1, stderr="error")
        with pytest.raises(RuntimeError, match="Failed to add to Safari"):
            adapter.create_node("resource", {"uri": "https://fail.com"})

    def test_create_wrong_type(self, adapter):
        with pytest.raises(ValueError, match="Unsupported type"):
            adapter.create_node("note", {"title": "Not a resource"})


# --- Query ---

class TestQuery:
    @patch.object(SafariAdapter, "_run_osascript")
    def test_query_all(self, mock_run, adapter):
        mock_run.side_effect = [
            make_result(stdout=SAMPLE_READING_LIST),
            make_result(stdout=SAMPLE_BOOKMARKS),
        ]
        nodes = adapter.query_nodes("resource")
        assert len(nodes) == 4

    @patch.object(SafariAdapter, "_run_osascript")
    def test_query_wrong_type(self, mock_run, adapter):
        nodes = adapter.query_nodes("task")
        assert nodes == []

    @patch.object(SafariAdapter, "_run_osascript")
    def test_query_scratch_only(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_READING_LIST)
        nodes = adapter.query_nodes("resource", {"register": "scratch"})
        # Only unread reading list items
        assert all(n["register"] == "scratch" for n in nodes)

    @patch.object(SafariAdapter, "_run_osascript")
    def test_query_reference_only(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_BOOKMARKS)
        nodes = adapter.query_nodes("resource", {"register": "reference"})
        assert all(n["register"] == "reference" for n in nodes)

    @patch.object(SafariAdapter, "_run_osascript")
    def test_query_text_search(self, mock_run, adapter):
        mock_run.side_effect = [
            make_result(stdout=SAMPLE_READING_LIST),
            make_result(stdout=SAMPLE_BOOKMARKS),
        ]
        nodes = adapter.query_nodes("resource", {"text_search": "interesting"})
        assert len(nodes) == 1
        assert nodes[0]["attributes"]["title"] == "Interesting Article"

    @patch.object(SafariAdapter, "_run_osascript")
    def test_query_with_limit(self, mock_run, adapter):
        mock_run.side_effect = [
            make_result(stdout=SAMPLE_READING_LIST),
            make_result(stdout=SAMPLE_BOOKMARKS),
        ]
        nodes = adapter.query_nodes("resource", {"limit": 2})
        assert len(nodes) == 2


# --- Update ---

class TestUpdate:
    @patch.object(SafariAdapter, "resolve")
    def test_update_returns_node(self, mock_resolve, adapter):
        mock_resolve.return_value = adapter._item_to_node({
            "url": "https://example.com", "title": "Example"
        })
        node = adapter.update_node("https://example.com", {})
        assert node is not None

    @patch.object(SafariAdapter, "resolve")
    def test_update_not_found(self, mock_resolve, adapter):
        mock_resolve.return_value = None
        with pytest.raises(ValueError, match="Resource not found"):
            adapter.update_node("https://missing.com", {})


# --- Close ---

class TestClose:
    def test_close_archive_noop(self, adapter):
        adapter.close_node("https://example.com", "archive")

    def test_close_delete_noop(self, adapter):
        adapter.close_node("https://example.com", "delete")

    def test_close_complete_noop(self, adapter):
        adapter.close_node("https://example.com", "complete")

    def test_close_invalid_mode(self, adapter):
        with pytest.raises(ValueError, match="supports close modes"):
            adapter.close_node("https://example.com", "cancel")


# --- Sync ---

class TestSync:
    @patch.object(SafariAdapter, "enumerate")
    def test_sync_returns_nodes(self, mock_enum, adapter):
        mock_enum.return_value = [
            adapter._item_to_node({"url": "https://a.com", "title": "A"}),
        ]
        result = adapter.sync()
        assert len(result["changed_nodes"]) == 1


# --- Fetch body ---

class TestFetchBody:
    @patch.object(SafariAdapter, "resolve")
    def test_fetch_body(self, mock_resolve, adapter):
        mock_resolve.return_value = adapter._item_to_node({
            "url": "https://example.com",
            "title": "Example",
            "description": "A description",
        })
        body = adapter.fetch_body("https://example.com")
        assert body == "A description"

    @patch.object(SafariAdapter, "resolve")
    def test_fetch_body_not_found(self, mock_resolve, adapter):
        mock_resolve.return_value = None
        body = adapter.fetch_body("https://missing.com")
        assert body is None
