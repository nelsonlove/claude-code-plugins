---
name: threads
description: Use when the user wants to start, reply to, or read a thread between Claude Code sessions, or asks about cross-session async coordination. Triggers on phrases like "start a thread", "reply to session", "show me the thread", "what threads are open". Documents the claude-threads plugin's slash commands and conventions.
---

# claude-threads skill

This skill helps Claude understand and use the `claude-threads` plugin to coordinate with other CC sessions.

## When to use

| User intent | Use |
|---|---|
| "Start a chat with session fern" | `/thread:start fern "<topic>"` |
| "Reply to thread abc12345" | `/thread:reply abc12345 <msg>` |
| "Show open threads" | `/thread:list` |
| "Show me thread abc12345" | `/thread:show abc12345` |
| "Close that thread" | `/thread:close abc12345` |

## Conventions

**Scope.** When you start a thread, the `scope` argument is a CSV of tags. Address by handle (`fern`), by JD ID (`02.14`), by role (`vault-sweeper`), or by path (`path:/Users/x/repos/foo/**`). Subscribers match if any of *their* tag patterns matches any of *yours* (fnmatch + path: prefix).

**Replies.** When the SessionStart, UserPromptSubmit, or PostToolUse hook surfaces a thread to you, the standard pattern is to reply with `/thread:reply <thread-id> <message>`. Don't open a new thread for a response.

**Status.** Set `/thread:close` when the conversation is genuinely done. Leaves the file in place; flags it as archive-eligible.

## When NOT to use

- For one-shot notifications (e.g. cron jobs reporting), use the `claude-notifications`-style inbox if revived, or just `terminal-notifier`. Threads are for conversations.
- For policy doc loading, use `jd-context` (when that lands).

## See also

- [[claude-identity plugin design]] — handle resolution, scope CRUD, match function
