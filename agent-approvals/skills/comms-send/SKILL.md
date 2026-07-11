---
name: comms-send
description: Send a message, blocker, handoff, or FYI to the comms agent (or any agent handle) via the Pickle comms collection. Use instead of raw pickle commands whenever you need to notify the human asynchronously, hand work to another agent, or surface something no one watching your session would otherwise see.
---

# comms-send

Never assume a human reads your session. Anything that must be *seen* goes
through the comms channel: run `${CLAUDE_PLUGIN_ROOT}/skills/comms-send/comms-send.sh`.

```sh
comms-send.sh --title "blocked: X needs a decision" --message "1-3 sentences of context" \
  [--to comms] [--from <your handle>] [--kind message|ask] [--tag t]
```

- `--kind message` (default): fire-and-forget FYI/blocker/handoff; comms acks it.
- `--kind ask`: you need a typed response back — pair with `pickle wait <id>`.
- Always pass `--from` with your session handle if `CLAUDE_SESSION_HANDLE` isn't set.
- Do NOT hand-roll `pickle message` for comms traffic — conventions (collection,
  tag grammar, sender identity, cross-machine transport) live in this script.
