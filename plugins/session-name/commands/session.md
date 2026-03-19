---
name: session
description: Set the session name. Pass a name to use it directly, or leave blank to have Claude suggest one based on conversation context.
argument-hint: "[name]"
---

Set the current session name.

<$ARGUMENTS>

## Instructions

### With argument

If a name was provided, call the `set_session_name` MCP tool with that name directly.

Report: "Session named: <name>"

### Without argument

If no argument was given, look at the conversation so far — what the user has been working on, what files have been touched, what topics have come up — and pick a short, descriptive session label (2-4 words, lowercase).

Call `set_session_name` with it directly.

Report: "Session named: <name>"
