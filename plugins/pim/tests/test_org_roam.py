"""Tests for the org-roam adapter."""

import json
from unittest.mock import patch
import subprocess

import pytest

from src.adapters.org_roam import OrgRoamAdapter


@pytest.fixture
def adapter():
    return OrgRoamAdapter()


def mock_run(stdout="", stderr="", returncode=0):
    """Create a mock CompletedProcess."""
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr,
    )


def json_stdout(data):
    """Create stdout that looks like emacsclient returning json-encoded data."""
    encoded = json.dumps(data)
    # emacsclient wraps in quotes
    return f'"{encoded.replace(chr(34), chr(92)+chr(34))}"'


SAMPLE_NODE = {
    "id": "abc-123",
    "title": "Test Note",
    "file": "/notes/20260312-test-note.org",
    "tags": ["project", "work"],
}

SAMPLE_NODE_INBOX = {
    "id": "def-456",
    "title": "Quick thought",
    "file": "/notes/20260312-quick-thought.org",
    "tags": ["inbox"],
}

SAMPLE_NODE_REF = {
    "id": "ghi-789",
    "title": "Reference Doc",
    "file": "/notes/reference-doc.org",
    "tags": ["reference"],
}


# --- Health check ---

class TestHealthCheck:
    @patch("src.adapters.org_roam.subprocess.run")
    def test_healthy(self, mock_subprocess, adapter):
        mock_subprocess.return_value = mock_run(stdout='"2.2.2"')
        assert adapter.health_check() is True

    @patch("src.adapters.org_roam.subprocess.run")
    def test_unhealthy_nil(self, mock_subprocess, adapter):
        mock_subprocess.return_value = mock_run(stdout="nil")
        assert adapter.health_check() is False

    @patch("src.adapters.org_roam.subprocess.run")
    def test_unhealthy_error(self, mock_subprocess, adapter):
        mock_subprocess.return_value = mock_run(returncode=1, stderr="error")
        assert adapter.health_check() is False

    @patch("src.adapters.org_roam.subprocess.run")
    def test_unhealthy_missing(self, mock_subprocess, adapter):
        mock_subprocess.side_effect = FileNotFoundError
        assert adapter.health_check() is False


# --- Node building ---

class TestBuildNode:
    def test_build_working_node(self, adapter):
        node = adapter._build_node(SAMPLE_NODE)
        assert node["id"] == "pim://note/org-roam/abc-123"
        assert node["type"] == "note"
        assert node["register"] == "working"
        assert node["attributes"]["title"] == "Test Note"
        assert node["attributes"]["tags"] == ["project", "work"]

    def test_build_inbox_node(self, adapter):
        node = adapter._build_node(SAMPLE_NODE_INBOX)
        assert node["register"] == "scratch"

    def test_build_reference_node(self, adapter):
        node = adapter._build_node(SAMPLE_NODE_REF)
        assert node["register"] == "reference"

    def test_build_no_tags(self, adapter):
        data = {"id": "x", "title": "X", "file": "/x.org", "tags": []}
        node = adapter._build_node(data)
        assert node["register"] == "working"  # default

    def test_build_missing_fields(self, adapter):
        node = adapter._build_node({})
        assert node["attributes"]["title"] == ""
        assert node["attributes"]["tags"] == []


# --- Resolve ---

class TestResolve:
    @patch("src.adapters.org_roam.subprocess.run")
    def test_resolve_found(self, mock_subprocess, adapter):
        mock_subprocess.return_value = mock_run(stdout=json_stdout(SAMPLE_NODE))
        node = adapter.resolve("abc-123")
        assert node is not None
        assert node["attributes"]["title"] == "Test Note"

    @patch("src.adapters.org_roam.subprocess.run")
    def test_resolve_not_found(self, mock_subprocess, adapter):
        mock_subprocess.return_value = mock_run(stdout='"null"')
        node = adapter.resolve("nonexistent")
        assert node is None


# --- Reverse resolve ---

class TestReverseResolve:
    def test_reverse_resolve(self, adapter):
        result = adapter.reverse_resolve("pim://note/org-roam/abc-123")
        assert result == "abc-123"

    def test_reverse_resolve_wrong_adapter(self, adapter):
        result = adapter.reverse_resolve("pim://note/internal/abc-123")
        assert result is None


# --- Enumerate ---

class TestEnumerate:
    @patch("src.adapters.org_roam.subprocess.run")
    def test_enumerate_notes(self, mock_subprocess, adapter):
        mock_subprocess.return_value = mock_run(
            stdout=json_stdout([SAMPLE_NODE, SAMPLE_NODE_INBOX])
        )
        nodes = adapter.enumerate("note")
        assert len(nodes) == 2

    @patch("src.adapters.org_roam.subprocess.run")
    def test_enumerate_wrong_type(self, mock_subprocess, adapter):
        nodes = adapter.enumerate("task")
        assert nodes == []
        mock_subprocess.assert_not_called()

    @patch("src.adapters.org_roam.subprocess.run")
    def test_enumerate_empty(self, mock_subprocess, adapter):
        mock_subprocess.return_value = mock_run(stdout='"null"')
        nodes = adapter.enumerate("note")
        assert nodes == []


# --- Create ---

class TestCreateNode:
    @patch("src.adapters.org_roam.subprocess.run")
    def test_create_note(self, mock_subprocess, adapter):
        mock_subprocess.return_value = mock_run(stdout='"new-id-123"')
        node = adapter.create_node("note", {"title": "New Note"})
        assert node["type"] == "note"
        assert node["native_id"] == "new-id-123"
        assert node["attributes"]["title"] == "New Note"

    @patch("src.adapters.org_roam.subprocess.run")
    def test_create_with_body(self, mock_subprocess, adapter):
        mock_subprocess.return_value = mock_run(stdout='"new-id-456"')
        node = adapter.create_node("note", {"title": "With Body"}, body="Content here")
        assert node["native_id"] == "new-id-456"
        # Should have made multiple emacsclient calls (create + get file + append)
        assert mock_subprocess.call_count >= 2

    def test_create_wrong_type(self, adapter):
        with pytest.raises(ValueError, match="only supports notes"):
            adapter.create_node("task", {"title": "X"})


# --- Query ---

class TestQueryNodes:
    @patch("src.adapters.org_roam.subprocess.run")
    def test_query_all(self, mock_subprocess, adapter):
        mock_subprocess.return_value = mock_run(
            stdout=json_stdout([SAMPLE_NODE])
        )
        nodes = adapter.query_nodes("note")
        assert len(nodes) == 1

    @patch("src.adapters.org_roam.subprocess.run")
    def test_query_with_text_search(self, mock_subprocess, adapter):
        mock_subprocess.return_value = mock_run(
            stdout=json_stdout([SAMPLE_NODE])
        )
        nodes = adapter.query_nodes("note", {"text_search": "Test"})
        assert len(nodes) == 1

    @patch("src.adapters.org_roam.subprocess.run")
    def test_query_with_register_filter(self, mock_subprocess, adapter):
        mock_subprocess.return_value = mock_run(
            stdout=json_stdout([SAMPLE_NODE, SAMPLE_NODE_INBOX])
        )
        nodes = adapter.query_nodes("note", {"register": "scratch"})
        assert len(nodes) == 1
        assert nodes[0]["register"] == "scratch"

    def test_query_wrong_type(self, adapter):
        nodes = adapter.query_nodes("task")
        assert nodes == []


# --- Update ---

class TestUpdateNode:
    @patch("src.adapters.org_roam.subprocess.run")
    def test_update_title(self, mock_subprocess, adapter):
        # First call: update title, second: resolve to return updated node
        mock_subprocess.side_effect = [
            mock_run(stdout="t"),
            mock_run(stdout=json_stdout({**SAMPLE_NODE, "title": "Updated"})),
        ]
        node = adapter.update_node("abc-123", {"attributes": {"title": "Updated"}})
        assert node["attributes"]["title"] == "Updated"

    @patch("src.adapters.org_roam.subprocess.run")
    def test_update_tags(self, mock_subprocess, adapter):
        mock_subprocess.side_effect = [
            mock_run(stdout="t"),
            mock_run(stdout=json_stdout({**SAMPLE_NODE, "tags": ["new-tag"]})),
        ]
        node = adapter.update_node("abc-123", {"attributes": {"tags": ["new-tag"]}})
        assert "new-tag" in node["attributes"]["tags"]

    @patch("src.adapters.org_roam.subprocess.run")
    def test_update_not_found(self, mock_subprocess, adapter):
        mock_subprocess.side_effect = [
            mock_run(stdout="t"),
            mock_run(stdout='"null"'),
        ]
        with pytest.raises(ValueError, match="Node not found"):
            adapter.update_node("missing", {"attributes": {"title": "X"}})


# --- Close ---

class TestCloseNode:
    @patch("src.adapters.org_roam.subprocess.run")
    def test_close_delete(self, mock_subprocess, adapter):
        mock_subprocess.return_value = mock_run(stdout="t")
        adapter.close_node("abc-123", "delete")
        mock_subprocess.assert_called_once()

    @patch("src.adapters.org_roam.subprocess.run")
    def test_close_archive(self, mock_subprocess, adapter):
        mock_subprocess.return_value = mock_run(stdout="t")
        adapter.close_node("abc-123", "archive")
        mock_subprocess.assert_called_once()

    @patch("src.adapters.org_roam.subprocess.run")
    def test_close_complete_noop(self, mock_subprocess, adapter):
        adapter.close_node("abc-123", "complete")
        mock_subprocess.assert_not_called()


# --- Sync ---

class TestSync:
    @patch("src.adapters.org_roam.subprocess.run")
    def test_sync(self, mock_subprocess, adapter):
        mock_subprocess.side_effect = [
            mock_run(stdout="t"),  # db-sync
            mock_run(stdout=json_stdout([SAMPLE_NODE])),  # enumerate
        ]
        result = adapter.sync()
        assert result["adapter"] == "org-roam"
        assert result["synced"] == 1


# --- Fetch body ---

class TestFetchBody:
    @patch("src.adapters.org_roam.subprocess.run")
    def test_fetch_body(self, mock_subprocess, adapter):
        content = "#+title: Test\\n\\nSome content here"
        mock_subprocess.return_value = mock_run(stdout=f'"{content}"')
        body = adapter.fetch_body("abc-123")
        assert body is not None
        assert "Some content here" in body

    @patch("src.adapters.org_roam.subprocess.run")
    def test_fetch_body_not_found(self, mock_subprocess, adapter):
        mock_subprocess.return_value = mock_run(stdout="nil")
        body = adapter.fetch_body("nonexistent")
        assert body is None


# --- Adapter identity ---

class TestAdapterIdentity:
    def test_adapter_id(self, adapter):
        assert adapter.adapter_id == "org-roam"

    def test_supported_types(self, adapter):
        assert adapter.supported_types == ("note",)

    def test_supported_registers(self, adapter):
        assert "working" in adapter.supported_registers
        assert "scratch" in adapter.supported_registers
