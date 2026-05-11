---
description: Self-terminate this Claude Code session after running the configured teardown sequence. Sends SIGTERM to own PID.
allowed-tools: ["mcp__claude-identity__whoami", "Read", "Bash"]
argument-hint: "[optional farewell message]"
---

# /goodbye

Self-terminate this session. After this runs, the CC process exits and the chat ends.

## When to use

**Agents must NOT self-invoke `/goodbye` on their own initiative.** Only run when:

- The user types `/goodbye` directly.
- The user says "quit", "end this session", or equivalent in plain language.
- A written instruction (thread message, CLAUDE.md, cron-launched task spec) explicitly directs the session to self-terminate.

If you find yourself thinking "the session feels done, I should /goodbye" — stop. Wait for an explicit user instruction. The cost of premature termination (lost in-flight work, broken thread coordination, dropped handoffs) is higher than the cost of staying alive idle. Anything ambiguous → don't quit; surface the question.

## Steps

1. **Resolve own PID** via `mcp__claude-identity__whoami`. If whoami errors (no registry entry), abort with a clear error — refuse to guess.

2. **Run teardown** by invoking `/teardown` (this plugin's sibling command). Teardown reads `~/.claude/claude-goodbye.local.md` and executes the user's configured pre-shutdown sequence (persist session log, finalize live docs, close handoff threads, etc.).
   - If `/teardown` reports any `required` step failed: **abort the goodbye**. Surface the teardown failure to the user; do not kill.
   - If `/teardown` reports no config exists: log "no teardown config — quitting without state-persistence" and proceed.
   - If `/teardown` succeeds (or all failures were optional): proceed.

3. **Optional farewell**: if the user passed a message as `$ARGUMENTS`, briefly acknowledge it in your final reply.

4. **Issue the termination** via Bash:
   ```bash
   kill -TERM <pid>
   ```
   Replace `<pid>` with the value from step 1. Use `SIGTERM` (not `SIGKILL`) so CC's signal handlers can flush state, fire Stop hooks, and persist conversation log cleanly.

5. **Final reply**: a short goodbye (one sentence). The process exits shortly after — the user may or may not see the reply depending on timing.

## Safety notes

- **Do not run from inside a hook.** Hooks fire mid-tool-call; self-terminating in that state can corrupt session log.
- **In-flight background tasks** (Monitors armed via `/claude-threads:watch`, etc.) are children of the CC process and reaped when the parent exits. No manual cleanup needed.
- **No `--force` flag**: if a user really wants SIGKILL semantics, they can Ctrl-C the terminal. This command is for graceful shutdown only.
- **Refuse if no PID is resolvable**: never `kill` a guessed PID. If `whoami` doesn't return a valid integer `pid`, abort with `claude-goodbye: could not resolve own PID; not killing`.
- **Refuse if required teardown step failed**: data persistence > process termination.
