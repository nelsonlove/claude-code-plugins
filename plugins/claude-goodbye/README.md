# claude-goodbye

A Claude Code plugin that exposes a single `/goodbye` slash command for agent self-termination.

## Why

Autonomous agents sometimes need to quit cleanly — they finished their assigned task, the user wants them gone, a fleet-cleanup script needs to retire them. Ctrl-C from the terminal works, but it requires human hands on the keyboard. `/goodbye` is the programmatic equivalent: the agent calls it, the CC process gracefully terminates via SIGTERM to its own PID.

## Install

```bash
claude plugin install claude-goodbye
# or, if running from the monorepo, symlink:
ln -s /path/to/claude-code-plugins/plugins/claude-goodbye ~/.claude/plugins/claude-goodbye
```

## Usage

```
/goodbye
/goodbye Wrapping up — see you next time
```

The optional argument is a farewell message the agent may include in its final reply or persist to a live-note/thread before exiting.

## Mechanism

1. Resolve own PID via `claude-identity`'s `whoami` MCP tool (this plugin depends on `claude-identity`).
2. Send `SIGTERM` to that PID via Bash. CC's signal handler flushes state, fires Stop hooks, and exits cleanly.

## Dependencies

- [`claude-identity`](../claude-identity) — for PID resolution. Hard dependency.
- Bash — for the `kill` invocation.

## Safety

- Refuses to run if `whoami` can't resolve a valid PID (won't guess).
- Uses SIGTERM, not SIGKILL — graceful shutdown only.
- Should not be called from inside a hook (mid-tool-call termination corrupts session log).
- Background Monitors are reaped automatically when the parent CC process exits.
