---
description: Rename this session's handle (agent self-rename). Equivalent to the user typing /rename, but agent-callable.
allowed-tools: ["mcp__claude-identity__set_handle"]
argument-hint: "<handle>"
---

# /claude-identity:rename

Take `$ARGUMENTS` as the proposed handle (one word, lowercase, optionally one hyphen-separated suffix; e.g. `cairn`, `wren`, `jd-cli-audit`). Call the `set_handle` MCP tool with that value.

Report the result. On success: confirm the new handle to the user. On error (`InvalidHandle`, `HandleCollision`): explain why and suggest a different handle.

Validation rules (handled by the MCP tool):
- 2-32 chars, lowercase letters/digits, optionally one hyphen segment
- No reserved tokens (`*`, `all`, `any`, `none`, `self`, `external`, `unknown`)
- Not UUID-prefix-shaped (8 hex chars)
- Not already taken by another live session

Behavioral note: this writes the same `name` field that CC's built-in `/rename` writes, so the two are interchangeable. The handle becomes visible in CC's native UI and in `/claude-identity:whoami` / `/claude-identity:sessions` output.
