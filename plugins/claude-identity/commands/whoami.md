---
description: Print this session's identity (UUID, handle, pid, cwd, status, tags)
allowed-tools: ["mcp__claude-identity__whoami"]
---

# /identity:whoami

Call the `whoami` MCP tool and pretty-print the result for the user, with each field on its own line.

If the tool returns an error (e.g. no registry entry for this PID), report it succinctly and suggest restarting CC if appropriate.
