---
name: notebook
description: Generate an engineering journal entry from today's Claude Code sessions. Summarizes what you worked on, what shipped, what broke, and open threads.
user_invocable: true
---

# Engineering Notebook

Generate a journal entry from today's Claude Code sessions.

## Usage

Run the notebook script:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/bin/notebook.py"
```

This will:
1. Index all sessions for today by project
2. Check cache — skip sessions already summarized
3. Resume uncached sessions via `claude -p --resume` (in parallel) to get summaries
4. Print a combined journal entry

### Options

- `--date YYYY-MM-DD` — summarize a specific date
- `--project FRAGMENT` — filter to one project
- `--workers N` — parallel summarizers (default: 4)
- `--list-dates` — show all available dates
- `--list-projects` — show all projects
- `--index-only` — show session index with cache status
- `--no-cache` — force re-summarize all sessions
- `--cache-stats` — show cache statistics

## After the script runs

1. Read the output — it contains per-session summaries grouped by project
2. **Synthesize** the raw summaries into a polished journal entry:
   - Merge overlapping sessions into coherent narratives
   - Add a headline (≤10 words)
   - Add topic tags
   - **Open questions** — forks-in-the-road, design calls awaiting more thought
   - **Loose ends** — small atoms that need 30 seconds of action next time:
     uncommitted changes, files in scratch locations, manual steps deferred,
     test contacts/data to clean up, scripts paused mid-execution
   - First person, honest, concise — write for future-you
3. **Save to Day One** — always save to Day One journal "Claude Code". Do not ask the user where to save.

   **Deduplication (important):** Before creating a new entry, check for an existing entry on the same date:
   - Use `mcp__plugin_dayone_dayone-cli__get_entries` with `journal_names: ["Claude Code"]`, `start_date` set to the target date, and `end_date` set to the next day (e.g. for 2026-04-15, use `start_date: "2026-04-15"`, `end_date: "2026-04-16"`).
   - If an entry already exists for that date, use `mcp__plugin_dayone_dayone-cli__update_entry` to **replace** its body with the new synthesized content. Merge any unique content from the old entry that the new summaries don't cover. Preserve the entry's existing tags and add any new ones.
   - If no entry exists, use `mcp__plugin_dayone_dayone-cli__create_entry` to create one.

   **Entry format:**
   - Date: ISO8601 with time component (e.g. `2026-04-15T12:00:00Z`). Bare dates like `2026-04-15` will be rejected.
   - `all_day: true`
   - Tags: relevant topic tags from the entry
