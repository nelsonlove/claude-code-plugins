---
name: notebook
description: Save the current Claude Code session as a `## HH:MM — <headline>` section appended to today's daily agent note in the JD vault's `02.13 Agent notebook/Agent note for YYYY-MM-DD.md`. Sessions accumulate as sections within a single dated file. Use when wrapping up a session.
user_invocable: true
---

# Engineering Notebook

Save the current Claude Code session as a `## HH:MM — <headline>` section appended to today's daily agent note at `02.13 Agent notebook/Agent note for YYYY-MM-DD.md`. If today's file doesn't exist yet, instantiate it from the template; otherwise append a section to the existing file.

See [[.07 dashboards + agent notebook v2 design]] in the vault (`92023.10 Requirements & design/`) for the convention.

## What to do

### 1. Synthesize the entry

- **Headline** (≤10 words) — the main thing accomplished. Becomes the section's heading.
- **Body** — first person, honest, concise; write for future-you. Cover:
  - What was the goal
  - What shipped (concrete artifacts, files, PRs, commits)
  - What broke and what you learned
  - Key decisions made
  - **Open questions** — forks in the road, design calls deferred
  - **Loose ends** — small atoms that need 30 seconds next time
- **Tags line** at the bottom: 3–7 relevant topic tags

### 2. Identify touched scopes

List every area / category / project the session worked on. These become wikilinks in the body's `*scope:*` line. Backlinks from each scope's landing note will surface this session.

Examples:
- System-meta work (JD conventions, `00.x` notes) → `[[00 System management]]`
- Claude Code tooling (plugins, prompts, configs) → `[[02 LLMs & Agents]]`
- Specific projects → `[[92005 jd-tools]]`, `[[92023 claude-code-plugins]]`, etc.
- Areas → `[[90-99 Projects]]` for project-area meta-work

If a session genuinely touches no specific scope, use `[[00 System management]]` as the catch-all.

### 3. Resolve the path

```
~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian/00-09 System/02 LLMs & Agents/02.13 Agent notebook/Agent note for YYYY-MM-DD.md
```

Substitute `YYYY-MM-DD` with today's date.

### 4. Write the entry

Use `Read` and `Write` (NOT shell heredocs — vault is on iCloud).

**Case A: file doesn't exist (first session of the day).**

Instantiate from `02.03 Templates for category 02/Agent note for {{date}}.md`. Substitute placeholders:
- `{{date}}` → today's date `YYYY-MM-DD`
- `{{time}}` → current local time `HH:MM`
- `{{headline}}` → the headline
- `{{session-id}}` → first 8 hex chars of the session UUID
- `{{model-id}}` → active model (visible in the system prompt's environment block, e.g. `claude-opus-4-7`)
- `{{wikilink-1}}` … `{{wikilink-N}}` → wikilinks from Step 2 (use as many as needed; remove unused placeholders)
- `{{body}}` → the body content
- `{{topic-tag-N}}` → topic tags from Step 1

Write the result to the resolved path.

**Case B: file exists (a session has already written today).**

Read it. Append a new section to the end of the body (preserve a single blank line as separator before the new `##` heading):

```markdown

## HH:MM — <headline>
*claude-code · session `<8-char-id>` · model `<model-id>`*
*scope: [[area]] · [[category]] · [[project]]*

<body>

**Tags:** topic1, topic2, topic3
```

Update the frontmatter `modified` field to the current timestamp (with `:` since it's YAML, not a filename).

If `/notebook` is invoked twice in the same session UUID on the same day (e.g., to revise an entry), find your existing section by matching the session ID in the authorship line and update that section in place rather than appending a new one.

### 5. Confirm

Tell the user briefly: the path written and the headline. One short sentence.

## Scope

This skill summarizes **only the current session**. To backfill a past session:

- Read the relevant JSONL at `~/.claude/projects/<encoded-project-dir>/<session-id>.jsonl` directly with the `Read` tool, then synthesize and append/create as above using the past session's start time.
- Use the `sessions` skill (`bin/sessions.py`) to find session IDs by date or audit disk usage.
