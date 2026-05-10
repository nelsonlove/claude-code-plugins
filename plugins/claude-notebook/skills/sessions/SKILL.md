---
name: sessions
description: List, audit, and clean up Claude Code session files. Shows disk usage, finds orphan directories, stale sessions, and zombie remnants.
user_invocable: true
---

# Session Manager

Audit and clean up Claude Code session files.

## Usage

Run the sessions script:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/bin/sessions.py"
```

This prints a session audit: total sessions, disk usage, orphan directories,
and a breakdown by age and project.

### Options

- `--cleanup` — interactively remove orphan dirs and optionally old sessions
- `--older-than N` — with `--cleanup`, target sessions older than N days (default: 30)
- `--dry-run` — show what would be cleaned up without doing it
- `--stats` — just show disk usage stats

## After the script runs

1. Review the audit output
2. If `--cleanup` was used, confirm the list of items to remove
3. Items are moved to Trash, not permanently deleted
