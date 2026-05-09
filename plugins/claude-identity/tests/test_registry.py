"""Tests for the read-only session registry adapter."""
import os
import pytest

from lib.registry import resolve_handle, list_live_sessions, find_my_session


def test_resolve_handle_uses_name_field(tmp_home, sample_registry_entry):
    sample_registry_entry(pid=100, session_id="11111111-2222-3333-4444-555555555555",
                          name="vault-spec")
    assert resolve_handle(tmp_home, "11111111-2222-3333-4444-555555555555") == "vault-spec"


def test_resolve_handle_falls_back_to_uuid_prefix(tmp_home, sample_registry_entry):
    sample_registry_entry(pid=101, session_id="22222222-aaaa-bbbb-cccc-dddddddddddd",
                          name=None)
    assert resolve_handle(tmp_home, "22222222-aaaa-bbbb-cccc-dddddddddddd") == "22222222"


def test_resolve_handle_unknown_returns_none(tmp_home):
    assert resolve_handle(tmp_home, "ffffffff-ffff-ffff-ffff-ffffffffffff") is None


def test_list_live_sessions_filters_dead_pids(tmp_home, sample_registry_entry, monkeypatch):
    sample_registry_entry(pid=200, session_id="aaaa1111-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    sample_registry_entry(pid=999999, session_id="bbbb2222-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    # Mock kill: pid 200 alive, pid 999999 dead
    def mock_kill(pid, sig):
        if pid == 999999:
            raise ProcessLookupError()
    monkeypatch.setattr("lib.registry.os.kill", mock_kill)

    sessions = list_live_sessions(tmp_home)
    sids = [s["sessionId"] for s in sessions]
    assert "aaaa1111-aaaa-aaaa-aaaa-aaaaaaaaaaaa" in sids
    assert "bbbb2222-bbbb-bbbb-bbbb-bbbbbbbbbbbb" not in sids


def test_resolve_handle_or_uuid_handles_handle(tmp_home, sample_registry_entry, monkeypatch):
    """resolve_handle_or_uuid_to_session_id can take either a handle or UUID."""
    from lib.registry import resolve_handle_or_uuid_to_session_id
    sample_registry_entry(pid=300, session_id="cccc3333-cccc-cccc-cccc-cccccccccccc",
                          name="fern")
    monkeypatch.setattr("lib.registry.os.kill", lambda pid, sig: None)

    # Handle
    assert resolve_handle_or_uuid_to_session_id(tmp_home, "fern") == "cccc3333-cccc-cccc-cccc-cccccccccccc"
    # Full UUID
    assert resolve_handle_or_uuid_to_session_id(tmp_home, "cccc3333-cccc-cccc-cccc-cccccccccccc") == "cccc3333-cccc-cccc-cccc-cccccccccccc"
    # 8-char prefix
    assert resolve_handle_or_uuid_to_session_id(tmp_home, "cccc3333") == "cccc3333-cccc-cccc-cccc-cccccccccccc"


def test_resolve_ambiguous_raises(tmp_home, sample_registry_entry, monkeypatch):
    """Two sessions with same handle → AmbiguousHandle."""
    from lib.registry import resolve_handle_or_uuid_to_session_id, AmbiguousHandle
    sample_registry_entry(pid=400, session_id="dddd4444-dddd-dddd-dddd-dddddddddddd",
                          name="fern")
    sample_registry_entry(pid=401, session_id="eeee5555-eeee-eeee-eeee-eeeeeeeeeeee",
                          name="fern")
    monkeypatch.setattr("lib.registry.os.kill", lambda pid, sig: None)

    with pytest.raises(AmbiguousHandle) as excinfo:
        resolve_handle_or_uuid_to_session_id(tmp_home, "fern")
    assert "fern" in str(excinfo.value)
    assert len(excinfo.value.candidates) == 2
