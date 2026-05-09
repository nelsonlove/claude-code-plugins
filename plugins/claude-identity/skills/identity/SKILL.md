---
name: identity
description: Use when discussing or managing Claude Code session identity, scope tags, subscription matching, or cross-session coordination. Triggers on phrases like "what session is this", "subscribe to", "tag this session", "list sessions", "scope". Documents the claude-identity plugin's slash commands and MCP tools, and the conventions for handle resolution and tag matching.
---

# claude-identity skill

This skill helps Claude understand and use the `claude-identity` plugin substrate effectively.

## What `claude-identity` provides

- **Session handle** — every CC session has a UUID; running `/rename` sets a human-readable name. `claude-identity` resolves either to the other.
- **Subscription tags** — sessions can self-tag with arbitrary strings (JD IDs like `02.14`, role names, free-form). Tags are how sessions express interest in scopes.
- **Match function** — given two tag arrays (subscriber, scope), tell whether they overlap. fnmatch glob (`02.*`) plus `path:` prefix dispatch for filesystem paths.

## When to use what

| User intent | Use |
|---|---|
| "What session am I?" | `/identity:whoami` |
| "List active sessions" | `/identity:sessions` |
| "Add a tag to this session" | `/identity:scope add <tag>` |
| "Remove a tag" | `/identity:scope rm <tag>` |
| "Tag another session" | `/identity:scope add <tag> --session <handle>` |
| "Does this match?" | `/identity:match <csv>` |

## Tag conventions

- **Plain tags** — `02.14`, `vault-sweeper`, `production`. fnmatch glob applies.
- **`path:` prefix** — `path:/Users/nelson/repos/foo/**`. pathlib semantics, supports `**`.
- **Mixed types never match** — `02.14` does not match `path:/repos/foo` and vice versa.

## Implicit handle subscription

Every session implicitly subscribes to its own `name` (set with `/rename`) — so a thread targeting `[fern]` reaches session `fern` even if `fern` hasn't added itself to its tag list. The matcher reads the handle from the registry at match time.

## When NOT to call `claude-identity`

- For thread CRUD — use `/thread:*` commands from `claude-threads`.
- For policy doc loading — use `/jd-context:*` (when that plugin lands).
