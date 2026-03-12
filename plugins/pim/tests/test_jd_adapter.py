"""Tests for the Johnny Decimal adapter."""

import json
import subprocess
from unittest.mock import patch, MagicMock
import pytest

from src.adapters.jd import JDAdapter


@pytest.fixture
def adapter():
    return JDAdapter()


def make_result(stdout="", stderr="", returncode=0):
    r = MagicMock(spec=subprocess.CompletedProcess)
    r.stdout = stdout
    r.stderr = stderr
    r.returncode = returncode
    return r


SAMPLE_INDEX = json.dumps([
    {"id": "00-09", "name": "System"},
    {"id": "01", "name": "Capture"},
    {"id": "01.01", "name": "Unsorted", "path": "/Users/test/Documents/00-09 System/01 Capture/01.01 Unsorted"},
    {"id": "01.02", "name": "Downloads", "path": "/Users/test/Documents/00-09 System/01 Capture/01.02 Downloads"},
    {"id": "10-19", "name": "Personal"},
    {"id": "11", "name": "nelson.love"},
    {"id": "11.01", "name": "Unsorted", "path": "/Users/test/Documents/10-19 Personal/11 nelson.love/11.01 Unsorted"},
])

SAMPLE_SEARCH = json.dumps([
    {"id": "01.02", "name": "Downloads", "path": "/tmp/01.02"},
    {"id": "06.03", "name": "Dotfiles", "path": "/tmp/06.03"},
])


# --- JD level detection ---

class TestJDLevel:
    def test_area(self, adapter):
        assert adapter._jd_level("00-09") == "area"
        assert adapter._jd_level("10-19") == "area"

    def test_category(self, adapter):
        assert adapter._jd_level("01") == "category"
        assert adapter._jd_level("13") == "category"

    def test_id(self, adapter):
        assert adapter._jd_level("01.01") == "id"
        assert adapter._jd_level("13.05") == "id"


# --- Health check ---

class TestHealthCheck:
    @patch.object(JDAdapter, "_run_jd")
    def test_healthy(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout="jd 0.8.0")
        assert adapter.health_check() is True

    @patch.object(JDAdapter, "_run_jd")
    def test_unhealthy(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1)
        assert adapter.health_check() is False


# --- Node builders ---

class TestNodeBuilders:
    def test_area_to_node(self, adapter):
        node = adapter._area_to_node({"id": "00-09", "name": "System"})
        assert node["type"] == "topic"
        assert node["register"] == "reference"
        assert node["attributes"]["title"] == "System"
        assert node["attributes"]["jd_level"] == "area"
        assert node["attributes"]["taxonomy_id"] == "00-09"

    def test_category_to_node(self, adapter):
        node = adapter._category_to_node({"id": "01", "name": "Capture"})
        assert node["type"] == "topic"
        assert node["register"] == "reference"
        assert node["attributes"]["jd_level"] == "category"

    def test_id_to_node(self, adapter):
        node = adapter._id_to_node({"id": "01.01", "name": "Unsorted", "path": "/tmp/01.01"})
        assert node["type"] == "topic"
        assert node["register"] == "working"
        assert node["attributes"]["jd_level"] == "id"
        assert node["attributes"]["path"] == "/tmp/01.01"

    def test_file_to_node(self, adapter):
        node = adapter._file_to_node({"path": "/tmp/doc.md", "name": "doc.md", "jd_id": "01.01"})
        assert node["type"] == "resource"
        assert node["register"] == "reference"
        assert node["attributes"]["uri"] == "/tmp/doc.md"


# --- Resolve ---

class TestResolve:
    @patch.object(JDAdapter, "_run_jd")
    def test_resolve_area(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=json.dumps({"name": "System"}))
        node = adapter.resolve("00-09")
        assert node is not None
        assert node["attributes"]["jd_level"] == "area"
        mock_run.assert_called_once_with("ls", "00-09", "--json")

    @patch.object(JDAdapter, "_run_jd")
    def test_resolve_category(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=json.dumps({"name": "Capture"}))
        node = adapter.resolve("01")
        assert node is not None
        assert node["attributes"]["jd_level"] == "category"

    @patch.object(JDAdapter, "_run_jd")
    def test_resolve_id(self, mock_run, adapter):
        mock_run.side_effect = [
            make_result(stdout="/tmp/01.01"),  # jd which
            make_result(stdout=json.dumps({"name": "Unsorted"})),  # jd ls
        ]
        node = adapter.resolve("01.01")
        assert node is not None
        assert node["attributes"]["jd_level"] == "id"
        assert node["attributes"]["path"] == "/tmp/01.01"

    @patch.object(JDAdapter, "_run_jd")
    def test_resolve_not_found(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1)
        node = adapter.resolve("99.99")
        assert node is None


# --- Reverse resolve ---

class TestReverseResolve:
    def test_valid_uri(self, adapter):
        result = adapter.reverse_resolve("pim://topic/jd/01.01")
        assert result == "01.01"

    def test_wrong_adapter(self, adapter):
        result = adapter.reverse_resolve("pim://topic/internal/abc")
        assert result is None

    def test_malformed_uri(self, adapter):
        result = adapter.reverse_resolve("pim://topic/jd")
        assert result is None


# --- Enumerate ---

class TestEnumerate:
    @patch.object(JDAdapter, "_run_jd")
    def test_enumerate_topics(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_INDEX)
        nodes = adapter.enumerate("topic")
        assert len(nodes) == 7
        # Check types
        areas = [n for n in nodes if n["attributes"]["jd_level"] == "area"]
        cats = [n for n in nodes if n["attributes"]["jd_level"] == "category"]
        ids = [n for n in nodes if n["attributes"]["jd_level"] == "id"]
        assert len(areas) == 2
        assert len(cats) == 2
        assert len(ids) == 3

    @patch.object(JDAdapter, "_run_jd")
    def test_enumerate_wrong_type(self, mock_run, adapter):
        nodes = adapter.enumerate("task")
        assert nodes == []

    @patch.object(JDAdapter, "_run_jd")
    def test_enumerate_with_offset(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_INDEX)
        nodes = adapter.enumerate("topic", offset=5, limit=10)
        assert len(nodes) == 2

    @patch.object(JDAdapter, "_run_jd")
    def test_enumerate_failure(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1)
        nodes = adapter.enumerate("topic")
        assert nodes == []

    @patch.object(JDAdapter, "_run_jd")
    def test_enumerate_resources_empty(self, mock_run, adapter):
        nodes = adapter.enumerate("resource")
        assert nodes == []


# --- Create ---

class TestCreate:
    @patch.object(JDAdapter, "_run_jd")
    def test_create_jd_id(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout="01.03")
        node = adapter.create_node("topic", {
            "title": "New Item",
            "taxonomy_id": "01",
        })
        assert node["native_id"] == "01.03"
        mock_run.assert_called_once_with("new-id", "01", "New Item")

    @patch.object(JDAdapter, "_run_jd")
    def test_create_category(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout="07")
        node = adapter.create_node("topic", {"title": "New Category"})
        mock_run.assert_called_once_with("new-category", "New Category")

    @patch.object(JDAdapter, "_run_jd")
    def test_create_failure(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1, stderr="error")
        with pytest.raises(RuntimeError, match="Failed to create JD entry"):
            adapter.create_node("topic", {"title": "Fail"})

    def test_create_wrong_type(self, adapter):
        with pytest.raises(ValueError, match="Unsupported type"):
            adapter.create_node("note", {"title": "Not a topic"})


# --- Query ---

class TestQuery:
    @patch.object(JDAdapter, "_run_jd")
    def test_query_topics(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_INDEX)
        nodes = adapter.query_nodes("topic")
        assert len(nodes) == 7

    @patch.object(JDAdapter, "_run_jd")
    def test_query_text_search(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_SEARCH)
        nodes = adapter.query_nodes("topic", {"text_search": "downloads"})
        assert len(nodes) == 2

    @patch.object(JDAdapter, "_run_jd")
    def test_query_wrong_type(self, mock_run, adapter):
        nodes = adapter.query_nodes("task")
        assert nodes == []

    @patch.object(JDAdapter, "_run_jd")
    def test_query_with_limit(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_INDEX)
        nodes = adapter.query_nodes("topic", {"limit": 3})
        assert len(nodes) == 3


# --- Update ---

class TestUpdate:
    @patch.object(JDAdapter, "resolve")
    @patch.object(JDAdapter, "_run_jd")
    def test_update_rename(self, mock_run, mock_resolve, adapter):
        mock_run.return_value = make_result(stdout="")
        mock_resolve.return_value = adapter._id_to_node({
            "id": "01.01", "name": "Renamed", "path": "/tmp/01.01"
        })
        node = adapter.update_node("01.01", {"attributes": {"title": "Renamed"}})
        mock_run.assert_called_once_with("mv", "01.01", "Renamed")
        assert node["attributes"]["title"] == "Renamed"

    @patch.object(JDAdapter, "_run_jd")
    def test_update_failure(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1, stderr="error")
        with pytest.raises(RuntimeError, match="Failed to rename"):
            adapter.update_node("01.01", {"attributes": {"title": "Fail"}})

    @patch.object(JDAdapter, "resolve")
    @patch.object(JDAdapter, "_run_jd")
    def test_update_resolve_fails(self, mock_run, mock_resolve, adapter):
        mock_run.return_value = make_result(stdout="")
        mock_resolve.return_value = None
        with pytest.raises(ValueError, match="JD entry not found"):
            adapter.update_node("01.01", {"attributes": {"title": "X"}})


# --- Close ---

class TestClose:
    def test_close_archive_noop(self, adapter):
        adapter.close_node("01.01", "archive")

    def test_close_delete_raises(self, adapter):
        with pytest.raises(ValueError, match="should not be deleted"):
            adapter.close_node("01.01", "delete")

    def test_close_other_noop(self, adapter):
        adapter.close_node("01.01", "complete")


# --- Sync ---

class TestSync:
    @patch.object(JDAdapter, "_run_jd")
    def test_sync_returns_nodes(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_INDEX)
        result = adapter.sync()
        assert len(result["changed_nodes"]) == 7

    @patch.object(JDAdapter, "_run_jd")
    def test_sync_failure(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1)
        result = adapter.sync()
        assert result["changed_nodes"] == []


# --- Fetch body ---

class TestFetchBody:
    @patch.object(JDAdapter, "_run_jd")
    def test_fetch_body_with_readme(self, mock_run, adapter, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text("# Hello\nThis is the JD ID readme.")
        mock_run.return_value = make_result(stdout=str(tmp_path))
        body = adapter.fetch_body("01.01")
        assert "Hello" in body

    @patch.object(JDAdapter, "_run_jd")
    def test_fetch_body_no_readme(self, mock_run, adapter, tmp_path):
        mock_run.return_value = make_result(stdout=str(tmp_path))
        body = adapter.fetch_body("01.01")
        assert body is None

    @patch.object(JDAdapter, "_run_jd")
    def test_fetch_body_not_found(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1)
        body = adapter.fetch_body("99.99")
        assert body is None
