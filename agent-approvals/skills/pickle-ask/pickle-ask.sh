#!/usr/bin/env bash
# pickle-ask: file a Pickle request with a session/handoff join, print the REQID.
# The caller then launches `pickle wait <REQID>` as a background task (no timeout).
#
# Usage:
#   pickle-ask --title "..." --message "..." [pickle ask flags] \
#              [--session-id <id>] [--ops-handoff <path>]
set -euo pipefail

# Default to the current Claude Code session so a cold resume can target it,
# and to the current dir so the resume launches with the right project settings.
SESSION_ID="${CLAUDE_CODE_SESSION_ID:-}"
OPS_HANDOFF=""
CWD="$PWD"
ASK_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --session-id)  SESSION_ID="${2:-}"; shift 2 ;;
    --ops-handoff) OPS_HANDOFF="${2:-}"; shift 2 ;;
    --cwd)         CWD="${2:-}"; shift 2 ;;
    *)             ASK_ARGS+=("$1"); shift ;;
  esac
done

META="$(mktemp -t pickle-ask-meta.XXXXXX.json)"
trap 'rm -f "$META"' EXIT
python3 - "$SESSION_ID" "$OPS_HANDOFF" "$CWD" >"$META" <<'PY'
import sys, json
sid, handoff, cwd = sys.argv[1], sys.argv[2], sys.argv[3]
m = {"workflow": "pickle-ask"}
if sid:     m["session_id"] = sid
if handoff: m["ops_handoff"] = handoff
if cwd:     m["cwd"] = cwd
print(json.dumps(m))
PY

# `pickle ask` prints the created request id on the last line.
REQID="$(pickle ask "${ASK_ARGS[@]}" --metadata "$META" | tail -1)"
echo "$REQID"
