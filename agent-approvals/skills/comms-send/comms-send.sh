#!/bin/zsh
# comms-send — the fleet's one interface for messaging the comms agent (or any
# addressee). Wraps pickle so conventions live HERE, not in every agent's prompt:
#   - collection: comms
#   - addressing: to:<handle> tag; sender: from:<handle> tag (pickle message has
#     no --source flag; upstream hardcodes source=callum — see agent-stack patch queue)
#   - future: transparent remote transport (pickle serve over Tailscale) when
#     this machine isn't the collection host. Callers never change.
# Usage: comms-send.sh --title "..." [--message "..."] [--body-file f]
#                      [--to comms] [--from <handle>] [--kind message|ask] [--tag t]...
set -euo pipefail
TO="comms"; FROM="${COMMS_HANDLE:-${CLAUDE_SESSION_HANDLE:-agent}}"; KIND="message"
TITLE=""; MSG=""; BODYFILE=""; EXTRA_TAGS=()
while [ $# -gt 0 ]; do case "$1" in
  --title) TITLE="$2"; shift 2;; --message) MSG="$2"; shift 2;;
  --body-file) BODYFILE="$2"; shift 2;; --to) TO="$2"; shift 2;;
  --from) FROM="$2"; shift 2;; --kind) KIND="$2"; shift 2;;
  --tag) EXTRA_TAGS+=(--tag "$2"); shift 2;;
  *) echo "comms-send: unknown arg $1" >&2; exit 2;;
esac; done
[ -n "$TITLE" ] || { echo "comms-send: --title required" >&2; exit 2; }
ARGS=(--collection comms --title "$TITLE" --tag "to:$TO" --tag "from:$FROM" "${EXTRA_TAGS[@]}")
[ -n "$MSG" ] && ARGS+=(--message "$MSG")
[ -n "$BODYFILE" ] && ARGS+=(--body-file "$BODYFILE")
if [ "$KIND" = "ask" ]; then
  exec pickle ask "${ARGS[@]}" --source "$FROM" --json
else
  exec pickle message "${ARGS[@]}" --json
fi
