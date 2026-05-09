# claude-code-plugins

A collection of Claude Code plugins for macOS, integrating Apple apps, local
tools, and productivity utilities into the Claude Code terminal environment.

Published as the `claude-code-plugins-mac` marketplace package.

## Plugins

| Plugin | Version | Description | Source |
|--------|---------|-------------|--------|
| apple-mail | 0.1.0 | Apple Mail -- search, triage, archive, and draft replies from the command line | [apple-mail-py](https://github.com/nelsonlove/apple-mail-py) |
| apple-music | 0.3.0 | Apple Music control and intelligent playlist curation | [apple-music-py](https://github.com/nelsonlove/apple-music-py) |
| apple-notes | 0.2.0 | Apple Notes -- read, create, search, and triage notes via MCP | [apple-notes-py](https://github.com/nelsonlove/apple-notes-py) |
| backlog | 1.0.0 | Backlog.md task tracker -- manage markdown-based backlogs via MCP | local |
| claude-notifications | 0.1.0 | Persistent cross-session notification inbox for automated agents and cron jobs | local |
| claude-tone | 0.1.0 | Unique pentatonic notification tone per session (plays on Stop and Notification events) | local |
| dayone | 1.0.0 | Day One journaling -- create, read, and update journal entries via MCP | local |
| homebrew-audit | 0.2.0 | Audit and triage Homebrew packages via an org-mode workflow with babel action blocks | local |
| jd | 0.1.0 | Johnny Decimal filing system integration | [jd-cli](https://github.com/nelsonlove/jd-cli) |
| mail | 0.0.1 | Mail handling with himalaya | local |
| marked-preview | 0.1.0 | Generate markdown and preview in Marked 2 | local |
| omnifocus | 3.0.0 | OmniFocus task management -- create, update, complete, and query tasks and projects via MCP | [omnifocus-py](https://github.com/nelsonlove/omnifocus-py) |
| pim | 1.0.0 | Personal information management -- unified graph across notes, tasks, calendar, email, contacts | [pim](https://github.com/nelsonlove/pim) |
| safari | 0.2.0 | Safari bookmarks and reading list -- search, export, and manage | [safari-py](https://github.com/nelsonlove/safari-py) |
| steipete-scripts | 0.0.1 | Skills ported from steipete/agent-scripts (attribution: Peter Steinberger) | local |
| things | 0.1.0 | Things.app task management -- query tasks, projects, areas, and tags | [things-py](https://github.com/nelsonlove/things-py) |
| tomatobar | 1.0.0 | Control TomatoBar Pomodoro timer and query session state | local |

One additional plugin (`org-roam-claude`) exists in the `plugins/` directory
but is not yet published to the marketplace.

## Installation

### From the marketplace

```
claude plugins install claude-code-plugins-mac
```

This installs all plugins listed in the marketplace manifest.

### From source

Clone the repo and install the local package:

```
git clone https://github.com/nelsonlove/claude-code-plugins.git
claude plugins install ./claude-code-plugins
```

### External plugin dependencies

Several plugins are sourced from separate Git repos (see Source column above).
The marketplace manifest references these via `git-subdir`, so they are fetched
automatically on install. Their CLI tools must be installed separately:

- `apple-mail` -- requires [apple-mail-py](https://github.com/nelsonlove/apple-mail-py)
- `apple-music` -- requires [apple-music-py](https://github.com/nelsonlove/apple-music-py)
- `apple-notes` -- requires [apple-notes-py](https://github.com/nelsonlove/apple-notes-py)
- `omnifocus` -- requires [omnifocus-py](https://github.com/nelsonlove/omnifocus-py)
- `safari` -- requires [safari-py](https://github.com/nelsonlove/safari-py)
- `things` -- requires [things-py](https://github.com/nelsonlove/things-py)
- `jd` -- requires [jd-cli](https://github.com/nelsonlove/jd-cli)
- `pim` -- requires [pim](https://github.com/nelsonlove/pim)

## Development

### Repository structure

```
.claude-plugin/
  marketplace.json    # Marketplace package manifest
plugins/
  <name>/             # Each plugin directory
    commands/         # Slash commands (optional)
    skills/           # Skills (optional)
    hooks/            # Hooks with hooks.json (optional)
    agents/           # Agents (optional)
    scripts/          # Supporting scripts (optional)
    server.py         # MCP server (optional)
    README.md         # Plugin docs (optional)
```

Plugins that live in external repos follow the same layout under
`plugin/claude-code/` in their respective repositories.

### Adding a plugin

1. Create a directory under `plugins/<name>/` with the desired components
   (commands, skills, hooks, agents, MCP server).
2. Add an entry to `.claude-plugin/marketplace.json` with name, source,
   description, and version.
3. For external repos, use the `git-subdir` source format pointing to the
   repo URL, path, and ref.

### Plugin components

- **Commands** (`commands/`): Slash commands invoked with `/<name>`.
- **Skills** (`skills/`): Contextual capabilities Claude loads on demand.
- **Hooks** (`hooks/`): Event-driven scripts triggered on PreToolUse, PostToolUse, Stop, Notification, etc.
- **Agents** (`agents/`): Subagents for specialized multi-step workflows.
- **MCP servers** (`server.py`): Model Context Protocol servers exposing tools and resources.

## Author

Nelson Love ([nelson@nelson.love](mailto:nelson@nelson.love))
