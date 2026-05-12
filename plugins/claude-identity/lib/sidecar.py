"""Sessions-meta sidecar CRUD.

State at $HOME/.claude/sessions-meta/<sessionId>.json. Schema version 1:
  {
    "schema": 1,
    "session_id": "<uuid>",
    "tags": ["...", ...],
    "handle": "<str-or-absent>",
    "added": "<iso8601>",
    "modified": "<iso8601>"
  }

The `handle` field (added in v0.1.3) holds the persistent agent name —
decoupled from CC's `name` field in the registry, which is reserved for
the session's current-task/topic label set via CC's built-in `/rename`.
`set_handle` writes to the sidecar; `get_handle` reads from it.

Writes are atomic via os.replace from a tmp file. Idempotent operations (e.g.
adding an existing tag, setting handle to the current value) are no-ops and
do NOT bump mtime — required by the mtime-pull change-detection contract.
"""
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = 1


class SidecarPath:
    def __init__(self, home, session_id):
        self.path = Path(home) / ".claude" / "sessions-meta" / f"{session_id}.json"


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S%z")


def _read_or_empty(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _atomic_write(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, str(path))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def create_if_absent(home, session_id, default_tags, handle=None):
    """Initialize a sidecar if it doesn't exist. Return True if created, False if no-op.

    `handle` (optional, v0.1.3+) seeds the persistent agent name. Omit to defer.
    """
    path = SidecarPath(home, session_id).path
    if path.exists():
        return False
    ts = _now_iso()
    data = {
        "schema": SCHEMA_VERSION,
        "session_id": session_id,
        "tags": list(default_tags),
        "added": ts,
        "modified": ts,
    }
    if handle is not None:
        data["handle"] = handle
    _atomic_write(path, data)
    return True


def read_sidecar(home, session_id):
    """Read and return the sidecar dict, or None if absent or corrupt."""
    return _read_or_empty(SidecarPath(home, session_id).path)


def list_tags(home, session_id):
    data = read_sidecar(home, session_id)
    if not data:
        return []
    return list(data.get("tags", []))


def add_tag(home, session_id, tag):
    """Append tag; idempotent. Returns True if added (and mtime bumped), False if no-op."""
    path = SidecarPath(home, session_id).path
    data = _read_or_empty(path)
    if data is None:
        # Auto-init then add
        create_if_absent(home, session_id, default_tags=[tag])
        return True
    if tag in data.get("tags", []):
        return False  # idempotent: no mtime bump
    data["tags"] = list(data.get("tags", [])) + [tag]
    data["modified"] = _now_iso()
    _atomic_write(path, data)
    return True


def remove_tag(home, session_id, tag):
    """Remove tag; idempotent. Returns True if removed, False if absent (no mtime bump)."""
    path = SidecarPath(home, session_id).path
    data = _read_or_empty(path)
    if data is None:
        return False
    tags = list(data.get("tags", []))
    if tag not in tags:
        return False
    tags.remove(tag)
    data["tags"] = tags
    data["modified"] = _now_iso()
    _atomic_write(path, data)
    return True


def get_handle(home, session_id):
    """Return the persistent agent handle from the sidecar, or None if absent."""
    data = read_sidecar(home, session_id)
    if not data:
        return None
    return data.get("handle")


def get_live_note_seen_body_hash(home, session_id):
    """Return the last-known body sha256 of the agent's live note, or None.

    Watermark stored after each write_live_note call so the watcher can detect
    user-edits without false positives from Obsidian Linter rewriting
    frontmatter timestamps.
    """
    data = read_sidecar(home, session_id)
    if not data:
        return None
    return data.get("live_note_seen_body_hash")


def set_live_note_seen_body_hash(home, session_id, value):
    """Update the body-hash watermark. Idempotent. Returns True if changed."""
    path = SidecarPath(home, session_id).path
    data = _read_or_empty(path)
    if data is None:
        ts = _now_iso()
        data = {"schema": SCHEMA_VERSION, "session_id": session_id, "tags": [],
                "added": ts, "modified": ts}
    if data.get("live_note_seen_body_hash") == value:
        return False
    data["live_note_seen_body_hash"] = value
    data["modified"] = _now_iso()
    _atomic_write(path, data)
    return True


def set_handle(home, session_id, handle):
    """Set the persistent agent handle on the sidecar. Returns True if changed,
    False if no-op (handle already matches; mtime preserved per mtime-pull contract).

    Auto-creates the sidecar if absent. Caller is responsible for validating
    the handle string (collision check, format) — see lib.registry.set_handle
    which wraps this with validation + write-through.
    """
    path = SidecarPath(home, session_id).path
    data = _read_or_empty(path)
    if data is None:
        # Auto-init with handle present from the start
        return create_if_absent(home, session_id, default_tags=[], handle=handle)
    if data.get("handle") == handle:
        return False  # idempotent: no mtime bump
    data["handle"] = handle
    data["modified"] = _now_iso()
    _atomic_write(path, data)
    return True
