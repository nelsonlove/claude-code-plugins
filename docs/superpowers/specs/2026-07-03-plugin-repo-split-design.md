# Design: split the plugin monorepo into per-plugin repos + a pure marketplace

**Date:** 2026-07-03
**Repo:** `nelsonlove/claude-code-plugins` (public)
**Status:** design approved, pending spec review → implementation plan

## Goal

Turn `claude-code-plugins` from a monorepo-that-also-hosts-plugins into a **pure
marketplace repo** whose `.claude-plugin/marketplace.json` references every plugin
from its own standalone GitHub repo. This buys, per Nelson: independent versioning
and release cadence per plugin, standalone shareable installs, a smaller-blast-radius
top-level repo, and one consistent distribution model across all plugins.

## Starting state (verified 2026-07-03)

The marketplace `claude-code-plugins-mac` lists **22 plugins** across two source
styles that already coexist correctly:

- **8 already one-plugin-per-repo** via `git-subdir` — the Python-companion plugins,
  which live at `plugin/claude-code` inside their `*-py` repos because those repos
  also carry a Python package: `jd` (jd-cli), `things` (things-py), `omnifocus`
  (omnifocus-py), `apple-music`, `apple-notes`, `apple-mail`, `safari`, `pim`.
  **These are already in their target shape and are not touched by this work.**
- **14 embedded locally** under `plugins/<name>` as `"./plugins/<name>"` sources —
  the pure plugins with no CLI companion. **These are what we extract.**

Each of the 14 already has its own `.claude-plugin/plugin.json` at its directory
root, so a `git subtree split` that rewrites that directory to repo root produces a
valid, self-describing root-level plugin repo with **zero manifest surgery**.

### Non-published directories in `plugins/`

Six dirs exist under `plugins/` but are **not** in the manifest:

- `plugins/jd` — stale duplicate; `jd` ships from `jd-cli` via git-subdir. Remove.
- `plugins/batch-issues`, `plugins/claude-notifications`, `plugins/imessage-research`,
  `plugins/org-roam-claude` — WIP / incubating, not published.
- `plugins/_archived/` — deprecated code (contains `claude-notifications`, retired in #16).

## Decisions (all settled during brainstorming)

| Decision | Choice |
|---|---|
| Repo layout for extracted plugins | **Plugin at repo root** — whole repo IS the plugin. Referenced as `{"source":"github","repo":"nelsonlove/cc-<name>","ref":"v<x.y.z>"}`. |
| Repo naming | **`cc-` prefix on the repo/URL only.** Plugin `name` in `plugin.json` and the manifest stays clean (`claude-notebook`, `mail`, …). |
| History | **Preserve per-plugin history** via `git subtree split` (fallback `git filter-repo` for renamed paths). |
| Visibility | **Public**, gated behind a mandatory per-plugin privacy scan before first push. |
| Archived divorce strings | **Delete the tree AND rewrite history** to purge, then force-push. |
| Spec location | **In-repo** `docs/superpowers/specs/`. |

### Repo name map (14 extractions)

| Plugin (manifest `name`) | New repo | Current version → tag |
|---|---|---|
| backlog | `cc-backlog` | v1.0.0 |
| calibre | `cc-calibre` | v0.1.1 |
| claude-goodbye | `cc-claude-goodbye` | v0.2.0 |
| claude-identity | `cc-claude-identity` | v0.1.3 |
| claude-notebook | `cc-claude-notebook` | v0.9.0 |
| claude-threads | `cc-claude-threads` | v0.2.2 |
| claude-tone | `cc-claude-tone` | v0.1.0 |
| dayone | `cc-dayone` | v1.0.0 |
| homebrew-audit | `cc-homebrew-audit` | v0.2.0 |
| mail | `cc-mail` | v0.0.1 |
| marked-preview | `cc-marked-preview` | v0.1.0 |
| steipete-scripts | `cc-steipete-scripts` | v0.0.1 |
| tomatobar | `cc-tomatobar` | v1.0.0 |
| zotero | `cc-zotero` | v0.1.0 |

Versions are read from each plugin's `plugin.json` at extraction time; the table
above is indicative.

## End state

- `claude-code-plugins` contains: `.claude-plugin/marketplace.json`, `README.md`,
  `docs/`, `.claude/` (dev tooling), `TODO.md`, and an `incubator/` dir for WIP
  plugins. **No published plugin is embedded.** No `plugins/` dir, no `_archived/`.
- `marketplace.json` lists 22 plugins, **all external**: 8 unchanged `git-subdir` +
  14 new `github` root-level entries.
- 14 new `nelsonlove/cc-*` public repos, each a standalone installable plugin with
  preserved history and a version tag.

## Privacy scan findings (2026-07-03)

Ran secret + divorce/cat-26 + family-name + contact-PII scans across `plugins/`,
`docs/`, `README.md`.

- **The 14 plugins to extract are clean** of secrets, divorce/cat-26 content, and
  family names. They contain hardcoded `/Users/nelson/...` paths in docs/tests
  (cosmetic; GitHub handle is already public). No hardcoded credentials anywhere.
- **Only tracked sensitive content in the whole public repo:** 3 example-string
  lines in `plugins/_archived/claude-notifications/server.py`
  (`"divorce email archive"`, `"divorce-email-cron"`) — public on `main` today.
- `plugins/imessage-research/` (a `matilda|tilly` search example) is **untracked /
  never pushed** — safe, but must be scrubbed before it is ever committed.

## Work plan (phases)

### Phase 0 — Privacy remediation (do first, independent of extraction)
1. Full-history scan of the monorepo (`git log -p` / `git grep` across all refs) for
   `divorce`, `matilda`/`tilly`, `jennifer`, `helen morse`, secrets, phone/SSN.
2. `git rm -r plugins/_archived` (and any other confirmed-sensitive tracked file).
3. `git filter-repo` to purge the confirmed sensitive strings/paths from **all**
   history, then **force-push** `main`. Caveat: rewrites public history; existing
   clones/forks diverge. Coordinate before force-pushing.
4. Confirm `git grep` across all refs returns clean.

### Phase 1 — Pipeline shakedown (one low-stakes plugin)
Run the full per-plugin procedure on **`tomatobar`** (self-contained, low-risk) end
to end, verify it installs standalone from `cc-tomatobar`, then proceed to the rest.

### Phase 2 — Per-plugin extraction (repeat for each of the 14)
For plugin `<name>`:
1. **Privacy gate** — scan `plugins/<name>` for secrets + divorce/cat-26/PII. Any
   hit blocks this plugin until resolved. (The 14 pass today; the gate is a standing
   guard, also protecting future incubator extractions.)
2. `git subtree split -P plugins/<name> -b split/<name>`. If the plugin's path
   changed historically and the split drops pre-rename commits, fall back to
   `git filter-repo --path plugins/<name> --path-rename plugins/<name>/:`.
3. `gh repo create nelsonlove/cc-<name> --public`.
4. `git push git@github.com:nelsonlove/cc-<name>.git split/<name>:main`.
5. Tag `v<version>` (from `plugin.json`) in the new repo.
6. **Verify**: install the plugin from `{source:github, repo:nelsonlove/cc-<name>,
   ref:v<version>}`; spot-check one command/skill resolves.
7. Flip the manifest entry from `"./plugins/<name>"` to the `github` source.
8. `git rm -r plugins/<name>` in the monorepo; commit.

Each plugin is one commit (or one PR). **The marketplace stays fully functional
throughout** — a mix of `./plugins/…` and `github` entries is valid, so extraction
is incremental and reversible per-plugin.

### Phase 3 — Incubator + cleanup
1. `mkdir incubator/`; `git mv` the WIP dirs (`batch-issues`, `claude-notifications`,
   `imessage-research`, `org-roam-claude`) into it. Scrub `imessage-research`'s
   `matilda|tilly` example before it is committed.
2. `git rm -r plugins/jd` (stale duplicate of the jd-cli git-subdir entry) after
   confirming it is not newer than jd-cli's.
3. Remove the now-empty `plugins/` dir.
4. Update `README.md` to describe the repo as a pure marketplace and document the
   `incubator/` convention.

### Phase 4 — Optional cosmetic pass (low priority, can defer)
Neutralize hardcoded `/Users/nelson` paths in docs/fixtures → `$HOME`/`~`/generic
examples across the extracted repos.

## Verification strategy

- After each manifest edit: validate `marketplace.json` parses and lists 22 plugins.
- After each extraction: `/plugin` install from the new `github` source succeeds and
  a representative command/skill loads.
- After Phase 0: `git grep` across all refs is clean of the target terms.
- Final: fresh clone of `claude-code-plugins` contains no embedded published plugin;
  all 22 install from external sources.

## Risks & notes

- **History force-push (Phase 0)** rewrites public history. Any clone/fork diverges;
  do it deliberately and note it. The purged strings are generic examples, but Nelson
  explicitly wants them gone from history.
- **`subtree split` path-rename gap** — spot-check history depth in each new repo;
  use `filter-repo` where the split looks truncated.
- **Standalone runtime deps** — several plugins read from Nelson's JD/vault tree at
  runtime (e.g. claude-notebook writes the friction log, claude-threads reads a
  threads dir). These paths are configured, not secret; public exposure is fine, but
  note in each repo's README that paths are environment-specific.
- **`ref` pinning vs `main`** — pinning `ref: v<version>` gives reproducible installs
  but means the manifest must bump when a plugin releases. Alternative: point `ref` at
  `main` for auto-latest. Default here is version-pinned; revisit if bumping churn is
  annoying.
