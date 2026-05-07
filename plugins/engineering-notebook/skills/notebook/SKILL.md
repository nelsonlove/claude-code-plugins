---
name: notebook
description: Save a Day One journal entry summarizing the current conversation. Captures what shipped, what broke, key decisions, and loose ends. Use when wrapping up a session.
user_invocable: true
---

# Engineering Notebook

Save a Day One entry summarizing **the current conversation**. The assistant already has full session context; no subprocess, no `claude --resume`.

## What to do

### 1. Synthesize the conversation into a journal entry

- **Headline** (≤10 words) — the main thing accomplished. Becomes the entry's H1.
- **Body** — first person, honest, concise; write for future-you. Cover:
  - What was the goal
  - What shipped (concrete artifacts, files, PRs, commits)
  - What broke and what you learned
  - Key decisions made
  - **Open questions** — forks in the road, design calls deferred for more thought
  - **Loose ends** — small atoms that need 30 seconds next time: uncommitted changes, files in scratch dirs (`/tmp/*`, `~/Desktop/*`), manual steps deferred, scripts paused mid-run, test data to clean up
- **Tags line** at the bottom: 3–7 relevant topic tags

### 2. Save to Day One

Use the `dayone2` CLI. Journal is **`Claude Code`**.

```bash
cat <<'EOF' | dayone2 -j "Claude Code" -d "$(date '+%Y-%m-%d %H:%M')" -t tag1 tag2 tag3 -- new
# Headline

Body…

**Tags:** tag1, tag2, tag3
EOF
```

Notes:

- Pipe the body via stdin (heredoc) — keeps backticks, asterisks, and long bodies safe from shell interpretation.
- Date format `YYYY-MM-DD HH:MM` is local time; `dayone2` accepts that without seconds or timezone.
- The `--` before `new` ends the tag list.
- Don't ask the user where to save — Day One, journal "Claude Code", always.

### 3. Confirm

Briefly tell the user the entry was saved (one short sentence with the headline).

## Scope

This skill summarizes **only the current session**. To backfill a past session:

- Read the relevant JSONL at `~/.claude/projects/<encoded-project-dir>/<session-id>.jsonl` directly with the `Read` tool, then synthesize and push as above.
- Use the `sessions` skill (`bin/sessions.py`) to find session IDs by date or audit disk usage.
