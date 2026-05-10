---
description: List open threads matching this session's subscribed tags
allowed-tools: ["mcp__claude-threads__list_threads"]
argument-hint: "[--scope <pattern>] [--status <enum>]"
---

# /thread:list

Parse optional `--scope <pattern>` and `--status <enum>` from `$ARGUMENTS`. Call `list_threads` with the parsed args. Render as a table:

| thread-id | status | title | opener | scope | modified |
|---|---|---|---|---|---|
