---
description: Set this session's persistent agent handle. Distinct from CC's built-in /rename (which controls the session topic/focus label).
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

Behavioral note (v0.1.3+): writes the persistent agent handle to the sessions-meta sidecar at `~/.claude/sessions-meta/<session-id>.json`. **Decoupled from CC's built-in `/rename`**, which controls the registry `name` field (session topic/focus label). Use this for the persistent agent identity (`quill`, `wren`, etc.); use CC's `/rename` for the session's current-task label.

The handle becomes visible in `/claude-identity:whoami` / `/claude-identity:sessions` output and is read by downstream consumers (claude-threads, status line). Resolution chain (back-compat): sidecar `handle` → CC registry `name` → UUID-prefix fallback.
