# claude-identity

Foundational Claude Code plugin: cross-session identity substrate.

Provides session handle resolution, subscription tag CRUD, and a public `match()` function used by other plugins (`claude-threads`, `jd-context`) for filtering messages and context by scope.

## Install

This plugin is part of the `claude-code-plugins-mac` marketplace. Install via:

```
/plugin install claude-code-plugins-mac
```

Or for development: clone `~/repos/claude-code-plugins/` and install locally.

## Slash commands

- `/identity:whoami` — print this session's identity
- `/identity:sessions` — list all live sessions
- `/identity:scope add|rm|list [<tag>] [--session <handle>]` — manage tags
- `/identity:match <scope-csv>` — debug scope-pattern matches

## Configuration

Two layers:
- **Global**: `~/.claude/claude-identity/config.toml`
- **Per-project**: `<project>/.claude/claude-identity.local.md` (gitignored)

See [the design doc](../../92023.10%20Requirements%20%26%20design/claude-identity%20plugin%20design.md) for full schema.

## Hook ordering

Other plugins reading sessions-meta should:
1. Use a SessionStart hook with a distinct script name (avoid bug #29724).
2. Self-initialize a missing sidecar as a defensive fallback.
3. Read sessions-meta on UserPromptSubmit / PostToolUse via mtime-pull.

## Development

```
cd plugins/claude-identity

python3 -m pytest -v

shellcheck hooks/*.sh
```
