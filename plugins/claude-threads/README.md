# claude-threads

Inter-session threaded conversations for Claude Code.

Sessions exchange persistent multi-message `.md` threads filtered by subscription tags. Three poll hooks (SessionStart / UserPromptSubmit / PostToolUse) cover boot, active human, and active autonomous regimes — all running as shell scripts with zero token cost when empty.

## Depends on

- [`claude-identity`](../claude-identity/) — provides handle resolution and the match function. Install both.

## Install

Part of the `claude-code-plugins-mac` marketplace:

```
/plugin install claude-code-plugins-mac
```

## Slash commands

- `/thread:start <scope-csv> <topic>` — open a new thread
- `/thread:reply <thread-id> <message>` — append to existing
- `/thread:list [--scope <pat>] [--status <enum>]` — show subscribed threads
- `/thread:show <thread-id>` — render a thread as conversation
- `/thread:close <thread-id>` — set status to resolved

Tag/scope and session-listing are in `/identity:*` (from `claude-identity`).

## Configuration

- **Global**: `~/.claude/claude-threads/config.toml`
- **Per-project**: `<project>/.claude/claude-threads.local.md` (gitignored)

```toml
# Example global config
[paths]
threads_dir = "~/.claude/threads"

[frontmatter]
prefix = "thread-"

[scope]
auto_tag_cwd = false
```

See [the design doc](../../92023.10%20Requirements%20%26%20design/claude-threads%20plugin%20design.md) for full schema.

## Migration

If you have pre-existing 02.14-style threads (the original convention), run:

```
python3 migrations/migrate_02_14.py <threads-dir> --scope "02.14"
```

Idempotent.

## Development

```
cd plugins/claude-threads
python3 -m pytest -v
shellcheck hooks/*.sh
tests/test_hooks.sh
```
