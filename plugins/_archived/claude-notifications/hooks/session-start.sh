#!/usr/bin/env bash

# SessionStart hook for claude-notifications
# Checks ~/.claude/inbox/ for pending notifications and injects context

INBOX_DIR="$HOME/.claude/inbox"
STATE_DIR="$HOME/.claude/inbox-state"

# Ensure dirs exist
mkdir -p "$INBOX_DIR" "$STATE_DIR"

# Prune stale state files from dead sessions
for sf in "$STATE_DIR"/*; do
  [ -f "$sf" ] || continue
  pid=$(basename "$sf")
  if ! kill -0 "$pid" 2>/dev/null; then
    rm -f "$sf"
  fi
done

# Count pending .md files
count=$(find "$INBOX_DIR" -maxdepth 1 -name '*.md' -type f 2>/dev/null | wc -l | tr -d ' ')

# Record current timestamp for UserPromptSubmit to compare against
date +%s > "$STATE_DIR/$$"

if [ "$count" -gt 0 ]; then
  MSG="You have ${count} pending notification(s) in the inbox. Use get_notifications to read them, or dismiss_notification to clear them. The user can also run /inbox."
  ESCAPED=$(printf '%s' "$MSG" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')

  cat << EOF
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": ${ESCAPED}
  }
}
EOF
fi

exit 0
