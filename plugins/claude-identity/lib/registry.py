"""Read-only adapter over Claude Code's session registry at $HOME/.claude/sessions/<pid>.json.

CC owns this directory; we never write to it. The 'name' field is set by /rename.
Liveness is checked via kill -0 <pid>.
"""
import json
import os
from pathlib import Path


class AmbiguousHandle(Exception):
    def __init__(self, handle, candidates):
        self.handle = handle
        self.candidates = candidates
        super().__init__(f"Handle '{handle}' is ambiguous; candidates: {candidates}")


def _sessions_dir(home):
    return Path(home) / ".claude" / "sessions"


def _read_entry(path: Path):
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _is_alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (ProcessLookupError, PermissionError, ValueError):
        return False


def _handle_for_entry(entry):
    name = entry.get("name")
    if name:
        return name
    sid = entry.get("sessionId", "")
    return sid[:8] if sid else ""


def list_live_sessions(home):
    """Yield session entries (dicts) for live sessions, with `handle` field added."""
    out = []
    d = _sessions_dir(home)
    if not d.is_dir():
        return out
    for f in d.iterdir():
        if not f.name.endswith(".json"):
            continue
        entry = _read_entry(f)
        if entry is None:
            continue
        pid = entry.get("pid")
        if pid is None or not _is_alive(pid):
            continue
        entry["handle"] = _handle_for_entry(entry)
        out.append(entry)
    return out


def find_my_session(home, my_pid):
    """Find the registry entry for the running process by PID. Returns None if absent."""
    f = _sessions_dir(home) / f"{my_pid}.json"
    if not f.exists():
        return None
    entry = _read_entry(f)
    if entry is None:
        return None
    entry["handle"] = _handle_for_entry(entry)
    return entry


def resolve_handle(home, session_id):
    """Given a session UUID, return the handle (name or first-8-of-uuid). None if not found."""
    d = _sessions_dir(home)
    if not d.is_dir():
        return None
    for f in d.iterdir():
        if not f.name.endswith(".json"):
            continue
        entry = _read_entry(f)
        if entry is None:
            continue
        if entry.get("sessionId") == session_id:
            return _handle_for_entry(entry)
    return None


def resolve_handle_or_uuid_to_session_id(home, identifier):
    """Accept handle, full UUID, or 8-char prefix. Return the full sessionId.

    Raises AmbiguousHandle if multiple matches; KeyError if none.
    """
    entries = list_live_sessions(home)

    # Exact UUID match
    for e in entries:
        if e["sessionId"] == identifier:
            return e["sessionId"]

    # Handle match (name or first-8)
    matches = [e for e in entries if e["handle"] == identifier]
    if len(matches) == 1:
        return matches[0]["sessionId"]
    if len(matches) > 1:
        raise AmbiguousHandle(identifier, [m["sessionId"] for m in matches])

    # UUID prefix (length >= 4)
    if len(identifier) >= 4:
        matches = [e for e in entries if e["sessionId"].startswith(identifier)]
        if len(matches) == 1:
            return matches[0]["sessionId"]
        if len(matches) > 1:
            raise AmbiguousHandle(identifier, [m["sessionId"] for m in matches])

    raise KeyError(f"No live session matches '{identifier}'")
