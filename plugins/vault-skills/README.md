# vault-skills (Claude Code plugin)

The landing plugin for skills and agents authored as notes in Nelson's Obsidian vault. It carries no vault content of its own: the exporter writes the vault's projection into this directory, and Claude Code loads it in place.

The exporter is the **skills satellite of [obsidian-mcp-suite](https://github.com/nelsonlove/obsidian-mcp-suite)** — `packages/skills`, published as `@vault-mcp/skills`. This plugin ships no MCP server of its own.

## What is tracked and what is generated

- `.claude-plugin/plugin.json` — the manifest. Static, tracked.
- `skills/new-skill/` — the static authoring skill and its bundled `conventions.md`. Tracked; this is the plugin's own payload, not vault output.
- `skills/`, `agents/`, `hooks/` — landing directories the exporter writes into. Their generated contents are git-ignored, along with the `.vault-skills-manifest.json` the exporter drops beside them; only the `.gitkeep` placeholders are tracked, so a fresh checkout already has the directories the exporter expects.

Do not hand-edit the generated files. The source of truth is the vault note; edit it and re-export.

## How it gets loaded

The plugin is served from this repository through the `claude-code-plugins-mac` marketplace, and Claude Code installs it into `~/.claude/plugins/cache/claude-code-plugins-mac/vault-skills/<version>/`. The exporter writes into the installed copy, so no symlink is needed.

Skills invoke as `/vault-skills:<name>`; agents as `vault-skills:<name>`. The exporter builds a tree from each note's `parent` edge — every agent owns its skills, preloaded, and delegates to its child agents.

## History

Until 2026-09-26 this plugin lived at `claude-code/` inside `nelsonlove/obsidian-vault-skills`, which GitHub has had archived since 2026-08-11, and the catalogue sourced it from there. Nelson ruled that vault-skills is not retired, so the plugin moved here and the exporter is being rebuilt as the suite satellite named above. The move is byte-for-byte; the manifest's version and description and this README are the only things revised.
