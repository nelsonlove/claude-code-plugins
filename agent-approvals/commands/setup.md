---
name: setup
description: Install the agent-approvals dependency chain (pickle, mdbase-cli, tickle) and wire up the cold-resume job. Run once.
---

Install everything agent-approvals needs and report status. Requires Homebrew
(for pickle + mdbase-cli) and network access (for the tickle release binary).

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/setup.sh"
```

Then: summarize what installed vs. what's missing. If no Pickle collection is
configured, tell the user to run
`pickle collections add <name> <path-to-their-Obsidian-Pickle-folder> --set-default`
pointing at the folder their Pickle Obsidian plugin manages.
