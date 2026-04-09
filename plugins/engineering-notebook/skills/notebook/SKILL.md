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
2. Resume each session via `claude -p --resume` (in parallel) to get a summary
3. Print a combined journal entry

### Options

- `--date YYYY-MM-DD` — summarize a specific date
- `--project FRAGMENT` — filter to one project
- `--workers N` — parallel summarizers (default: 4)
- `--list-dates` — show all available dates
- `--list-projects` — show all projects
- `--index-only` — show session index without summarizing

## After the script runs

1. Read the output — it contains per-session summaries grouped by project
2. **Synthesize** the raw summaries into a polished journal entry:
   - Merge overlapping sessions into coherent narratives
   - Add a headline (≤10 words)
   - Add topic tags and open questions
   - First person, honest, concise — write for future-you
3. **Ask the user** where to save:
   - **Screen** (default) — just print
   - **File** — write as `YYYY-MM-DD.md` to a directory they specify
   - **Day One** — `dayone-cli create --journal "Engineering" --date YYYY-MM-DD --title "headline" --body "entry"`
