"""Shared pytest fixtures for claude-identity tests."""
import json
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_home(monkeypatch, tmp_path):
    """Provide an isolated $HOME for tests so we don't touch the real ~/.claude."""
    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude").mkdir()
    (home / ".claude" / "sessions").mkdir()
    (home / ".claude" / "sessions-meta").mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.fixture
def sample_registry_entry(tmp_home):
    """Write a sample CC session registry entry under tmp_home."""
    def _write(pid=12345, session_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
               name=None, status="idle", cwd="/tmp"):
        data = {
            "pid": pid,
            "sessionId": session_id,
            "cwd": cwd,
            "startedAt": 1000000,
            "version": "2.1.119",
            "kind": "interactive",
            "entrypoint": "cli",
            "status": status,
            "updatedAt": 2000000,
        }
        if name is not None:
            data["name"] = name
        path = tmp_home / ".claude" / "sessions" / f"{pid}.json"
        path.write_text(json.dumps(data))
        return path
    return _write
