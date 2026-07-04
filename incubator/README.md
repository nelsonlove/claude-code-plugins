# incubator

Work-in-progress plugins that are **not** published to the marketplace yet.

Each plugin here is developed until it's ready, then extracted to its own
standalone `cc-<name>` repository (history preserved via `git subtree split` or
`git filter-repo`) and added to `.claude-plugin/marketplace.json` as a
`github` source — the same shape as every published plugin.

Nothing in this directory is installed by the marketplace.

Current occupants:

- `batch-issues`
- `org-roam-claude`
