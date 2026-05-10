"""Read-only access to claude-identity's sessions-meta sidecar.

We deliberately do NOT import claude-identity as a Python module — plugins are
independent. We just read its files. The contract is the JSON schema documented
in claude-identity plugin design.md.
"""
import json
import os
from pathlib import Path


def _sessions_meta(home, session_id):
    return Path(home) / ".claude" / "sessions-meta" / f"{session_id}.json"


def _sessions_dir(home):
    return Path(home) / ".claude" / "sessions"


def read_session_tags(home, session_id):
    """Return the session's subscription tags. Empty list if sidecar absent or corrupt."""
    p = _sessions_meta(home, session_id)
    if not p.exists():
        return []
    try:
        return list(json.loads(p.read_text()).get("tags", []))
    except (json.JSONDecodeError, OSError):
        return []


def read_session_handle(home, session_id):
    """Read the handle from CC's registry: the `name` field, falling back to first-8."""
    for f in _sessions_dir(home).iterdir():
        if not f.suffix == ".json":
            continue
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("sessionId") == session_id:
            name = data.get("name")
            if name:
                return name
            return session_id[:8]
    return session_id[:8]  # fallback if not in live registry


def discover_my_session_id(home, my_pid):
    """Resolve the running process's session UUID via its PID."""
    p = _sessions_dir(home) / f"{my_pid}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text()).get("sessionId")
    except (json.JSONDecodeError, OSError):
        return None
