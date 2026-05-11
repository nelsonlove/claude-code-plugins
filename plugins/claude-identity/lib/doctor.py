"""Maintenance: identify and prune stale state in claude-identity's sidecars.

Stale sidecar = a `~/.claude/sessions-meta/<session-id>.json` whose `session_id`
no longer corresponds to a live entry in `~/.claude/sessions/<pid>.json`. These
accumulate as sessions end (CC doesn't reap them); they then interfere with
SessionStart's handle-collision check (block live sessions from picking their
deterministic word).
"""
import json
import os
from pathlib import Path

from lib import registry, sidecar


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


def prune_stale_sidecars(home, dry_run=False):
    """Remove stale sidecars. Returns dict {removed: [<path>], dry_run: bool}.

    When `dry_run=True`, lists what would be removed without touching anything.
    """
    candidates = find_stale_sidecars(home)
    removed = []
    if not dry_run:
        for c in candidates:
            try:
                os.unlink(c["path"])
                removed.append(c["path"])
            except OSError:
                pass
    return {
        "removed": removed if not dry_run else [],
        "would_remove": [c["path"] for c in candidates] if dry_run else [],
        "stale": candidates,
        "dry_run": dry_run,
    }
