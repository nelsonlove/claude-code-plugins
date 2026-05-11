# claude-goodbye

A Claude Code plugin for agent self-termination with a configurable pre-shutdown teardown sequence.

## Commands

- **`/teardown`** — runs the configured pre-shutdown sequence (persist session state, finalize live docs, close handoff threads, etc.). Does NOT kill the process.
- **`/goodbye [farewell]`** — runs `/teardown` then SIGTERMs the CC process. Refuses to kill if any required teardown step failed.

## Why

Autonomous agents need a programmatic exit path. Ctrl-C from the terminal requires human hands; `/goodbye` is the agent-callable equivalent. But naïve self-termination loses session state — daily summaries, live previews, open thread handoffs. The `/teardown` orchestrator runs the user's configured cleanup steps first, so `/goodbye` only kills after state is persisted.

## Install

```bash
claude plugin install claude-goodbye
```

## Configure teardown

Create `~/.claude/claude-goodbye.local.md`:

```yaml
---
steps:
  - command: /claude-notebook:notebook
    description: Persist session log to daily agent note
    required: true
  - command: /claude-identity:live-update finalize 'session ending'
    description: Update live preview note
    required: false
  - command: /claude-threads:close <thread-id>
    description: Close any open handoff threads owned by this session
    required: false
---

# Local teardown config

Whatever notes/documentation about this fleet's teardown sequence.
```

**Step fields:**

- `command` (required) — the exact slash command to invoke, including any arguments.
- `description` (required) — human-readable label shown to the user during execution.
- `required` (default: `false`) — if `true`, a failure of this step aborts the entire teardown and prevents `/goodbye` from killing the process.

## Usage

```
/teardown
```

Runs the configured sequence without quitting. Use to test the sequence, or as a milestone "save state" without ending the session.

```
/goodbye
/goodbye wrapping up — see you next time
```

Runs teardown, then SIGTERMs own PID. Optional message is acknowledged in the final reply.

## Agent guidance baked into the slash commands

The slash-command bodies include explicit guidance that agents should **never self-invoke `/goodbye`** without an explicit user instruction. The plugin is a safety surface, not a "session feels done" trigger.

## Dependencies

- [`claude-identity`](../claude-identity) — `whoami` MCP tool for PID resolution. Hard dependency.
- Bash — for the `kill` invocation in `/goodbye`.

Teardown steps may reference any other plugin's slash commands (e.g. `claude-notebook`, `claude-identity`, `claude-threads`). The plugin doesn't require any of those to be installed — it only invokes what the user configures.

## Safety

- Refuses to kill if `whoami` can't resolve a valid PID (won't guess).
- Refuses to kill if a required teardown step failed (data persistence > process termination).
- Uses SIGTERM, not SIGKILL — graceful shutdown only.
- Should not be called from inside a hook (mid-tool-call termination corrupts session log).
- Background Monitors are reaped automatically when the parent CC process exits.
