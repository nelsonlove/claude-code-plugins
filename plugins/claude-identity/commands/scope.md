---
description: Manage subscription tags. Usage — /identity:scope add <tag> | rm <tag> | list [--session <handle-or-id>]
allowed-tools: ["mcp__claude-identity__add_tag", "mcp__claude-identity__remove_tag", "mcp__claude-identity__list_tags"]
argument-hint: "<add|rm|list> [<tag>] [--session <handle>]"
---

# /identity:scope

Parse `$ARGUMENTS`:
- First word is the subcommand: `add`, `rm`, or `list`.
- For `add` / `rm`: second word is the tag (required).
- Optional `--session <handle-or-id>` flag (defaults to self).

Then call the matching MCP tool:
- `add` → `add_tag`
- `rm` → `remove_tag`
- `list` → `list_tags`

Report the resulting tag list.
