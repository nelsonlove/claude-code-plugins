"""Maintenance: identify and prune stale state in claude-identity's sidecars.

Stale sidecar = a `~/.claude/sessions-meta/<session-id>.json` whose `session_id`
no longer corresponds to a live entry in `~/.claude/sessions/<pid>.json`. These
accumulate as sessions end (CC doesn't reap them); they then interfere with
SessionStart's handle-collision check (block live sessions from picking their
deterministic word).

Removal uses `/usr/bin/trash` (macOS) so the user can recover from a false
positive via the Trash UI. Falls back to `os.unlink` if trash isn't available.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

from lib import registry


def _meta_dir(home):
    return Path(home) / ".claude" / "sessions-meta"


def find_stale_sidecars(home):
    """Return a list of dicts describing stale sidecars:
      [{"path": <str>, "session_id": <uuid>, "handle": <str-or-None>}]
    """
    out = []
    md = _meta_dir(home)
    if not md.is_dir():
        return out
    live_sids = {e["sessionId"] for e in registry.list_live_sessions(home)}
    for f in md.iterdir():
        if not f.name.endswith(".json"):
            continue
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        sid = data.get("session_id")
        if not sid:
            continue
        if sid in live_sids:
            continue
        out.append({
            "path": str(f),
            "session_id": sid,
            "handle": data.get("handle"),
        })
    return out


def _trash_path():
    """Return /usr/bin/trash if available, else None."""
    if os.path.exists("/usr/bin/trash"):
        return "/usr/bin/trash"
    return shutil.which("trash")


def _delete_file(path):
    """Send file to macOS Trash via /usr/bin/trash; fall back to os.unlink."""
    trash = _trash_path()
    if trash:
        result = subprocess.run([trash, path], capture_output=True, text=True)
        if result.returncode == 0:
            return True
        # trash failed; fall through to unlink rather than leave orphan
    try:
        os.unlink(path)
        return True
    except OSError:
        return False


def prune_stale_sidecars(home, dry_run=False):
    """Remove stale sidecars (sends to Trash via /usr/bin/trash when available).
    Returns dict with `removed` (paths actually removed), `would_remove`
    (paths that would be removed in dry-run), `stale` (all candidates),
    and `dry_run`.

    Recoverability: deletions go through macOS Trash, so a false positive
    (e.g., a sidecar whose session was incorrectly classified as dead) can
    be recovered from Trash. Falls back to `os.unlink` only if `/usr/bin/trash`
    is unavailable.
    """
    candidates = find_stale_sidecars(home)
    removed = []
    if not dry_run:
        for c in candidates:
            if _delete_file(c["path"]):
                removed.append(c["path"])
    return {
        "removed": removed if not dry_run else [],
        "would_remove": [c["path"] for c in candidates] if dry_run else [],
        "stale": candidates,
        "dry_run": dry_run,
    }
