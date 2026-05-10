---
description: Render a thread as a conversation
allowed-tools: ["mcp__claude-threads__get_thread"]
argument-hint: "<thread-id>"
---

# /thread:show

Call `get_thread(thread_id=<arg>)`. Render frontmatter as a header block, then each message as `### <handle> · <when>` followed by the body.
