"""Watcher state machine for per-agent live notes.

Detects user-edits to an agent's live note by comparing the file's current
`modified:` frontmatter value against the watermark the agent recorded after
its last write (stored in the sessions-meta sidecar).

Cooperates with lib.live_note: every write_live_note() call updates the
watermark after writing, so subsequent changes to `modified:` are by
definition not from the agent.

Used by bin/watch-live (the long-running monitor script).
"""
from pathlib import Path

from lib import sidecar
from lib.live_note import (
    LIVE_NOTES_SUBPATH,
    read_modified_field,
    resolve_note_path,
    resolve_vault_path,
)


def current_modified(vault, handle):
    """Read the live note file and return its `modified:` value, or None if
    the file doesn't exist or has no frontmatter."""
    path = resolve_note_path(vault, handle)
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return read_modified_field(text)


def detect_user_edit(home, session_id, handle, vault=None):
    """Compare the live note's current `modified:` against the watermark.

    Returns a dict:
      - {"changed": False, "current": <str-or-None>}  — no user edit
      - {"changed": True, "current": <str>, "previous": <str-or-None>}
        — user edited; caller should emit an event and update the watermark
        via accept_change() once handled.
    """
    if vault is None:
        vault = resolve_vault_path()
    cur = current_modified(vault, handle)
    seen = sidecar.get_live_note_seen_modified(home, session_id)
    if cur is None:
        # Note doesn't exist yet (or no frontmatter); nothing to compare.
        return {"changed": False, "current": None}
    if seen is None:
        # No watermark recorded — the agent hasn't written through this watcher's
        # write_live_note yet. Treat the current value as baseline (no event).
        return {"changed": False, "current": cur}
    if cur == seen:
        return {"changed": False, "current": cur}
    return {"changed": True, "current": cur, "previous": seen}


def accept_change(home, session_id, new_modified):
    """Record the new `modified:` value as the watermark, so we don't keep
    firing for the same edit. Called after the watcher emits an event."""
    sidecar.set_live_note_seen_modified(home, session_id, new_modified)
