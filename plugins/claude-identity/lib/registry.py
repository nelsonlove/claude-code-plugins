"""Adapter over Claude Code's session registry at $HOME/.claude/sessions/<pid>.json.

CC owns this directory. v0.1.0 was strictly read-only. v0.1.2 added a write
path through CC's `name` field. v0.1.3 decouples: the persistent agent handle
now lives in the sessions-meta sidecar (`lib.sidecar`), independent from CC's
`name` field. The sidecar handle is the canonical source; CC's `name` is read
as a back-compat fallback for sessions that set handle via the v0.1.2 path.

Resolution order: sidecar `handle` → CC registry `name` → UUID-prefix.

Liveness is checked via kill -0 <pid>.
"""
import json
import os
import re
from pathlib import Path

from lib import sidecar


class AmbiguousHandle(Exception):
    def __init__(self, handle, candidates):
        self.handle = handle
        self.candidates = candidates
        super().__init__(f"Handle '{handle}' is ambiguous; candidates: {candidates}")


class InvalidHandle(ValueError):
    """Raised by set_handle for handles that violate validation rules."""


class HandleCollision(Exception):
    """Raised by set_handle when another live session already has that handle."""
    def __init__(self, handle, taken_by_session_id):
        self.handle = handle
        self.taken_by_session_id = taken_by_session_id
        super().__init__(
            f"Handle '{handle}' is already taken by session {taken_by_session_id}"
        )


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


def _handle_for_entry(entry, home):
    """Resolve the handle for a session entry. Order:
      1. sidecar `handle` field (v0.1.3+ canonical)
      2. CC registry `name` field (v0.1.2 back-compat)
      3. UUID-prefix fallback (no handle ever set)
    """
    sid = entry.get("sessionId", "")
    if sid:
        h = sidecar.get_handle(home, sid)
        if h:
            return h
    name = entry.get("name")
    if name:
        return name
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
        entry["handle"] = _handle_for_entry(entry, home)
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
    entry["handle"] = _handle_for_entry(entry, home)
    return entry


def resolve_handle(home, session_id):
    """Given a session UUID, return the handle (sidecar / name / first-8-of-uuid).
    None if no registry entry."""
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
            return _handle_for_entry(entry, home)
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


# ---------------------------------------------------------------------------
# v0.1.3: handle write path (set_handle / /claude-identity:rename).
# v0.1.2 wrote CC's registry `name` field; v0.1.3 writes the sidecar `handle`
# field instead — see module docstring for the resolution-chain rationale.
# ---------------------------------------------------------------------------

# Reserved tokens that would conflict with tag-matching semantics or look
# indistinguishable from system internals. set_handle rejects these.
_RESERVED_HANDLES = frozenset({"*", "all", "any", "none", "self", "external", "unknown"})

# Canonical UUID-prefix shape (8 lowercase hex chars). Rejected as a handle
# to avoid confusion with the auto-default that the absence of a `name` field
# produces — otherwise users could not tell "this session set its own handle"
# from "this session has no handle and is showing the UUID fallback."
_UUID_PREFIX_RE = re.compile(r"^[0-9a-f]{8}$")

# Allowed handle shape: lowercase letters/digits, optional one hyphen-separated
# suffix. Mirrors the bird-name / Docker-style convention from multi-session
# naming discussions (cairn, wren, jd-cli-audit, etc.). 2-32 chars total.
_VALID_HANDLE_RE = re.compile(r"^[a-z][a-z0-9]{1,15}(-[a-z][a-z0-9]{1,15})?$")


def _validate_handle(handle):
    """Normalize + validate a proposed handle. Returns the normalized form."""
    if not isinstance(handle, str):
        raise InvalidHandle(f"handle must be a string, got {type(handle).__name__}")
    h = handle.strip().lower()
    if not h:
        raise InvalidHandle("handle cannot be empty")
    if h in _RESERVED_HANDLES:
        raise InvalidHandle(
            f"'{h}' is a reserved token (would conflict with tag-matching "
            f"or system semantics)"
        )
    if _UUID_PREFIX_RE.match(h):
        raise InvalidHandle(
            f"'{h}' looks like a UUID prefix; would be confusing alongside "
            f"the default first-8 fallback. Pick a word-style name instead."
        )
    if not _VALID_HANDLE_RE.match(h):
        raise InvalidHandle(
            f"'{h}' invalid: use lowercase letters/digits, optionally one "
            f"hyphen-separated suffix, 2-32 chars total"
        )
    return h


def set_handle(home, my_pid, handle):
    """Set the running session's persistent agent handle by writing the
    `handle` field of its sessions-meta sidecar (v0.1.3+).

    Decoupled from CC's `name` field — CC's built-in `/rename` continues to
    control the registry `name` (session topic/focus), while this controls
    the persistent agent handle (`quill`, `wren`, etc.) used by claude-threads,
    `/claude-identity:whoami`, `/claude-identity:sessions`, and downstream
    consumers.

    Validation:
      - handle matches the word-style pattern (see _validate_handle)
      - handle is not reserved (*, all, any, etc.)
      - handle does not look like a UUID prefix
      - no other LIVE session currently has that handle (collision check)

    Returns: dict {ok: True, handle: <normalized>, previous: <prior handle or None>}
    Raises: InvalidHandle, HandleCollision, KeyError (no registry entry for pid)
    """
    h = _validate_handle(handle)
    pid_file = _sessions_dir(home) / f"{my_pid}.json"
    if not pid_file.exists():
        raise KeyError(f"no registry entry for pid {my_pid}")
    entry = _read_entry(pid_file)
    if entry is None:
        raise KeyError(f"could not read registry entry at {pid_file}")
    my_session_id = entry.get("sessionId")
    # Collision check: any OTHER live session with this handle?
    # list_live_sessions already populates `handle` via the sidecar→name→UUID chain.
    for other in list_live_sessions(home):
        if other["sessionId"] == my_session_id:
            continue  # ourselves — re-setting same handle is fine
        if other["handle"] == h:
            raise HandleCollision(h, other["sessionId"])
    # `previous` follows the same resolution chain consumers see: sidecar handle
    # first, fall back to CC's name (legacy v0.1.2 path). Returns None only when
    # neither was set — the session was on the bare UUID-prefix fallback.
    previous = sidecar.get_handle(home, my_session_id) or entry.get("name")
    sidecar.set_handle(home, my_session_id, h)
    return {"ok": True, "handle": h, "previous": previous}
