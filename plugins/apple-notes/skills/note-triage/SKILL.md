---
name: note-triage
description: Use when the user asks to triage, clean up, organize, or audit their Apple Notes. Also use when they mention "notes triage", "clean up notes", "sort notes", or reference the Apple Notes audit.
---

# Apple Notes Triage

## Overview

Guide the user through batch cleanup of Apple Notes. The 06.13 audit identified 741 notes with ~308 stuck in capture purgatory (01 Inbox, Notes default folder). Work through notes in batches of ~20, proposing actions for each.

## Workflow

### 1. Target Selection

Ask the user which folder to triage, or default to the worst offenders:
- "Notes" (default folder) — 95 unsorted notes
- "01 Inbox" — 213 unsorted notes

Use `list_folders` to show current folder state.

### 2. Batch Pull

Use `list_notes` with:
- `folder` — the target folder
- `limit: 20` — batch size
- `sort_by: "modified"`, `order: "asc"` — oldest first (stalest = most likely to delete/archive)

### 3. Analyze Each Note

For each note in the batch, use `get_note` to read content. Classify:

| Action | Criteria | Execution |
|--------|----------|-----------|
| **Delete** | Empty, near-empty (≤5 chars), "New Note" stub, duplicate title, obviously scratch | `delete_note` (moves to Recently Deleted, 30-day recovery) |
| **Archive** | Valuable content but stale; belongs in JD tree as Markdown | `export_note` → save to JD path via `jd` CLI → `delete_note` |
| **Keep + Refolder** | Active/useful but in wrong folder | `move_note` to correct folder |
| **Keep as-is** | Active, ephemeral, or already well-placed | No action |

### 4. Present Batch

Show a table of the batch with proposed actions:

```
| # | Title                    | Modified   | Chars | Action       | Destination          |
|---|--------------------------|------------|-------|--------------|----------------------|
| 1 | New Note                 | 2021-03-14 | 0     | Delete       | —                    |
| 2 | Adelphi syllabus draft   | 2021-07-05 | 2340  | Archive      | 52.01 Unsorted       |
| 3 | Shopping list            | 2025-12-01 | 45    | Keep+Refolder| 31.04 Inventories    |
```

Ask user to approve, modify, or skip individual items.

### 5. Execute

Process approved actions. For archives:
1. `export_note` to get Markdown
2. Write to temp file
3. Use `jd` CLI to file: `jd mv /tmp/note.md <JD-ID>`
4. `delete_note` to remove from Notes

Report results: successes, failures, skipped.

### 6. Next Batch

After each batch, show progress (X of Y notes in folder processed) and ask if user wants to continue.

## Integration with JD

When archiving, determine the target JD ID based on note content and folder:
- Notes in "52 Adelphi University" → archive to `52.xx` in JD tree
- Notes in "26.02 Notes" → archive to `26.xx` in JD tree
- Notes in "73.06 LLM outputs" → archive to `73.06` in JD tree
- Generic/unsorted → file to category unsorted (`xx.01`) in the best-fit area

Use `jd find` or `jd ls` to verify target IDs exist before filing.

## Safety

- Delete moves to Recently Deleted (30-day recovery window)
- Never delete locked/password-protected notes
- Always show the batch and get approval before executing
- Archive exports the note to Markdown BEFORE deleting from Notes
- Report failures without stopping the batch
