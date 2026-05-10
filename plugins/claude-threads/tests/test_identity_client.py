"""Test that we can read claude-identity's sessions-meta sidecar."""
import json

from lib.identity_client import read_session_tags, read_session_handle


def test_read_session_tags(tmp_home, write_sidecar):
    write_sidecar("sid-aaaa-bbbb-cccc-dddddddddddd",
                  tags=["02.14", "vault-sweeper"])
    assert read_session_tags(tmp_home, "sid-aaaa-bbbb-cccc-dddddddddddd") \
        == ["02.14", "vault-sweeper"]


def test_read_session_tags_missing_returns_empty(tmp_home):
    assert read_session_tags(tmp_home, "nonexistent") == []


def test_read_session_handle_uses_registry_name(tmp_home, write_registry_entry):
    write_registry_entry(pid=300, session_id="abc", name="fern")
    assert read_session_handle(tmp_home, "abc") == "fern"


def test_read_session_handle_falls_back_to_uuid_prefix(tmp_home, write_registry_entry):
    write_registry_entry(pid=301, session_id="11111111-2222-...", name=None)
    assert read_session_handle(tmp_home, "11111111-2222-...") == "11111111"
