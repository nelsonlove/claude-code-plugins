---
description: Self-terminate this Claude Code session. Sends SIGTERM to own PID after an optional farewell message.
allowed-tools: ["mcp__claude-identity__whoami", "Bash"]
argument-hint: "[optional farewell message]"
---

# /goodbye

Self-terminate this session. After this runs, the CC process exits and the chat ends.

## Steps

1. Call `mcp__claude-identity__whoami` to resolve this session's `pid`. If whoami errors (e.g. no registry entry), abort with a clear error — refuse to guess the PID.

2. If the user passed a farewell message as `$ARGUMENTS`:
   - Briefly acknowledge it back to the user in your final reply.
   - Optionally append it to your live note (if `claude-identity:live-update` is installed and the agent maintains one) or post a closing message to a thread (if `claude-threads` is installed and the agent has an active conversation). These side-effects are optional — skip if not applicable.
3. Issue the termination via Bash:
   ```bash
   kill -TERM <pid>
   ```
   Replace `<pid>` with the value from step 1. Use `SIGTERM` (not `SIGKILL`) so CC's signal handlers can flush state, fire Stop hooks, and persist conversation log cleanly.

4. After the `kill` call returns, your final reply text should be a short goodbye (one sentence). The process will exit shortly after — the user may or may not see the reply depending on timing.

## Safety notes

- **Do not run this from inside a hook.** Hooks fire mid-tool-call; self-terminating in that state can corrupt session log.
- **In-flight background tasks** (Monitors armed via `/claude-threads:watch`, etc.) are children of the CC process and will be reaped when the parent exits. No manual cleanup needed.
- **No `--force` flag**: if a user really wants SIGKILL semantics, they can Ctrl-C the terminal themselves. This command is for graceful shutdown only.
- **Refuse if no PID is resolvable**: never `kill` a guessed PID. If `whoami` doesn't return a valid integer `pid` field, abort with `claude-goodbye: could not resolve own PID; not killing`.
