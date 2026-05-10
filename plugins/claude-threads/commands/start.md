---
description: Start a new thread. Usage — /thread:start <scope-csv> <topic>
allowed-tools: ["mcp__claude-threads__start_thread"]
argument-hint: "<scope-csv> <topic>"
---

# /thread:start

Parse `$ARGUMENTS`: first comma-separated token is `scope` (CSV); the rest is `topic`. Then ask the user for the message body, then call `start_thread`.

Example: `/thread:start 02.14,vault-sweeper "reconcile inbox triage"` → opens a thread to anyone subscribed to 02.14 OR vault-sweeper, titled "reconcile inbox triage".
