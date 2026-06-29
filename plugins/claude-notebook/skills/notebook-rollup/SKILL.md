---
name: notebook-rollup
description: Generate weekly narrative rollups for the JD vault's agent notebook. Surveys `03.13 Agent notebook/YYYY-MM/` per-session notes, finds COMPLETED ISO weeks that have sessions but no rollup yet, and writes `rollups/Agent rollup for YYYY-WNN.md` for each — a hand-quality thematic synthesis. Never rolls up the in-progress week. Use to catch up the rollup layer (manually; there is no schedule).
user_invocable: true
---

# Notebook Rollup

Generate **weekly narrative rollups** for the agent notebook: one `rollups/Agent rollup for YYYY-WNN.md` per ISO week, summarizing that week's per-session notes into a themed synthesis the user re-reads.

This is the *narrative* rollup — the curated layer above the raw per-session notes. It is **not** the `agent-log-rollup` auditor (a separate someday-spec at `[[03.08 Someday for category 03]] → Agent log rollup` that surveys logs and proposes codifications to an inbox file). Don't conflate them.

Base folder: `~/obsidian/00-09 System/03 LLMs & agents/03.13 Agent notebook/`. Rollups live in its `rollups/` subfolder. The folder note documents the layout; the convention is in `[[03.05 Conventions & policies for category 03#Engineering notebook—one file per session]]`.

## When to run

Manually, whenever you want to catch the rollup layer up — typically after a completed week. There is intentionally no schedule (the user opted for a manual command). The current in-progress week is always skipped: its rollup would be partial.

## 1. Detect which weeks need rolling up

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/bin/rollup_gaps.py" --summary
```

This prints JSON to stdout and a human summary to stderr. It buckets every session note by ISO week (`date.isocalendar()`), subtracts weeks that already have a rollup, and **excludes the current in-progress week**. `target_weeks` is the work list, in ascending order, each with its `week` (`YYYY-WNN`), `monday`/`sunday` bounds, `session_count`, `files` (paths relative to the base folder), and `rollup_path`.

- **`target_weeks` is empty** → nothing to do. Tell the user everything completed is already rolled up, and stop.
- **To (re)generate one specific week** (e.g. a week that gained a late session note, or to redo a thin rollup): `rollup_gaps.py --week 2026-W26 --summary`. It returns that week's files regardless of whether a rollup already exists (overwrites on regen).
- **To force-include the unfinished current week** (rare; produces a partial rollup): add `--include-current`. Default behavior — and the user's standing preference — is to leave the current week open.

## 2. Generate a rollup per target week

Process target weeks **in ascending order** so each week's "Carrying forward" link points at an already-written prior rollup. For each week, dispatch ONE subagent (Agent tool) that owns exactly that week's `rollup_path` and touches nothing else. If there are several weeks you may run the subagents in parallel — wikilinks resolve regardless of write order — but assign each a distinct output file (never two agents to one file).

Give each subagent this brief, substituting the week label, date range, session count, and the explicit list of session-note paths (prefix each `files[]` entry with the base folder):

> You are writing one weekly rollup for the Obsidian agent notebook — a vault of per-session notes Claude Code agents write after each session. You are summarizing **ISO week {YYYY-WNN} ({Mon date} – {Sun date})**, {N} sessions.
>
> 1. Read ALL of these {N} session notes IN FULL (base folder `~/obsidian/00-09 System/03 LLMs & agents/03.13 Agent notebook/`): {explicit list of `YYYY-MM/Agent session ...md` paths}.
> 2. Study two existing rollups to match voice + structure exactly: `rollups/Agent rollup for 2026-W14.md` (small — shows the full section set) and `rollups/Agent rollup for 2026-W21.md` (rich — shows the dense thematic voice and how a busy week is clustered).
> 3. Write ONE new file to `rollups/Agent rollup for {YYYY-WNN}.md`. Do NOT modify the session notes or any other file.
>
> Frontmatter (NO `uid` line — tooling backfills it; no aliases):
> ```
> ---
> jd-id:
> title: Agent rollup for {YYYY-WNN}
> description:
> created: {today YYYY-MM-DDTHH:MM:SS}
> modified: {same as created}
> tags:
>   - agent/log
>   - rollup
> ---
> ```
> Body, in this order:
> - `# Agent rollup for {YYYY-WNN}`
> - A `> [!info]` callout: one tight paragraph — session count + dates + a one-line executive summary of the week's character, ending with "Carries forward from [[Agent rollup for {prev YYYY-WNN}]]."
> - `## Themes this week` — a NUMBERED list. Each item opens with a **bold lead-in** then prose. CLUSTER related sessions into coherent themes (don't transcribe one bullet per session); for a busy week aim ~8–15 themes. Pull in concrete specifics: note/file names as `[[wikilinks]]`, counts, commands, PR numbers, bugs, decisions. This is the part the user re-reads — make it genuinely useful.
> - `## Carrying forward from {prev WNN}` — bullets of threads continuing from prior weeks or left open; link `[[Agent rollup for {prev YYYY-WNN}]]`. Keep light.
> - `## Still open (new this week)` — bullets, or `*None this week.*`
> - `## Loose ends` — bullets, or `*None new.*`
> - `## Decisions worth remembering` — durable decisions/patterns with a trailing date, or `*None.*`
> - `## Scopes touched` — a comma-separated line of `[[wikilink]]` scopes, taken from the sessions' own `session-scope` frontmatter.
>
> Hard rules:
> - Tags go ONLY in frontmatter — NEVER write a body `**Tags:**` line (standing vault correction).
> - Omit `uid` entirely; don't invent one (the `add-uid` tool backfills a UUID v7).
> - Use real `[[wikilinks]]` taken from the session notes' own links and `session-scope` fields.
> - Dense, specific, past-tense voice like W21. No filler. Don't fabricate — a thin week gets a short rollup (W14 is short and that's fine).
>
> Reply with a 2–3 sentence summary of the week and confirm the path written.

The previous-week label is just the target week minus one (e.g. W23 carries from W22; W08 carries from the prior year's last week if applicable). Use today's date for `created`/`modified`; the vault linter will fix `modified` and add `uid` on its next pass.

## 3. Verify each rollup

After the subagents finish, check every file written:

```bash
cd "$HOME/obsidian/00-09 System/03 LLMs & agents/03.13 Agent notebook/rollups"
# List the exact files you just wrote, one quoted entry per week:
for f in "Agent rollup for 2026-W23.md" "Agent rollup for 2026-W24.md"; do
  [ -f "$f" ] || { echo "FAIL: $f missing"; continue; }
  grep -q '^\*\*Tags' "$f" && echo "FAIL $f: body **Tags** line"
  grep -q '^uid:' "$f" && echo "WARN $f: invented uid (strip it — add-uid backfills)"
  grep -q '^## Scopes touched' "$f" || echo "FAIL $f: missing sections"
done
```

Confirm: the file exists, frontmatter has tags only in `tags:` (no body `**Tags:**`), no hand-written `uid:`, and the seven sections are present. If a subagent invented a `uid`, strip that line so `add-uid` assigns a proper UUID v7.

## 4. Report

Tell the user which weeks were written (week + headline), and note any week intentionally skipped (the current in-progress week). The folder note's `rollups/` Dataview query picks up new files automatically — no index edit needed.
