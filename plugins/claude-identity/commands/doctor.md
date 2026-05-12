---
description: Identify and prune stale claude-identity state (sidecars whose sessions are no longer alive).
allowed-tools: ["Bash"]
argument-hint: "[--dry-run]"
---

# /claude-identity:doctor

Run the doctor script to clean up stale sidecars. Parse `$ARGUMENTS` for `--dry-run` and invoke:

```
"${CLAUDE_PLUGIN_ROOT}/bin/doctor" [--dry-run]
```

Report the output to the user.

## What "stale" means

A sidecar at `~/.claude/sessions-meta/<session-id>.json` is stale if its `session_id` does not appear in `~/.claude/sessions/` for any live pid (verified via `kill -0`). CC doesn't reap these files when sessions end, so they accumulate over time and interfere with the SessionStart hook's handle-collision check.

## When to run

- After noticing repeated SessionStart hook auto-rename falls through to UUID-prefix unexpectedly (someone "took" the deterministic word but isn't actually running).
- Periodically as housekeeping. Cheap; only touches files whose corresponding session has provably ended.

## Safety

`--dry-run` lists candidates without touching anything. Default action removes them.
