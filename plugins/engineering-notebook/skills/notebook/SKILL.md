---
name: notebook
description: Save a Claude Code engineering-journal entry as one timestamped file in the JD vault's 02.13 Engineering notebook. Captures what shipped, what broke, key decisions, and loose ends. Use when wrapping up a session.
user_invocable: true
---

# Engineering Notebook

Save the current Claude Code session as a single timestamped file in `02.13 Engineering notebook/` in the JD vault. One session per file. The canonical entry shape lives at `02.03 Templates for category 02/engineering-notebook entry.md` — keep this skill aligned with that template.

## What to do

### 1. Synthesize the entry

- **Headline** (≤10 words) — the main thing accomplished. Becomes the H1.
- **Body** — first person, honest, concise; write for future-you. Cover:
  - What was the goal
  - What shipped (concrete artifacts, files, PRs, commits)
  - What broke and what you learned
  - Key decisions made
  - **Open questions** — forks in the road, design calls deferred
  - **Loose ends** — small atoms that need 30 seconds next time: uncommitted changes, files in scratch dirs (`/tmp/*`, `~/Desktop/*`), manual steps deferred, scripts paused mid-run, test data to clean up
- **Tags** — 3–7 relevant topical tags; go in frontmatter `tags:` after the leading `jd/agent`.

### 2. Resolve identity + timestamp

- **Session UUID:** the current Claude Code session's full UUID. Find it via `~/.claude/projects/<encoded>/<uuid>.jsonl` — the `<uuid>` is what you need. The 8-char prefix (lowercase hex) goes in the filename for disambiguation.
- **Model ID:** active model ID, e.g. `claude-opus-4-7`, `claude-sonnet-4-6`, `claude-haiku-4-5`. Visible in the system prompt's environment block under "powered by the model".
- **Timestamp:** local America/New_York time. Use ISO-8601 with explicit TZ offset (`-04:00` EDT, `-05:00` EST). Both `created` and `modified` start equal; if you're updating an entry later, bump `modified` only.

### 3. Build the filename

```
YYYY-MM-DDTHH-MM-SS — <uuid8>.md
```

- ISO timestamp with `-` instead of `:` (macOS-friendly).
- Em-dash (U+2014) with single spaces around it.
- `<uuid8>` is the first 8 hex chars of the session UUID, lowercased.
- Example: `2026-05-08T00-16-00 — 7bd265f4.md`

### 4. Write the file

Vault path:

```
~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian/00-09 System/02 LLMs & Agents/02.13 Engineering notebook/<filename>.md
```

Use the `Write` tool (the vault is on iCloud — shell heredocs can hit EPERM).

Content shape — match the template at `02.03 Templates for category 02/engineering-notebook entry.md`:

````markdown
---
title: '<ISO timestamp, no TZ, e.g. 2026-05-08T00:16:00>'
created: '<ISO timestamp with TZ, e.g. 2026-05-08T00:16:00-04:00>'
modified: '<same as created on first write>'
tags: [jd/agent, <tag1>, <tag2>, <tag3>]
source: vault
source-session-uuid: '<full session UUID>'
source-model: '<model-id>'
disabled rules:
  - yaml-title-alias
  - yaml-key-sort
---

# <headline>

<body — markdown, free-form. Common sections: ## What shipped, ## What I learned, ## Decisions, ## Open questions, ## Loose ends>
````

`disabled rules` keeps the linter from rewriting the title to match the H1 (we want title=timestamp, H1=headline) and from reordering keys.

### 5. Confirm

Tell the user briefly: the timestamp + headline + path written. One short sentence.

## Scope

This skill summarizes **only the current session**. To backfill a past session:

- Read the relevant JSONL at `~/.claude/projects/<encoded-project-dir>/<session-id>.jsonl` directly with the `Read` tool, then synthesize and write as above with the original session's UUID, model, and timestamp.
- Use the `sessions` skill (`bin/sessions.py`) to find session IDs by date or audit disk usage.

## Why one file per session (and not one per day)

Earlier versions stacked sessions into daily notes (`YYYY-MM-DD.md` with `## HH:MM — headline` sections). The flat one-per-session shape replaces that:

- Every entry has its own filename, sortable by ISO timestamp.
- Provenance (session UUID, model) lives in frontmatter — structured, queryable, no body parsing needed.
- No collision/merge logic: never read-then-append, just write.
- Day One historical imports use the same shape (with `source: dayone` instead).

If you find a same-second collision (rare), the `<uuid8>` suffix disambiguates.
