#!/usr/bin/env bash

# UserPromptSubmit hook for claude-notifications
# Checks for NEW notifications since last check (avoids re-alerting on old ones)

INBOX_DIR="$HOME/.claude/inbox"
STATE_DIR="$HOME/.claude/inbox-state"
STATE_FILE="$STATE_DIR/$$"

mkdir -p "$INBOX_DIR" "$STATE_DIR"

# If no state file yet (first prompt in session), create one and exit silently
# SessionStart already showed the count
if [ ! -f "$STATE_FILE" ]; then
  date +%s > "$STATE_FILE"
  exit 0
fi

# Read last-check timestamp
LAST_CHECK=$(cat "$STATE_FILE")

# Find .md files newer than last check
NEW_COUNT=0
for f in "$INBOX_DIR"/*.md; do
  [ -f "$f" ] || continue
  FILE_MTIME=$(stat -f %m "$f" 2>/dev/null)
  if [ -n "$FILE_MTIME" ] && [ "$FILE_MTIME" -gt "$LAST_CHECK" ]; then
    NEW_COUNT=$((NEW_COUNT + 1))
  fi
done

# Update timestamp
date +%s > "$STATE_FILE"

if [ "$NEW_COUNT" -gt 0 ]; then
  MSG="You have ${NEW_COUNT} new notification(s) since last check. Use get_notifications to read them."
  ESCAPED=$(printf '%s' "$MSG" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')

  cat << EOF
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": ${ESCAPED}
  }
}
EOF
fi

exit 0
