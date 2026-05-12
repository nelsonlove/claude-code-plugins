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

- `/claude-identity:whoami` — print this session's identity
- `/claude-identity:sessions` — list all live sessions
- `/claude-identity:scope add|rm|list [<tag>] [--session <handle>]` — manage tags
- `/claude-identity:match <scope-csv>` — debug scope-pattern matches
- `/claude-identity:rename <handle>` — agent self-rename. Writes the persistent agent handle to the sessions-meta sidecar (v0.1.3+: decoupled from CC's built-in `/rename`, which controls the session topic/focus label). Validates format, rejects collisions with other live sessions.
- `/claude-identity:live-update [--section <name>] [--cadence <desc>] <body>` — write or update this agent's live working note in the Obsidian vault. Created on first invocation at `03 LLMs & agents/03.15 Agent live notes/<handle>.md`; updated in place thereafter. Nelson follows these live in Obsidian.

## Handle vs CC name (v0.1.3+)

The plugin distinguishes two identifiers:

- **Handle** (persistent agent name like `quill`, `wren`, `cairn`): lives in the sessions-meta sidecar at `~/.claude/sessions-meta/<session-id>.json`. Set via `/claude-identity:rename` or auto-assigned by the SessionStart hook from a curated single-word pool (`lib/wordlist.py`). Used by claude-threads, status line display, cross-session addressing.
- **Name** (session topic/focus): lives in CC's registry at `~/.claude/sessions/<pid>.json`. Set via CC's built-in `/rename <topic>`. Shown wherever CC natively displays the session name.

The two are independent. `/rename` no longer touches the handle (as of v0.1.3); `/claude-identity:rename` no longer touches the topic.

Resolution chain (back-compat): sidecar `handle` → CC `name` (v0.1.2 legacy) → UUID-prefix fallback.

## Convenience tools

- `bin/jump <handle>` — opens an agent's live note in Obsidian via the URL scheme. Zero token cost; runs `osascript` + `open` directly. Put on your PATH or alias as `obsidian-jump`.

## Statusline integration

Recommended statusline snippet to display this session's subscribed scope tags. Add to your `~/.claude/statusline-command.sh` (the script CC invokes per `settings.json`'s `statusLine` config):

```bash
# Subscribed scope tags from claude-identity's sessions-meta sidecar
session_id=$(echo "$input" | jq -r '.session_id // empty')
scope_tags=""
if [ -n "$session_id" ]; then
  sidecar="$HOME/.claude/sessions-meta/$session_id.json"
  if [ -f "$sidecar" ]; then
    scope_tags=$(jq -r '.tags // [] | join(", ")' < "$sidecar" 2>/dev/null)
  fi
fi

# In your output assembly:
if [ -n "$scope_tags" ]; then
  printf '  scope: %s' "$scope_tags"
fi
```

This reads the same sidecar file that `add_tag` / `remove_tag` write to, so the statusline updates as soon as you `/claude-identity:scope add foo`. No restart needed.

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
