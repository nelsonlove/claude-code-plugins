#!/usr/bin/env bash
# claude-identity SessionStart hook.
# Initializes the sessions-meta sidecar for this session if absent. Idempotent.
#
# Per spec, distinct script name (not the generic session-start.sh) avoids the
# cross-plugin dedup bug at https://github.com/anthropics/claude-code/issues/29724

set -u

HOME_DIR="${HOME}"
SESSIONS_DIR="$HOME_DIR/.claude/sessions"
META_DIR="$HOME_DIR/.claude/sessions-meta"
mkdir -p "$META_DIR"

# Resolve session UUID. Per Phase 0 verification, either:
#   - $CLAUDE_SESSION_ID is set in the env (preferred)
#   - We look up via PID -> ~/.claude/sessions/<pid>.json
SESSION_ID="${CLAUDE_SESSION_ID:-}"
if [ -z "$SESSION_ID" ]; then
  PID_FILE="$SESSIONS_DIR/$$.json"
  if [ ! -f "$PID_FILE" ]; then
    exit 0  # no registry yet; CC hasn't written; bail silent
  fi
  SESSION_ID=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('sessionId',''))" "$PID_FILE" 2>/dev/null)
  if [ -z "$SESSION_ID" ]; then
    exit 0
  fi
fi

META_FILE="$META_DIR/$SESSION_ID.json"
if [ -f "$META_FILE" ]; then
  exit 0  # already initialized
fi

# Read default_tags from $PWD/.claude/claude-identity.local.md if present
PROJECT_CONFIG="$PWD/.claude/claude-identity.local.md"

# Make lib.wordlist importable from the embedded Python below.
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
export PYTHONPATH="$PLUGIN_ROOT${PYTHONPATH:+:$PYTHONPATH}"

python3 - "$SESSION_ID" "$META_FILE" "$PROJECT_CONFIG" <<'PYEOF'
import json, os, re, sys
from datetime import datetime, timezone

session_id, meta_file, project_config = sys.argv[1], sys.argv[2], sys.argv[3]

default_tags = []
if os.path.isfile(project_config):
    try:
        text = open(project_config).read()
        m = re.match(r'^---\n(.*?)\n---', text, re.DOTALL)
        if m:
            tag_match = re.search(r'^default_tags:\s*\[(.*?)\]', m.group(1), re.MULTILINE)
            if tag_match:
                default_tags = [
                    t.strip().strip('"').strip("'")
                    for t in tag_match.group(1).split(",") if t.strip()
                ]
    except Exception:
        pass

# v0.1.3: auto-assign a handle from the wordlist. Deterministic on session_id,
# so reconnects to the same UUID get the same name. Fall through silently if
# the wordlist module isn't importable for some reason — sidecar still gets
# created, just without an auto-handle.
#
# Collision check: hash collisions in the wordlist would otherwise produce two
# live sessions with the same handle (and overwriting live notes). Scan other
# live sidecars before claiming the word; if another session already has it,
# fall through to UUID-prefix default. Cheap O(n_sessions) check at boot.
handle = None
try:
    from lib.wordlist import pick_handle
    candidate = pick_handle(session_id)
    if candidate:
        meta_dir = os.path.dirname(meta_file)
        taken = False
        try:
            for f in os.listdir(meta_dir):
                if not f.endswith(".json"):
                    continue
                p = os.path.join(meta_dir, f)
                # Skip our own (we haven't written it yet, but be defensive)
                if os.path.realpath(p) == os.path.realpath(meta_file):
                    continue
                try:
                    other = json.load(open(p))
                except Exception:
                    continue
                if other.get("handle") == candidate:
                    taken = True
                    break
        except FileNotFoundError:
            pass  # meta_dir doesn't exist yet — first session, no collisions
        if not taken:
            handle = candidate
except Exception:
    pass

ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S%z")
data = {"schema": 1, "session_id": session_id, "tags": default_tags,
        "added": ts, "modified": ts}
if handle:
    data["handle"] = handle

import tempfile
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(meta_file),
                          prefix=f".{os.path.basename(meta_file)}.", suffix=".tmp")
try:
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, meta_file)
except Exception as e:
    print(f"claude-identity hook: {e}", file=sys.stderr)
    try:
        os.unlink(tmp)
    except Exception:
        pass
    sys.exit(0)  # fail silent
PYEOF

exit 0
