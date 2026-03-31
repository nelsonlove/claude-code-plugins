#!/usr/bin/env bash

# Inject JD system policy into session context
# POLICY.md lives in dotfiles, symlinked into the JD tree

POLICY_FILE="$HOME/repos/dotfiles/docs/POLICY.md"

if [ ! -f "$POLICY_FILE" ]; then
  exit 0
fi

# Read and escape for JSON
POLICY_CONTENT=$(cat "$POLICY_FILE" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')

cat << EOF
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": ${POLICY_CONTENT}
  }
}
EOF

exit 0
