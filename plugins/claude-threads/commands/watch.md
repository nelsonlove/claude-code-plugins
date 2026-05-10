---
description: Arm an event-driven Monitor for peer thread updates (no /loop polling). Use when you want notifications-as-they-arrive while you keep working.
allowed-tools: ["Monitor", "mcp__claude-identity__whoami"]
argument-hint: "[--interval <seconds>] [--threads-dir <path>]"
---

# /claude-threads:watch

Set up a persistent Monitor task that emits one notification line per peer thread message, filtered to skip self-writes and dedupe iCloud sync touches.

## Steps

1. Parse `$ARGUMENTS` for optional flags:
   - `--interval <seconds>`: polling-fallback rate (only used if `fswatch` is not installed). Without this and without fswatch, the script will refuse to run with a clear install message.
   - `--threads-dir <path>`: override the threads_dir from config (rare).

2. Call `mcp__claude-identity__whoami` to resolve this session's `session_id` (UUID). If whoami errors (no registry entry, etc.), fall back to leaving `MY_SESSION_ID` empty — the watcher will still emit but lose the scope filter and skip-self protections.

3. Arm `Monitor` with:
   - `description`: `claude-threads peer events (session=<short-id-or-empty>)`
   - `persistent`: `true`
   - `timeout_ms`: `3600000` (1 hour; user can re-arm if needed)
   - `command`: prefix env vars then invoke the bin script:
     ```
     MY_SESSION_ID='<resolved-uuid>' WATCH_INTERVAL='<interval-or-empty>' WATCH_THREADS_DIR='<override-or-empty>' "${CLAUDE_PLUGIN_ROOT}/bin/watch"
     ```
     Set the env vars to empty string when not provided (the script tolerates empty values). The script resolves your handle FRESH per event from the registry — if you `/rename` mid-watch, the next event uses the new name without re-arming.

4. Report the Monitor task ID to the user with a one-line "stop with TaskStop on this task ID" hint.

## Output format

The script emits one line per peer event:

```
[<thread-id> · <status> · <author>] <filename> :: <preview of last message ~180 chars>
```

Each line becomes a notification in the chat. Self-writes and iCloud-sync touches are suppressed.
