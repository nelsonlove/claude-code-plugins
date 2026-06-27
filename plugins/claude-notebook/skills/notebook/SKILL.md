---
name: notebook
description: Save the current Claude Code session as a per-session note in the JD vault's `03.13 Agent notebook/YYYY-MM/Agent session YYYY-MM-DDTHHMM.md`. One file per session, grouped by month — session metadata lives in frontmatter, body is just headline + free-form prose. Use when wrapping up a session.
user_invocable: true
---

# Claude Notebook

Save the current Claude Code session as a per-session note at `03.13 Agent notebook/YYYY-MM/Agent session YYYY-MM-DDTHHMM.md`. **One file per session, grouped by month** in a `YYYY-MM/` subfolder. Session metadata (id, model, scope, tags) lives in YAML frontmatter; the body is just the H1 (matching `title`) plus free-form prose.

See [[03.05 Conventions & policies for category 03#Engineering notebook—one file per session]] in the vault for the canonical convention.

## What to do

### 1. Synthesize the entry

- **Headline** (≤10 words) — the main thing accomplished. Becomes the H1 (and `title`).
- **Body** — first person, honest, concise; write for future-you. Cover:
  - What was the goal
  - What shipped (concrete artifacts, files, PRs, commits)
  - What broke and what you learned
  - Key decisions made
  - **Open questions** — forks in the road, design calls deferred
  - **Loose ends** — small atoms that need 30 seconds next time
- **Topic, not topic-tags** — notebook entries carry a single `agent/log` tag; topic is captured by `session-scope` wikilinks (step 2), *not* by topic tags. This is the canonical convention (see [[00.31 Tags]] and [[03.05 Conventions & policies for category 03#Engineering notebook—one file per session]]). Don't add `llm/agent` or free-form topic tags.

### 2. Identify touched scopes

List every area / category / project the session worked on. These go in `session-scope:` as a YAML list of wikilink strings. Backlinks from each scope's landing note will surface this session.

Examples:
- System-meta work (JD conventions, `00.x` notes) → `"[[00 System management]]"`
- Claude Code tooling (plugins, prompts, configs) → `"[[03 LLMs & agents]]"`
- Specific projects → `"[[92005 jd-tools]]"`, `"[[92030 claude-code-plugins]]"`, etc.
- Areas → `"[[90-99 Projects]]"` for project-area meta-work

If a session genuinely touches no specific scope, use `"[[00 System management]]"` as the catch-all. Wikilinks must be quoted strings in YAML.

### 3. Consider the friction log

Before writing the entry, ask: did anything in this session feel like cross-cutting friction worth logging — a broken convention, ambiguous routing, repeated question, tooling gap, or something you'd otherwise sigh at and forget?

If **yes**, append a section to [[03.50 Agent friction log]] via the atomic-heredoc pattern (the log is shared across all agents — `Edit`/`Write` is blocked by a `PreToolUse` hook):

```bash
cat <<'EOF' >> '/Users/nelson/obsidian/00-09 System/03 LLMs & agents/03.50 Agent friction log.md'

## YYYY-MM-DDTHH:MM · <your-handle>

<observation in free-form prose>
EOF
```

The friction-log entry is **separate from** the notebook entry — the notebook captures the session's narrative; the friction log captures cross-cutting tooling issues other agents and the planned `agent-log-rollup` auditor can learn from. Write both if both apply.

If the friction also needs follow-up beyond noting the lesson, create a task in the appropriate `XX.02` with a `see friction log YYYY-MM-DDTHH:MM` cross-link (per [[03.05 Conventions & policies for category 03|03.05]] § "Friction-log entries are observations, not tasks").

If **no** — nothing rose to friction-log level — skip this step. The log gets noisy if every session logs trivia. Calibration: would another agent reading this in six months learn something they didn't already know, or recognize a pattern they're also hitting? If neither, don't log it.

See `~/.claude/CLAUDE.md` § "Notebook & Shared File Writes" for the atomic-append rule and the full file list it applies to.

### 4. Resolve the path

```
~/obsidian/00-09 System/03 LLMs & agents/03.13 Agent notebook/YYYY-MM/Agent session YYYY-MM-DDTHHMM.md
```

- Vault root is `~/obsidian/` (real directory; Obsidian Sync handles cross-device — see [[08.14 Sync architecture]]).
- `YYYY-MM/` subfolder groups sessions by month. **Create the subfolder if it doesn't exist yet** (e.g., at the start of a new month).
- Substitute `YYYY-MM-DDTHHMM` with the session's start time (no colon — JD forbids `:` in filenames).

### 5. Write the entry

Use `Read` and `Write` for vault writes. The per-session-file shape means each session writes its own file (single writer), so `Read` → `Write` is safe — no race with concurrent agents. (For files that *are* written by multiple concurrent agents — e.g. a shared append-only log — use `Bash` with `cat <<'EOF' >> '<path>'` to avoid Read→Edit races. That's not this file.)

**Case A: file doesn't exist (typical — fresh session).**

Instantiate from `00.03 Templates for the system/claude-notebook/D00-09 System/D03 LLMs & agents/Agent session.md`. Substitute placeholders:
- `{{datetime}}` → session start, `YYYY-MM-DDTHHMM` (no colon, for filename + title + alias)
- `{{datetime-iso}}` → same but with colon for `created:`/`modified:` (e.g. `YYYY-MM-DDTHH:mm`)
- `{{headline}}` → the headline (becomes H1 and `title`)
- `{{session-id}}` → first 8 hex chars of the session UUID
- `{{model-id}}` → active model (visible in the system prompt's environment block, e.g. `claude-opus-4-7`)
- `{{scope-wikilink-1}}`, `{{scope-wikilink-2}}`, `{{scope-wikilink-3}}` → quoted wikilink strings for `session-scope:`. **The template ships with exactly 3 slot lines** under `session-scope:`. If the session has fewer scopes, *delete* the unused `- "{{scope-wikilink-N}}"` lines entirely (don't leave the placeholders unfilled). If it has more, *add* additional `- "[[...]]"` list items. The list length should match the actual scope count.
- `tags:` → the template hardcodes `tags: [agent/log]`; leave it as-is. Don't add topic tags or `llm/agent` — topic is carried by `session-scope` (per step 1).
- `{{body}}` → the body content

Write the result to the resolved path.

**Case B: file exists (you're updating an entry from earlier in the same session).**

Locate the existing file by grepping for the session-id in frontmatter under the expected month's subfolder:

```bash
grep -rl 'session-id: <8-char>' '~/obsidian/00-09 System/03 LLMs & agents/03.13 Agent notebook/YYYY-MM/'
```

If exactly one path matches, Read it, then Write the file in place with the updated body and any changed metadata (`modified:` to current timestamp, scope or tag list if it grew, headline if revised). If zero paths match, fall back to Case A (write a fresh file — the earlier run wasn't actually persisted). If more than one matches, that's a bug worth surfacing to the user; don't write blindly.

Don't create a second file for the same session ID.

### 6. Confirm

Tell the user briefly: the path written and the headline. One short sentence.

## Frontmatter shape (canonical)

```yaml
---
title: Agent session YYYY-MM-DDTHHMM
created: YYYY-MM-DDTHH:mm
modified: <linter-maintained — write same as created on first write>
tags: [agent/log]
aliases: [Agent session YYYY-MM-DDTHHMM]
session-id: <8-char>
session-model: <model-id>
session-scope:
  - "[[wikilink]]"
  - "[[wikilink]]"
---
```

`uid:` is *not* written here — it's backfilled by the `add-uid` QuickAdd UserScript (wired into the Linter's lintCommands; the next save/lint adds the UUID v7). Do not generate or write `uid:` yourself.

## Body shape

```markdown
# <headline>

<body content>
```

No `## HH:MM` heading (the file IS the session). No authorship line (in frontmatter). No `*scope:*` line (in frontmatter). No `**Tags:**` trailing line (in frontmatter).

## Backfilling past sessions

To backfill a past session into the new shape:

- Read the relevant JSONL at `~/.claude/projects/<encoded-project-dir>/<session-id>.jsonl` directly with the `Read` tool
- Synthesize the headline + body
- Use the session's `start` timestamp for `datetime`, `created`
- Use the `sessions` skill (`bin/sessions.py`) to find session IDs by date or audit disk usage

## Legacy shape (deprecated)

Prior to 2026-05-27, notebook entries were stored as daily rollup files (`Agent note for YYYY-MM-DD.md`) with multiple `## HH:MM — <headline>` sections per day. That shape is retired; old files have been migrated to per-session form. Do not write the legacy shape.
