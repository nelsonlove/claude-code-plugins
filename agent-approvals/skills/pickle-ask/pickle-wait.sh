#!/usr/bin/env bash
# Indefinite waiter that CLAIMS a Pickle request for this live session, so the
# Tickle cold-path skips it while we're alive. Exits when answered (completion
# re-invokes the session to reconcile). The session removes the claim + writes
# the processed marker when it reconciles; a dead session's claim goes stale.
# Usage: pickle-wait.sh <REQID> [session-id]
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/bin:/bin:$PATH"
REQID="${1:?usage: pickle-wait.sh <REQID> [session-id]}"
SID="${2:-${CLAUDE_CODE_SESSION_ID:-}}"
CLAIMS="$HOME/.claude/pickle-state/claims"; mkdir -p "$CLAIMS"
CLAIM="$CLAIMS/$REQID"
printf 'session_id=%s\npid=%s\n' "$SID" "$$" > "$CLAIM"
while :; do
  state=$(pickle show --json "$REQID" 2>/dev/null | python3 -c 'import sys,json;print(json.load(sys.stdin).get("state","?"))' 2>/dev/null || echo "?")
  case "$state" in
    pending|"?") : ;;
    *) echo "answered:$state"; exit 0 ;;
  esac
  touch "$CLAIM"     # heartbeat
  sleep 2
done
