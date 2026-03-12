"""Tests for the Apple Contacts adapter."""

import json
import subprocess
from unittest.mock import patch, MagicMock
import pytest

from src.adapters.apple_contacts import AppleContactsAdapter


@pytest.fixture
def adapter():
    return AppleContactsAdapter()


def make_result(stdout="", stderr="", returncode=0):
    r = MagicMock(spec=subprocess.CompletedProcess)
    r.stdout = stdout
    r.stderr = stderr
    r.returncode = returncode
    return r


SAMPLE_CONTACTS_JSON = json.dumps([
    {
        "id": "ABC-123",
        "name": "John Doe",
        "firstName": "John",
        "lastName": "Doe",
        "organization": "Acme Corp",
        "jobTitle": "Engineer",
        "note": "Met at conference",
        "emailList": ["john@acme.com"],
        "phoneList": ["+1-555-0100"],
    },
    {
        "id": "DEF-456",
        "name": "Jane Smith",
        "firstName": "Jane",
        "lastName": "Smith",
        "organization": "",
        "jobTitle": "",
        "note": "",
        "emailList": [],
        "phoneList": [],
    },
])

SAMPLE_SINGLE_CONTACT = json.dumps([{
    "id": "ABC-123",
    "name": "John Doe",
    "firstName": "John",
    "lastName": "Doe",
    "organization": "Acme Corp",
    "jobTitle": "Engineer",
    "note": "Met at conference",
    "emailList": ["john@acme.com"],
    "phoneList": ["+1-555-0100"],
}])


# --- Health check ---

class TestHealthCheck:
    @patch.object(AppleContactsAdapter, "_run_osascript")
    def test_healthy(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout="Contacts")
        assert adapter.health_check() is True

    @patch.object(AppleContactsAdapter, "_run_osascript")
    def test_unhealthy(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1)
        assert adapter.health_check() is False


# --- Node builder ---

class TestNodeBuilder:
    def test_contact_to_node_full(self, adapter):
        data = {
            "id": "ABC-123",
            "name": "John Doe",
            "firstName": "John",
            "lastName": "Doe",
            "organization": "Acme Corp",
            "jobTitle": "Engineer",
            "note": "Notes here",
            "emailList": ["john@acme.com"],
            "phoneList": ["+1-555-0100"],
        }
        node = adapter._contact_to_node(data)
        assert node["type"] == "contact"
        assert node["adapter"] == "apple-contacts"
        assert node["native_id"] == "ABC-123"
        assert node["register"] == "reference"
        assert node["attributes"]["name"] == "John Doe"
        assert node["attributes"]["email"] == "john@acme.com"
        assert node["attributes"]["phone"] == "+1-555-0100"
        assert node["attributes"]["organization"] == "Acme Corp"
        assert node["attributes"]["role"] == "Engineer"
        assert node["body"] == "Notes here"

    def test_contact_minimal(self, adapter):
        data = {"id": "x", "name": "Simple", "emailList": [], "phoneList": []}
        node = adapter._contact_to_node(data)
        assert node["attributes"]["name"] == "Simple"
        assert "email" not in node["attributes"]
        assert "phone" not in node["attributes"]

    def test_contact_name_from_parts(self, adapter):
        data = {"id": "x", "firstName": "Jane", "lastName": "Smith"}
        node = adapter._contact_to_node(data)
        assert node["attributes"]["name"] == "Jane Smith"

    def test_contact_no_note(self, adapter):
        data = {"id": "x", "name": "Test", "note": ""}
        node = adapter._contact_to_node(data)
        assert node["body"] is None


# --- Resolve ---

class TestResolve:
    @patch.object(AppleContactsAdapter, "_run_osascript")
    def test_resolve_found(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_SINGLE_CONTACT)
        node = adapter.resolve("ABC-123")
        assert node is not None
        assert node["attributes"]["name"] == "John Doe"

    @patch.object(AppleContactsAdapter, "_run_osascript")
    def test_resolve_not_found(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1)
        node = adapter.resolve("nonexistent")
        assert node is None

    @patch.object(AppleContactsAdapter, "_run_osascript")
    def test_resolve_empty(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout="[]")
        node = adapter.resolve("x")
        assert node is None


# --- Reverse resolve ---

class TestReverseResolve:
    def test_valid_uri(self, adapter):
        result = adapter.reverse_resolve("pim://contact/apple-contacts/ABC-123")
        assert result == "ABC-123"

    def test_wrong_adapter(self, adapter):
        result = adapter.reverse_resolve("pim://contact/internal/ABC-123")
        assert result is None

    def test_malformed_uri(self, adapter):
        result = adapter.reverse_resolve("pim://contact/apple-contacts")
        assert result is None


# --- Enumerate ---

class TestEnumerate:
    @patch.object(AppleContactsAdapter, "_run_osascript")
    def test_enumerate_contacts(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_CONTACTS_JSON)
        nodes = adapter.enumerate("contact")
        assert len(nodes) == 2
        assert all(n["type"] == "contact" for n in nodes)
        assert all(n["register"] == "reference" for n in nodes)

    @patch.object(AppleContactsAdapter, "_run_osascript")
    def test_enumerate_wrong_type(self, mock_run, adapter):
        nodes = adapter.enumerate("task")
        assert nodes == []

    @patch.object(AppleContactsAdapter, "_run_osascript")
    def test_enumerate_with_offset(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_CONTACTS_JSON)
        nodes = adapter.enumerate("contact", offset=1, limit=10)
        assert len(nodes) == 1

    @patch.object(AppleContactsAdapter, "_run_osascript")
    def test_enumerate_failure(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1)
        nodes = adapter.enumerate("contact")
        assert nodes == []


# --- Create ---

class TestCreate:
    @patch.object(AppleContactsAdapter, "_run_osascript")
    def test_create_contact(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout="NEW-ID-789")
        node = adapter.create_node("contact", {
            "name": "New Person",
            "email": "new@example.com",
            "phone": "+1-555-9999",
            "organization": "NewCo",
        })
        assert node["attributes"]["name"] == "New Person"
        assert node["attributes"]["email"] == "new@example.com"

    @patch.object(AppleContactsAdapter, "_run_osascript")
    def test_create_minimal(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout="MIN-ID")
        node = adapter.create_node("contact", {"name": "Just Name"})
        assert node["attributes"]["name"] == "Just Name"

    @patch.object(AppleContactsAdapter, "_run_osascript")
    def test_create_failure(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1, stderr="error")
        with pytest.raises(RuntimeError, match="Failed to create contact"):
            adapter.create_node("contact", {"name": "Fail"})

    def test_create_wrong_type(self, adapter):
        with pytest.raises(ValueError, match="Unsupported type"):
            adapter.create_node("note", {"title": "Not a contact"})


# --- Query ---

class TestQuery:
    @patch.object(AppleContactsAdapter, "_run_osascript")
    def test_query_all(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_CONTACTS_JSON)
        nodes = adapter.query_nodes("contact")
        assert len(nodes) == 2

    @patch.object(AppleContactsAdapter, "_run_osascript")
    def test_query_wrong_type(self, mock_run, adapter):
        nodes = adapter.query_nodes("task")
        assert nodes == []

    @patch.object(AppleContactsAdapter, "_run_osascript")
    def test_query_text_search(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_CONTACTS_JSON)
        adapter.query_nodes("contact", {"text_search": "john"})
        # Verify search script was used
        mock_run.assert_called_once()

    @patch.object(AppleContactsAdapter, "_run_osascript")
    def test_query_with_attribute_filter(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_CONTACTS_JSON)
        nodes = adapter.query_nodes("contact", {
            "attributes": {"name": "Jane Smith"}
        })
        assert len(nodes) == 1

    @patch.object(AppleContactsAdapter, "_run_osascript")
    def test_query_with_limit(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_CONTACTS_JSON)
        nodes = adapter.query_nodes("contact", {"limit": 1})
        assert len(nodes) == 1

    @patch.object(AppleContactsAdapter, "_run_osascript")
    def test_query_failure(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1)
        nodes = adapter.query_nodes("contact")
        assert nodes == []


# --- Update ---

class TestUpdate:
    @patch.object(AppleContactsAdapter, "resolve")
    @patch.object(AppleContactsAdapter, "_run_osascript")
    def test_update_name(self, mock_run, mock_resolve, adapter):
        mock_run.return_value = make_result(stdout="ABC-123")
        mock_resolve.return_value = adapter._contact_to_node({
            "id": "ABC-123", "name": "Updated Name"
        })
        node = adapter.update_node("ABC-123", {
            "attributes": {"name": "Updated Name"}
        })
        assert node["attributes"]["name"] == "Updated Name"

    @patch.object(AppleContactsAdapter, "_run_osascript")
    def test_update_failure(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1, stderr="error")
        with pytest.raises(RuntimeError, match="Failed to update contact"):
            adapter.update_node("x", {"attributes": {"name": "Fail"}})

    @patch.object(AppleContactsAdapter, "resolve")
    @patch.object(AppleContactsAdapter, "_run_osascript")
    def test_update_resolve_fails(self, mock_run, mock_resolve, adapter):
        mock_run.return_value = make_result(stdout="x")
        mock_resolve.return_value = None
        with pytest.raises(ValueError, match="Contact not found"):
            adapter.update_node("x", {"attributes": {"name": "X"}})


# --- Close ---

class TestClose:
    @patch.object(AppleContactsAdapter, "_run_osascript")
    def test_close_delete(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout="")
        adapter.close_node("ABC-123", "delete")
        mock_run.assert_called_once()

    @patch.object(AppleContactsAdapter, "_run_osascript")
    def test_close_delete_failure(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1, stderr="error")
        with pytest.raises(RuntimeError, match="Failed to delete contact"):
            adapter.close_node("ABC-123", "delete")

    def test_close_archive_noop(self, adapter):
        adapter.close_node("ABC-123", "archive")

    def test_close_complete_noop(self, adapter):
        adapter.close_node("ABC-123", "complete")

    def test_close_invalid_mode(self, adapter):
        with pytest.raises(ValueError, match="supports close modes"):
            adapter.close_node("ABC-123", "cancel")


# --- Sync ---

class TestSync:
    @patch.object(AppleContactsAdapter, "_run_osascript")
    def test_sync_returns_contacts(self, mock_run, adapter):
        mock_run.return_value = make_result(stdout=SAMPLE_CONTACTS_JSON)
        result = adapter.sync()
        assert len(result["changed_nodes"]) == 2

    @patch.object(AppleContactsAdapter, "_run_osascript")
    def test_sync_failure(self, mock_run, adapter):
        mock_run.return_value = make_result(returncode=1)
        result = adapter.sync()
        assert result["changed_nodes"] == []


# --- Fetch body ---

class TestFetchBody:
    @patch.object(AppleContactsAdapter, "resolve")
    def test_fetch_body(self, mock_resolve, adapter):
        mock_resolve.return_value = adapter._contact_to_node({
            "id": "x", "name": "Test", "note": "Notes about contact"
        })
        body = adapter.fetch_body("x")
        assert body == "Notes about contact"

    @patch.object(AppleContactsAdapter, "resolve")
    def test_fetch_body_not_found(self, mock_resolve, adapter):
        mock_resolve.return_value = None
        body = adapter.fetch_body("nonexistent")
        assert body is None
