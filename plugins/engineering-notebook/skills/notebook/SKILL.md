---
name: notebook
description: Save the current Claude Code session as a per-session note in the JD vault's `02.13 Agent notebook/` folder. Filename `Agent note for YYYY-MM-DDTHH-MM.md`. Each session is tagged with the area / category / project scopes it touched. Use when wrapping up a session.
user_invocable: true
---

# Engineering Notebook

Save the current Claude Code session as a single file at `02.13 Agent notebook/Agent note for YYYY-MM-DDTHH-MM.md`. File ↔ session is 1:1 by session UUID — re-invocations of `/notebook` in the same session UPDATE the same file (matched on session ID), they don't create new files.

See [[.07 dashboards + agent notebook v2 design]] in the vault (`92023.10 Requirements & design/`) for the convention.

## What to do

### 1. Synthesize the entry

- **Headline** (≤10 words) — the main thing accomplished. Becomes both the H1 and the frontmatter `title`.
- **Body** — first person, honest, concise; write for future-you. Cover:
  - What was the goal
  - What shipped (concrete artifacts, files, PRs, commits)
  - What broke and what you learned
  - Key decisions made
  - **Open questions** — forks in the road, design calls deferred
  - **Loose ends** — small atoms that need 30 seconds next time
- **Tags line** at the bottom: 3–7 relevant topic tags

### 2. Identify touched scopes

List every area / category / project the session worked on. These become wikilinks in the body's `*scope:*` line (NOT frontmatter). Backlinks from each scope's landing note will surface this session — that's the discoverability mechanism.

Examples:
- System-meta work (JD conventions, `00.x` notes) → `[[00 System management]]`
- Claude Code tooling (plugins, prompts, configs) → `[[02 LLMs & Agents]]`
- Specific projects → `[[92005 jd-tools]]`, `[[92023 claude-code-plugins]]`, etc.
- Areas → `[[90-99 Projects]]` for project-area meta-work

If a session genuinely touches no specific scope, use `[[00 System management]]` as the catch-all.

### 3. Resolve the path

Compute `Agent note for YYYY-MM-DDTHH-MM.md` where `HH-MM` is the **first `/notebook` write timestamp for the current session**. If you've already invoked `/notebook` this session, the file exists at that earlier timestamp — find it (search `02.13 Agent notebook/` for files matching the session UUID in their frontmatter `session:` field). If this is the first invocation, use the current local time.

Full path:

```
~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian/00-09 System/02 LLMs & Agents/02.13 Agent notebook/Agent note for YYYY-MM-DDTHH-MM.md
```

### 4. Write the entry

Use `Read` and `Write` (NOT shell heredocs — vault is on iCloud).

**Case A: file doesn't exist (first `/notebook` for this session).**

Instantiate from `02.03 Templates for category 02/Agent note for {{date}}T{{time}}.md`. Substitute placeholders:
- `{{headline}}` → the headline
- `{{session-id}}` → first 8 hex chars of the session UUID
- `{{model-id}}` → active model (visible in the system prompt's environment block, e.g. `claude-opus-4-7`)
- `{{date}}` → today's date `YYYY-MM-DD`
- `{{time}}` → current local time `HH-MM`
- `{{wikilink-1}}` … `{{wikilink-N}}` → wikilinks from Step 2 (use as many as needed; remove unused placeholders)
- `{{body}}` → the body content
- `{{topic-tag-N}}` → topic tags from Step 1

Write the result to the resolved path.

**Case B: file exists (re-invocation in same session).**

Read it. Update:
- `modified` field in frontmatter → current timestamp (with `:` since this is YAML, not a filename)
- Body — replace or extend, depending on what changed since last invocation
- Authorship and scope lines — update if scopes changed
- Topic tags line — update if tags changed

Don't change `created`, `session`, or the filename — those identify the session.

### 5. Confirm

Tell the user briefly: the path written and the headline. One short sentence.

## Scope

This skill summarizes **only the current session**. To backfill a past session:

- Read the relevant JSONL at `~/.claude/projects/<encoded-project-dir>/<session-id>.jsonl` directly with the `Read` tool, then synthesize and write a new `Agent note for ...` file using the past session's start time as `HH-MM`.
- Use the `sessions` skill (`bin/sessions.py`) to find session IDs by date or audit disk usage.
