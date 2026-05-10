---
description: Reply to an existing thread. Usage — /thread:reply <thread-id> <message>
allowed-tools: ["mcp__claude-threads__reply_thread"]
argument-hint: "<thread-id> <message>"
---

# /thread:reply

First whitespace-separated token is `thread_id` (8 chars, or unique prefix ≥4). Rest is the message. Call `reply_thread`.
