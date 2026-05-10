"""Per-event filter helper invoked by bin/watch.

Resolves the session's CURRENT handle (so renames mid-watch take effect)
and decides whether the event matches subscriber tags. Output is a single
tab-separated line: `<current_handle>\\t<matches:0|1>`.

Why a Python script instead of bash:
- Handle resolution (look up sessionId → name in registry) is annoying in pure
  bash without jq, and we want to refresh per event (not cache at arm-time).
- Scope matching uses lib.match (fnmatch + path: prefix semantics) — copying
  that logic into bash invites drift from the substrate.
- One Python invocation per file change is cheap (~10ms) compared to fswatch's
  natural event rate.

Usage:
    python3 _watch_filter.py <my_session_id> <scope_json> <home>

Args:
    my_session_id: this session's UUID (for self-author skip + tag lookup)
    scope_json: the thread's scope array as a JSON string (e.g. '["jd/03.14"]')
    home: $HOME (test isolation)

Stdout: <handle>\\t<0-or-1>
  - handle: this session's current handle (may be empty if session_id absent
    from registry)
  - matches: 1 if any of (subscriber tags + implicit handle) matches any
    scope tag per lib.match.match; 0 otherwise

Returns 0 always (errors print empty handle and matches=0 to stdout).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.match import match


def _resolve_handle(home, session_id):
    sessions_dir = Path(home) / ".claude" / "sessions"
    if not sessions_dir.is_dir():
        return ""
    for f in sessions_dir.iterdir():
        if f.suffix != ".json":
            continue
        try:
            d = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if d.get("sessionId") == session_id:
            return d.get("name") or (session_id[:8] if session_id else "")
    return session_id[:8] if session_id else ""


def _read_tags(home, session_id):
    if not session_id:
        return []
    sidecar = Path(home) / ".claude" / "sessions-meta" / f"{session_id}.json"
    if not sidecar.exists():
        return []
    try:
        return list(json.loads(sidecar.read_text()).get("tags", []))
    except (json.JSONDecodeError, OSError):
        return []


def main():
    if len(sys.argv) != 4:
        print("\t0")
        return 0
    session_id, scope_json, home = sys.argv[1], sys.argv[2], sys.argv[3]
    handle = _resolve_handle(home, session_id)
    sub = _read_tags(home, session_id)
    if handle:
        sub.append(handle)  # implicit handle subscription
    try:
        scope = json.loads(scope_json) if scope_json else []
    except json.JSONDecodeError:
        scope = []
    if not isinstance(scope, list):
        scope = []
    matches = 1 if match(sub, scope) else 0
    print(f"{handle}\t{matches}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
