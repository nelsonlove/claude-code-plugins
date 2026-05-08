---
name: notebook
description: Save a Claude Code engineering-journal entry into the JD vault's .07 standard zero — daily note for the relevant category. Captures what shipped, what broke, key decisions, and loose ends. Use when wrapping up a session.
user_invocable: true
---

# Engineering Notebook

Save the current Claude Code session as an entry in the JD vault's `.07 Claude Code notebook for [scope]` slot for the relevant category. Daily-note format — sessions for the same category on the same day accumulate as `## HH:MM — <headline>` sections within a single dated file.

See [[Engineering notebook — .07 standard zero design]] in the vault (`92023.10 Requirements & design/`) for the convention.

## What to do

### 1. Synthesize the entry

- **Headline** (≤10 words) — the main thing accomplished. Becomes the section heading.
- **Body** — first person, honest, concise; write for future-you. Cover:
  - What was the goal
  - What shipped (concrete artifacts, files, PRs, commits)
  - What broke and what you learned
  - Key decisions made
  - **Open questions** — forks in the road, design calls deferred
  - **Loose ends** — small atoms that need 30 seconds next time: uncommitted changes, files in scratch dirs (`/tmp/*`, `~/Desktop/*`), manual steps deferred, scripts paused mid-run, test data to clean up
- **Tags line** at the bottom: 3–7 relevant topic tags

### 2. Pick the JD category

Decide which `XX.07 Claude Code notebook for [scope]` folder this entry belongs in. Use session content (files touched, repos visited, topics discussed) to infer the dominant category.

- When the vault-categories context-injection lands (tracked in `02.02`), pick from the explicit list.
- Until then, infer from session content. Common landing spots:
  - Work on the JD system itself (the conventions, the `00.x` notes, the JD tooling design) → `00.07`
  - Work in `02 LLMs & Agents` (Claude Code config, plugins, prompts) → `02.07`
  - Work in `06 Digital tools` (apple-notes, safari, etc.) → `06.07`
  - Work on a specific `92xxx` project — for now, this likely lands in `02.07` since project-level `.07` slots are not yet established. If the project's category later adopts `.07`, that becomes the right home.
- **If the choice isn't obvious, ask the user before writing.** Do not guess silently.
- Multi-category sessions: pick the dominant category; cross-reference others with `[[XX.07/YYYY-MM-DD]]` inline in the body.
- Fallback: `00.07` for sessions that don't fit any specific category.

### 3. Resolve the vault path

The vault root is at `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian/`. The path to a category's `.07` folder follows the JD shape:

```
<area>/<category>/XX.07 Claude Code notebook for [scope]/YYYY-MM-DD.md
```

Concrete examples:

- `00.07` → `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian/00-09 System/00 System management/00.07 Claude Code notebook for the system/YYYY-MM-DD.md`
- `02.07` → `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian/00-09 System/02 LLMs & Agents/02.07 Claude Code notebook for category 02/YYYY-MM-DD.md`
- `06.07` → `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian/00-09 System/06 Digital tools/06.07 Claude Code notebook for category 06/YYYY-MM-DD.md`

`[scope]` follows the standard-zero convention: "the system" for `00`, "area XX-XX" for `x0` (x>0), "category XY" for `XY` (Y>0).

If `jd which XX.07` is available in the user's `jd` CLI and resolves the path, prefer that over hand-constructing the path. Otherwise hand-construct it from the area + category folder names.

### 4. Write the entry

Use the `Read` and `Write` tools (not shell heredocs — vault is on iCloud and shell ops can hit EPERM). Two cases:

**Case A: today's `YYYY-MM-DD.md` does not exist yet.**

Create it with this content (substitute `YYYY-MM-DD` with today's date, `HH:MM` with current local time, `<8-char-id>` with the first 8 hex characters of the current Claude Code session UUID, `<model-id>` with the active model ID like `claude-opus-4-7`):

````markdown
---
title: YYYY-MM-DD
created: YYYY-MM-DDTHH:mm
modified: YYYY-MM-DDTHH:mm
tags: [jd/agent]
---

# YYYY-MM-DD

## HH:MM — <headline>
*claude-code · session `<8-char-id>` · model `<model-id>`*

<body>

**Tags:** tag1, tag2, tag3
````

**Case B: today's `YYYY-MM-DD.md` already exists.**

Read it. Append the new section (with two blank lines as separator) to the end of the body:

````markdown


## HH:MM — <headline>
*claude-code · session `<8-char-id>` · model `<model-id>`*

<body>

**Tags:** tag1, tag2, tag3
````

Update the frontmatter `modified` field to the current timestamp. Write the file back.

### 5. Maintain the landing note

After writing the daily file, ensure the category's landing note `XX.07 Claude Code notebook for [scope].md` exists and references today's daily file.

- If the landing note doesn't exist, create it. Frontmatter shape mirrors the `{{category}}.07` template at `00.03 Templates for the system/`. Body should have a `## Daily notes` section listing `[[YYYY-MM-DD]]`.
- If the landing note exists, read it; ensure today's `[[YYYY-MM-DD]]` is in the daily-notes list (no duplicates); write it back if changed.

### 6. Confirm

Tell the user briefly: which category was chosen, the path written, and the headline. One short sentence.

## Scope

This skill summarizes **only the current session**. To backfill a past session:

- Read the relevant JSONL at `~/.claude/projects/<encoded-project-dir>/<session-id>.jsonl` directly with the `Read` tool, then synthesize and write as above.
- Use the `sessions` skill (`bin/sessions.py`) to find session IDs by date or audit disk usage.
