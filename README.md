# claude-code-plugins

A **marketplace** of Claude Code plugins for macOS — integrating Apple apps,
local tools, and productivity utilities into the Claude Code terminal
environment.

This repository is the marketplace manifest only. **Every plugin lives in its
own repository** and is referenced from `.claude-plugin/marketplace.json`.
Published as the `claude-code-plugins-mac` marketplace.

## Installation

Add the marketplace, then install the plugins you want:

```
/plugin marketplace add nelsonlove/claude-code-plugins
/plugin install <name>@claude-code-plugins-mac
```

Each plugin is fetched directly from its own repo. Plugins backed by a CLI or
Python package (the `*-py` repos below) require that tool to be installed
separately — see each plugin's own README.

## Plugins

Every plugin is sourced from a standalone repository. Two source styles are
used, and the marketplace mixes them freely:

- **`github`** — the repo *is* the plugin (`.claude-plugin/plugin.json` at its
  root). These are the `cc-*` repos.
- **`git-subdir`** — the plugin lives at `plugin/claude-code/` inside a larger
  repo that also ships a CLI/Python package (the `*-py` repos, plus `jd` and
  `pim`).

| Plugin | Version | Repository |
|--------|---------|------------|
| apple-mail | 0.1.0 | [apple-mail-py](https://github.com/nelsonlove/apple-mail-py) |
| apple-music | 0.3.0 | [apple-music-py](https://github.com/nelsonlove/apple-music-py) |
| apple-notes | 0.2.0 | [apple-notes-py](https://github.com/nelsonlove/apple-notes-py) |
| backlog | 1.0.0 | [cc-backlog](https://github.com/nelsonlove/cc-backlog) |
| calibre | 0.1.2 | [cc-calibre](https://github.com/nelsonlove/cc-calibre) |
| claude-goodbye | 0.2.0 | [cc-claude-goodbye](https://github.com/nelsonlove/cc-claude-goodbye) |
| claude-identity | 0.1.4 | [cc-claude-identity](https://github.com/nelsonlove/cc-claude-identity) |
| claude-notebook | 0.9.0 | [cc-claude-notebook](https://github.com/nelsonlove/cc-claude-notebook) |
| claude-threads | 0.2.4 | [cc-claude-threads](https://github.com/nelsonlove/cc-claude-threads) |
| claude-tone | 0.1.0 | [cc-claude-tone](https://github.com/nelsonlove/cc-claude-tone) |
| dayone | 1.0.0 | [cc-dayone](https://github.com/nelsonlove/cc-dayone) |
| homebrew-audit | 0.2.0 | [cc-homebrew-audit](https://github.com/nelsonlove/cc-homebrew-audit) |
| jd | 0.1.0 | [jd-cli](https://github.com/nelsonlove/jd-cli) |
| mail | 0.0.1 | [cc-mail](https://github.com/nelsonlove/cc-mail) |
| marked-preview | 0.1.0 | [cc-marked-preview](https://github.com/nelsonlove/cc-marked-preview) |
| omnifocus | 3.0.0 | [omnifocus-py](https://github.com/nelsonlove/omnifocus-py) |
| pim | 1.0.0 | [pim](https://github.com/nelsonlove/pim) |
| safari | 0.2.0 | [safari-py](https://github.com/nelsonlove/safari-py) |
| steipete-scripts | 0.0.1 | [cc-steipete-scripts](https://github.com/nelsonlove/cc-steipete-scripts) |
| things | 0.1.0 | [things-py](https://github.com/nelsonlove/things-py) |
| tomatobar | 1.0.0 | [cc-tomatobar](https://github.com/nelsonlove/cc-tomatobar) |
| zotero | 0.1.0 | [cc-zotero](https://github.com/nelsonlove/cc-zotero) |

Work-in-progress plugins that are not yet published live under
[`incubator/`](incubator/).

## Adding or updating a plugin

1. Develop the plugin in its own repo (or under [`incubator/`](incubator/)
   until it's ready to extract).
2. Ensure the repo has a `.claude-plugin/plugin.json` with `name`, `version`,
   and `description`. For `cc-*` repos this sits at the repo root; for
   `git-subdir` plugins it sits under `plugin/claude-code/`.
3. Tag the release (`vX.Y.Z`) in the plugin's repo.
4. Add or update its entry in `.claude-plugin/marketplace.json`:
   - `cc-*` repo: `{"source":"github","repo":"nelsonlove/cc-<name>","ref":"vX.Y.Z"}`
   - subdir repo: `{"source":"git-subdir","url":"…","path":"plugin/claude-code","ref":"…"}`
   Keep the entry's `version` in sync with the `ref` tag.

The design and migration history for this split live in
[`docs/superpowers/specs/`](docs/superpowers/specs/) and
[`docs/superpowers/plans/`](docs/superpowers/plans/).

## Author

Nelson Love ([nelson@nelson.love](mailto:nelson@nelson.love))
