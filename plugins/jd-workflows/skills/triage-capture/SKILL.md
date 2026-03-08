---
name: triage-capture
description: Use when sorting, triaging, or organizing the capture folder, unsorted files, or inbox items into Johnny Decimal categories. Also use when the user says "triage", "sort capture", "process inbox", or asks to organize loose files.
---

# Triage Capture Folder

Sort items from `01.01 Capture - Unsorted` into their correct Johnny Decimal locations.

## Workflow

### 1. Scan and classify

List everything in `~/Documents/00-09 System/01 Capture/01.01 Capture - Unsorted/`. For each item:
- Inspect contents (read files, list directories) to understand what it is
- Propose a JD destination (area, category, and ID)
- Flag ambiguous items for user decision

Present the full classification as a table:

| Item | Type | Proposed destination | Confidence |
|------|------|---------------------|------------|
| ... | file/dir | `XX.XX Description` | high/medium/low |

### 2. Get approval

Wait for the user to review. Do not move anything until explicitly approved. Ask about low-confidence items individually.

### 3. Check for duplicates

Before moving each item, check whether the destination already contains a file with the same name or similar content. Flag conflicts rather than overwriting.

### 4. Move approved items

Use `mv` (never `cp`) to move each item. Use `jd` CLI to resolve destination paths when possible.

If a destination ID directory doesn't exist yet, ask the user before creating it.

### 5. Report

Summarize what was moved, what was skipped, and what remains in the capture folder.

## Rules

- **Never delete** anything from capture — only move it
- **Never overwrite** — flag duplicates for user decision
- **Use `mv`** — never `cp` for file moves
- **No `-f` flag on mv** — let conflicts surface rather than silently overwriting
- **Batch by category** — move all items going to the same category together for cleaner commits if version-controlled
- **Subdirectories in capture** — explore them recursively; they may contain multiple items that sort to different destinations
