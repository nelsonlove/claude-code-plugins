"""Watcher state machine for per-agent live notes.

Detects user-edits to an agent's live note by comparing the file's current
body hash against the watermark the agent recorded after its last write
(stored in the sessions-meta sidecar's `live_note_seen_body_hash` field).

Cooperates with lib.live_note: every write_live_note() call updates the
watermark after writing. The watermark is a sha256 of everything AFTER the
closing `---` of frontmatter, so Obsidian Linter rewriting `modified:` or
re-formatting frontmatter doesn't trigger false positives — only edits
within the message sections do.

Used by bin/watch-live (the long-running monitor script).
"""
from lib import sidecar
from lib.live_note import (
    body_hash,
    resolve_note_path,
    resolve_vault_path,
)


def current_body_hash(vault, handle):
    """Read the live note file and return its body sha256, or None if absent."""
    path = resolve_note_path(vault, handle)
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return body_hash(text)


def detect_user_edit(home, session_id, handle, vault=None):
    """Compare the live note's current body hash against the watermark.

    Returns a dict:
      - {"changed": False, "current": <hash-or-None>}  — no user edit
      - {"changed": True, "current": <hash>, "previous": <hash-or-None>}
        — user edited; caller should emit an event and call accept_change()
        once handled to update the watermark.
    """
    if vault is None:
        vault = resolve_vault_path()
    cur = current_body_hash(vault, handle)
    seen = sidecar.get_live_note_seen_body_hash(home, session_id)
    if cur is None:
        # Note doesn't exist yet; nothing to compare.
        return {"changed": False, "current": None}
    if seen is None:
        # No watermark recorded — the agent hasn't written through write_live_note
        # yet. Treat current as baseline (no event).
        return {"changed": False, "current": cur}
    if cur == seen:
        return {"changed": False, "current": cur}
    return {"changed": True, "current": cur, "previous": seen}


def accept_change(home, session_id, new_hash):
    """Record the new body hash as the watermark, so we don't keep firing for
    the same edit. Called after the watcher emits an event."""
    sidecar.set_live_note_seen_body_hash(home, session_id, new_hash)
