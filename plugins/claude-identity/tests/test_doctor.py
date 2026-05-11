"""Tests for the doctor (stale-sidecar pruning)."""
import json
from pathlib import Path

import pytest

from lib import doctor, sidecar


def _write_registry_entry(home, pid, session_id):
    d = Path(home) / ".claude" / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{pid}.json").write_text(json.dumps({
        "pid": pid, "sessionId": session_id, "cwd": "/tmp", "status": "idle",
    }))


def test_find_stale_sidecars_empty_when_no_meta_dir(tmp_home):
    assert doctor.find_stale_sidecars(tmp_home) == []


def test_find_stale_sidecars_alive_session_not_stale(tmp_home, monkeypatch):
    sid = "live-uuid-1111"
    _write_registry_entry(tmp_home, pid=99001, session_id=sid)
    sidecar.create_if_absent(tmp_home, sid, default_tags=[], handle="alive")
    monkeypatch.setattr("lib.registry.os.kill", lambda pid, sig: None)
    stale = doctor.find_stale_sidecars(tmp_home)
    assert stale == []


def test_find_stale_sidecars_dead_session_is_stale(tmp_home, monkeypatch):
    """Session has a sidecar but no live registry entry → stale."""
    sid = "dead-uuid-2222"
    sidecar.create_if_absent(tmp_home, sid, default_tags=[], handle="ghost")
    # Pretend nothing is alive
    monkeypatch.setattr("lib.registry.os.kill", lambda pid, sig: (_ for _ in ()).throw(ProcessLookupError()))
    stale = doctor.find_stale_sidecars(tmp_home)
    assert len(stale) == 1
    assert stale[0]["session_id"] == sid
    assert stale[0]["handle"] == "ghost"


def test_prune_dry_run_does_not_remove(tmp_home, monkeypatch):
    sid = "stale-uuid-3333"
    sidecar.create_if_absent(tmp_home, sid, default_tags=[], handle="x")
    monkeypatch.setattr("lib.registry.os.kill", lambda pid, sig: (_ for _ in ()).throw(ProcessLookupError()))
    result = doctor.prune_stale_sidecars(tmp_home, dry_run=True)
    assert result["dry_run"] is True
    assert len(result["would_remove"]) == 1
    assert result["removed"] == []
    # File still exists:
    assert sidecar.SidecarPath(tmp_home, sid).path.exists()


def test_prune_removes_stale(tmp_home, monkeypatch):
    sid = "stale-uuid-4444"
    sidecar.create_if_absent(tmp_home, sid, default_tags=[], handle="x")
    monkeypatch.setattr("lib.registry.os.kill", lambda pid, sig: (_ for _ in ()).throw(ProcessLookupError()))
    result = doctor.prune_stale_sidecars(tmp_home, dry_run=False)
    assert result["dry_run"] is False
    assert len(result["removed"]) == 1
    assert not sidecar.SidecarPath(tmp_home, sid).path.exists()


def test_prune_leaves_live_sidecars_alone(tmp_home, monkeypatch):
    live_sid = "live-uuid-5555"
    dead_sid = "dead-uuid-5555"
    _write_registry_entry(tmp_home, pid=99005, session_id=live_sid)
    sidecar.create_if_absent(tmp_home, live_sid, default_tags=[], handle="alive")
    sidecar.create_if_absent(tmp_home, dead_sid, default_tags=[], handle="dead")
    # kill returns None for live pid, raises for everything else.
    def fake_kill(pid, sig):
        if pid == 99005:
            return None
        raise ProcessLookupError()
    monkeypatch.setattr("lib.registry.os.kill", fake_kill)
    result = doctor.prune_stale_sidecars(tmp_home, dry_run=False)
    assert len(result["removed"]) == 1
    # Live one survives, dead one gone:
    assert sidecar.SidecarPath(tmp_home, live_sid).path.exists()
    assert not sidecar.SidecarPath(tmp_home, dead_sid).path.exists()
