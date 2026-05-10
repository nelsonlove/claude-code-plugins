"""Inline helper invoked by the 3 hook scripts."""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import config
from lib.identity_client import discover_my_session_id
from lib.poll import poll_for_session


def run(hook_event):
    home = os.path.expanduser("~")
    cfg = config.load_config(home=home, project_root=os.getcwd())
    threads_dir = cfg["threads_dir"]

    # Resolve session id. CC sets CLAUDE_SESSION_ID for hooks; if missing,
    # fall back to parent PID (the CC session is our parent, since the bash
    # wrapper exec's into python).
    sid = os.environ.get("CLAUDE_SESSION_ID") or discover_my_session_id(home, os.getppid())
    if sid is None:
        sys.exit(0)  # no registry; bail silent

    state_dir = Path(home) / ".claude" / "threads-state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / f"{sid}.json"

    # Read state: last_poll watermark + seen_modified per-thread map
    last_poll = 0
    seen_modified = {}
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text())
            last_poll = state.get("last_poll", 0)
            seen_modified = state.get("seen_modified", {}) or {}
        except (json.JSONDecodeError, OSError):
            pass

    # Poll. seen_modified is updated in-place by poll_for_session.
    try:
        result = poll_for_session(
            home=home, session_id=sid, threads_dir=threads_dir,
            last_poll_epoch=last_poll, seen_modified=seen_modified,
        )
    except Exception as e:
        print(f"claude-threads {hook_event}: {e}", file=sys.stderr)
        sys.exit(0)  # fail silent

    # Persist updated state BEFORE emitting (so concurrent hooks don't double-surface)
    try:
        with state_file.open("w") as f:
            json.dump({
                "last_poll": time.time(),
                "seen_modified": result.get("seen_modified") or {},
            }, f)
    except OSError as e:
        print(f"claude-threads {hook_event}: state write {e}", file=sys.stderr)

    # Emit additionalContext if matches
    matches = result["new_matches"]
    if matches:
        snippet_lines = [
            f"- **{m['thread_id']}** [{m['status'] if 'status' in m else 'open'}] {m['title']} (from {m['opener']}, scope={m['scope']})"
            for m in matches
        ]
        msg = (
            f"You have {len(matches)} new thread(s) matching your subscribed scope. "
            f"Use `/thread:show <id>` to read or `/thread:reply <id> <msg>` to respond.\n\n"
            + "\n".join(snippet_lines)
        )
        out = {
            "hookSpecificOutput": {
                "hookEventName": hook_event,
                "additionalContext": msg
            }
        }
        print(json.dumps(out))
    sys.exit(0)


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "Unknown")
