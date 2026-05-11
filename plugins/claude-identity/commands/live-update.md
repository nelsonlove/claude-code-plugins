---
description: Write or update this agent's live working note in the Obsidian vault (per-session preview Nelson follows live).
allowed-tools: ["mcp__claude-identity__update_live_note"]
argument-hint: "[--section <name>] [--cadence <description>] <body>"
---

# /claude-identity:live-update

Parse `$ARGUMENTS`:

- `--section <name>` (optional): which section to write into. Default: `Live notes`. Section names with spaces should be quoted (`--section "Current task"`). Unknown section names are appended as new sections.
- `--cadence <description>` (optional): freeform cadence string written to note frontmatter (e.g. `"every 5 min"`, `"as work progresses"`). Defaults to `"as work progresses"`.
- Remaining argument tokens (joined with spaces): the body content for the target section.

Then call the `update_live_note` MCP tool with `body`, optional `section`, optional `cadence`.

## Behavior

- First invocation creates the note at `<vault>/00-09 System/03 LLMs & agents/03.15 Agent live notes/<handle>.md` from the canonical template. Substitutes `{{handle}}`, `{{date}}`, `{{time}}`, `{{session-id}}`, `{{session-id-short}}`, `{{scope-csv}}`, `{{cadence}}`.
- Subsequent invocations update the targeted section in place; frontmatter `modified`, `scope` (from `claude-identity:list_tags`), and `cadence` are refreshed on every call.
- **Fails fast** if the session's handle is still the UUID-prefix default. Run `/claude-identity:rename <name>` (or wait for the SessionStart wordlist auto-assign) before invoking this.

## Output

On success, the tool returns `{ok: true, path: <str>, created: <bool>}`. Report whether the note was created or updated, and the path.

On error (UUID-default handle, no registry entry, etc.), surface the error message to the user with a suggested fix.

## Examples

```
/claude-identity:live-update reading thread fd218909 and waiting on cairn's PR
```

Writes "reading thread fd218909 and waiting on cairn's PR" into the `Live notes` section.

```
/claude-identity:live-update --section "Current task" implementing handle/session decoupling per issue #24
```

Replaces the `Current task` section body.

```
/claude-identity:live-update --cadence "every 5 min" --section "Live notes" working on the PR
```

Updates `Live notes` and sets cadence to `every 5 min` in frontmatter.
