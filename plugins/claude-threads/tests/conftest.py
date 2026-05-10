"""Shared pytest fixtures for claude-threads tests."""
import json
import os
from pathlib import Path

import pytest


@pytest.fixture
def tmp_home(monkeypatch, tmp_path):
    home = tmp_path / "home"
    (home / ".claude" / "sessions").mkdir(parents=True)
    (home / ".claude" / "sessions-meta").mkdir(parents=True)
    (home / ".claude" / "threads").mkdir(parents=True)
    (home / ".claude" / "threads-state").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.fixture
def threads_dir(tmp_home):
    return tmp_home / ".claude" / "threads"


@pytest.fixture
def write_sidecar(tmp_home):
    """Write a sessions-meta sidecar (claude-identity's territory; we just read it)."""
    def _write(session_id, tags=()):
        path = tmp_home / ".claude" / "sessions-meta" / f"{session_id}.json"
        path.write_text(json.dumps({
            "schema": 1, "session_id": session_id, "tags": list(tags),
            "added": "2026-05-09T00:00:00+0000",
            "modified": "2026-05-09T00:00:00+0000",
        }))
        return path
    return _write


@pytest.fixture
def write_registry_entry(tmp_home):
    def _write(pid, session_id, name=None, cwd="/tmp", status="idle"):
        data = {"pid": pid, "sessionId": session_id, "cwd": cwd,
                "startedAt": 1000000, "version": "2.1.119",
                "kind": "interactive", "entrypoint": "cli",
                "status": status, "updatedAt": 2000000}
        if name is not None:
            data["name"] = name
        path = tmp_home / ".claude" / "sessions" / f"{pid}.json"
        path.write_text(json.dumps(data))
        return path
    return _write
