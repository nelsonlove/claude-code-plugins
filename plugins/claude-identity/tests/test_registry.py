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


# ---------------------------------------------------------------------------
# v0.1.3: set_handle (writes sidecar `handle` field; decoupled from CC's name)
# ---------------------------------------------------------------------------

def test_set_handle_writes_sidecar_handle(tmp_home, sample_registry_entry):
    """v0.1.3: handle lives in the sessions-meta sidecar, not the CC registry."""
    from lib.registry import set_handle
    from lib.sidecar import get_handle
    sid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    sample_registry_entry(pid=500, session_id=sid)
    result = set_handle(tmp_home, my_pid=500, handle="cairn")
    assert result == {"ok": True, "handle": "cairn", "previous": None}
    assert get_handle(tmp_home, sid) == "cairn"
    # CC's registry `name` field is NOT touched by set_handle:
    import json
    entry = json.loads((tmp_home / ".claude" / "sessions" / "500.json").read_text())
    assert "name" not in entry or entry.get("name") is None


def test_set_handle_returns_previous_when_overwriting(tmp_home, sample_registry_entry):
    from lib.registry import set_handle
    sample_registry_entry(pid=501, session_id="bbbb1111-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                          name="old-name")
    result = set_handle(tmp_home, my_pid=501, handle="new-name")
    assert result["previous"] == "old-name"
    assert result["handle"] == "new-name"


def test_set_handle_normalizes_to_lowercase(tmp_home, sample_registry_entry):
    from lib.registry import set_handle
    sample_registry_entry(pid=502, session_id="cccc2222-cccc-cccc-cccc-cccccccccccc")
    result = set_handle(tmp_home, my_pid=502, handle="  Cairn  ")
    assert result["handle"] == "cairn"


def test_set_handle_rejects_reserved_tokens(tmp_home, sample_registry_entry):
    from lib.registry import set_handle, InvalidHandle
    sample_registry_entry(pid=503, session_id="dddd3333-dddd-dddd-dddd-dddddddddddd")
    for bad in ["*", "all", "any", "self", "external"]:
        with pytest.raises(InvalidHandle):
            set_handle(tmp_home, my_pid=503, handle=bad)


def test_set_handle_rejects_uuid_prefix_shape(tmp_home, sample_registry_entry):
    from lib.registry import set_handle, InvalidHandle
    sample_registry_entry(pid=504, session_id="eeee4444-eeee-eeee-eeee-eeeeeeeeeeee")
    with pytest.raises(InvalidHandle, match="UUID prefix"):
        set_handle(tmp_home, my_pid=504, handle="abcdef12")


def test_set_handle_rejects_invalid_chars(tmp_home, sample_registry_entry):
    from lib.registry import set_handle, InvalidHandle
    sample_registry_entry(pid=505, session_id="ffff5555-ffff-ffff-ffff-ffffffffffff")
    for bad in ["a", "has spaces", "with/slash", "with.dot", "two-segment-name-extra"]:
        with pytest.raises(InvalidHandle):
            set_handle(tmp_home, my_pid=505, handle=bad)


def test_set_handle_normalizes_uppercase(tmp_home, sample_registry_entry):
    """Uppercase input is normalized to lowercase, not rejected."""
    from lib.registry import set_handle
    sample_registry_entry(pid=506, session_id="ffff6666-ffff-ffff-ffff-ffffffffffff")
    result = set_handle(tmp_home, my_pid=506, handle="CAIRN")
    assert result["handle"] == "cairn"


def test_set_handle_collision_with_other_live_session(tmp_home, sample_registry_entry, monkeypatch):
    from lib.registry import set_handle, HandleCollision
    sample_registry_entry(pid=600, session_id="aaaa6666-aaaa-aaaa-aaaa-aaaaaaaaaaaa", name="taken")
    sample_registry_entry(pid=601, session_id="bbbb6666-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    monkeypatch.setattr("lib.registry.os.kill", lambda pid, sig: None)
    with pytest.raises(HandleCollision) as excinfo:
        set_handle(tmp_home, my_pid=601, handle="taken")
    assert excinfo.value.taken_by_session_id == "aaaa6666-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def test_set_handle_self_re_set_is_not_collision(tmp_home, sample_registry_entry, monkeypatch):
    """Setting your own handle to its current value is fine, not a collision."""
    from lib.registry import set_handle
    sample_registry_entry(pid=700, session_id="cccc7777-cccc-cccc-cccc-cccccccccccc", name="cairn")
    monkeypatch.setattr("lib.registry.os.kill", lambda pid, sig: None)
    result = set_handle(tmp_home, my_pid=700, handle="cairn")
    assert result["ok"] is True
    assert result["handle"] == "cairn"


def test_set_handle_unknown_pid_raises_keyerror(tmp_home):
    from lib.registry import set_handle
    with pytest.raises(KeyError, match="no registry entry"):
        set_handle(tmp_home, my_pid=99999, handle="cairn")
