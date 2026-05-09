---
description: Test whether this session's tags match a given scope. Useful for debugging tag patterns.
allowed-tools: ["mcp__claude-identity__match"]
argument-hint: "<scope-csv>"
---

# /identity:match

Take `$ARGUMENTS` as a CSV of scope tags. Split on `,` and call the `match` MCP tool with the resulting list.

Report whether it matches and which subscriber pattern caused the match (if matched), or list the session's tags + the scope tags side-by-side (if no match).
