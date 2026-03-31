#!/usr/bin/env bash

# On session end, spawn a background Claude to summarize the transcript
# and append an activity log entry to ACTIVITY.md if notable work was done.

LOG_FILE="$HOME/Documents/00-09 System-management area/00 System-management category/00.00 JDex for the system/ACTIVITY.md"
INPUT=$(cat)
TRANSCRIPT=$(echo "$INPUT" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('transcript_path',''))" 2>/dev/null)

if [ -z "$TRANSCRIPT" ] || [ ! -f "$TRANSCRIPT" ]; then
  exit 0
fi

(
  claude --print --model sonnet -p "You are a session logger. Read the session transcript below and decide if anything notable was done — files created or modified, features built, configs changed, bugs fixed, content organized, etc.

If YES, append a single markdown entry to the file at:
  $LOG_FILE

Use this exact format:

## $(date +%Y-%m-%d) — Short description

- What was done
- Files created or modified (with paths)
- Any follow-up needed

Rules:
- Be concise. Each bullet should be one line.
- Include file paths where relevant.
- If the session was just Q&A, exploration, or conversation with no real changes to files or systems, do NOT append anything.
- Do NOT modify existing entries in the file.
- Do NOT create the file if it doesn't exist.
- Append at the very end of the file.

Session transcript:" < "$TRANSCRIPT" > /dev/null 2>&1
) &

exit 0
