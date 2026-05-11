---
description: Arm a Monitor that watches this agent's live note for user-edits (notifies when Nelson revises the note in Obsidian).
allowed-tools: ["mcp__claude-identity__whoami"]
argument-hint: "[--interval <seconds>]"
---

# /claude-identity:watch-live-note

Parse `$ARGUMENTS` for:

- `--interval <seconds>`: polling interval (default 3).

Steps:

1. Call `mcp__claude-identity__whoami` to resolve this session's `session_id` (UUID).
2. Arm a persistent `Monitor` task with:
   - `description`: `claude-identity live-note watcher (session=<short-id>)`
   - `persistent`: `true`
   - `timeout_ms`: `3600000`
   - `command`:
     ```
     MY_SESSION_ID='<resolved-uuid>' WATCH_INTERVAL='<interval-or-empty>' "${CLAUDE_PLUGIN_ROOT}/bin/watch-live"
     ```
3. Report the Monitor task ID with a one-line "stop with TaskStop on this task ID" hint.

## How it works

The script polls the agent's live note (`<vault>/03 LLMs & agents/03.15 Agent live notes/<handle>.md`) every `interval` seconds and compares the file's `modified:` frontmatter field against the watermark the agent stored in its sidecar after its last `update_live_note` call.

- **No change** → silent.
- **`modified:` diverges from watermark** → emits one line to stdout, which Claude Code surfaces as a `<task-notification>` in the chat. Watcher then accepts the change as the new watermark so it doesn't keep firing for the same edit.

Self-writes are not emitted: every `update_live_note` call updates the watermark after writing, so the agent's own modifications are always "in sync" with the file.

## When notifications surface

- During an active conversation: the notification appears between user prompts (or right after the next tool call). The agent sees it inline.
- During idle waits: notifications queue up and surface on the next user prompt — same as the `/claude-threads:watch` pattern.
- Fully idle (no user interaction): not handled by the in-session Monitor. Cron-escalation territory (Spec 3 in the substrate roadmap).
