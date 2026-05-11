---
description: Run the configured teardown sequence (persist session state, finalize live docs, close handoffs) without quitting. Reads ~/.claude/claude-goodbye.local.md for the step list.
allowed-tools: ["Read", "Bash"]
argument-hint: ""
---

# /teardown

Run the configured pre-shutdown sequence. **Does not kill the process** — for that, follow with `/goodbye`.

Useful for: saving session state at a milestone, testing the teardown sequence before committing to `/goodbye`, or any "pause and resume" workflow.

## Steps

1. **Read the config**: `~/.claude/claude-goodbye.local.md`. If it doesn't exist, abort with: `claude-goodbye: no teardown config found at ~/.claude/claude-goodbye.local.md — nothing to do.`

2. **Parse the YAML frontmatter.** Expected shape:

   ```yaml
   ---
   steps:
     - command: /<plugin>:<command> [args]
       description: <human-readable>
       required: true|false   # optional; defaults to false if omitted
   ---
   ```

   If frontmatter parsing fails or `steps` is missing/empty, abort with a clear error. If a step omits `required`, treat it as `required: false`.

3. **Execute each step in order**:
   - Announce the step to the user: `Running step N/M: <description>` then the actual command.
   - Invoke the command exactly as written (it's a slash-command invocation by the agent on its own behalf).
   - A step succeeds if the invocation returns without error. (No per-step custom verification — the user's individual slash commands own their own success semantics.)
   - **If a `required: true` step fails**: abort the rest of the sequence and surface the failure clearly. Subsequent steps are NOT run.
   - **If a `required: false` (or omitted) step fails**: log it, continue.

4. **Report**: at the end, summarize which steps ran, which succeeded, which failed. If any required step failed, the overall teardown status is FAILED and `/goodbye` should refuse to kill until the teardown is resolved.

## Safety

- Treat each step's command as agent-trusted input — it's user-configured locally. No shell escaping required.
- Do not run any side effects beyond what's listed. This command is a pure orchestrator.
- Time-bound: if any individual step takes longer than ~2 minutes, surface a "step running long" note to the user but don't auto-kill the step. The user can Ctrl-C if needed.
