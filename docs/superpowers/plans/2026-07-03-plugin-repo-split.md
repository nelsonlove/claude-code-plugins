# Plugin Repo Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the 14 locally-embedded plugins from `nelsonlove/claude-code-plugins` into standalone public `cc-*` GitHub repos and reduce the monorepo to a pure marketplace, after purging sensitive strings from history.

**Architecture:** Each embedded plugin becomes its own root-level plugin repo (`.claude-plugin/plugin.json` at repo root) with preserved git history via `git subtree split`. The marketplace's `.claude-plugin/marketplace.json` flips each entry from a `"./plugins/<name>"` local source to a `{"source":"github","repo":"nelsonlove/cc-<name>","ref":"v<version>"}` external source. Extraction is incremental and per-plugin — the marketplace stays installable throughout because local and github sources coexist. The 8 existing `git-subdir` (`*-py`) plugins are untouched.

**Tech Stack:** git (`subtree`, `filter-repo`), `gh` CLI, Python 3 (JSON validation), bash.

## Global Constraints

- Marketplace name stays `claude-code-plugins-mac`; plugin `name` values stay clean (no `cc-` prefix in `plugin.json` or manifest). The `cc-` prefix appears ONLY in repo names/URLs.
- New repos: `nelsonlove/cc-<plugin-name>`, **public**.
- Every extraction preserves history (`git subtree split`); fall back to `git filter-repo --path plugins/<name> --path-rename plugins/<name>/:` if the split truncates history.
- A plugin may not be pushed to a public repo until its privacy scan (secrets + `divorce`/cat-26/`matilda`/`tilly`/`jennifer`/`helen morse` + phone/SSN) passes clean.
- `ref` in each manifest entry pins `v<version>` where `<version>` is the **authoritative `plugin.json` version** (backfilled/reconciled in Task 1). `plugin.json` wins over the manifest under default strict mode.
- Work happens in the worktree at `.claude/worktrees/plugin-repo-split-spec` on branch `worktree-plugin-repo-split-spec`. Monorepo edits are PR'd to `main`, not pushed directly.
- The Phase-0 history force-push (Task 0) is the only irreversible step and is done FIRST, in isolation, before any extraction depends on the monorepo state. **Requires explicit human go-ahead at that step.**

## Plugin → repo → version table (authoritative for Tasks 2–3)

`plugin.json` version is source of truth; where blank, backfill from the marketplace value shown in parens (Task 1).

| # | plugin `name` | new repo | tag |
|---|---|---|---|
| 1 | tomatobar | cc-tomatobar | v1.0.0 |
| 2 | calibre | cc-calibre | v0.1.2 |
| 3 | claude-goodbye | cc-claude-goodbye | v0.2.0 |
| 4 | claude-identity | cc-claude-identity | v0.1.4 |
| 5 | claude-notebook | cc-claude-notebook | v0.9.0 |
| 6 | claude-threads | cc-claude-threads | v0.2.4 |
| 7 | claude-tone | cc-claude-tone | v0.1.0 |
| 8 | homebrew-audit | cc-homebrew-audit | v0.2.0 |
| 9 | marked-preview | cc-marked-preview | v0.1.0 |
| 10 | zotero | cc-zotero | v0.1.0 |
| 11 | backlog | cc-backlog | v1.0.0 (backfill) |
| 12 | dayone | cc-dayone | v1.0.0 (backfill) |
| 13 | mail | cc-mail | v0.0.1 (backfill) |
| 14 | steipete-scripts | cc-steipete-scripts | v0.0.1 (backfill) |

## File structure

- `.claude-plugin/marketplace.json` — edited 14 times (one source flip per plugin), each in its own commit.
- `plugins/<name>/` — 14 dirs removed (`git rm`) after their extraction; `plugins/_archived/` removed in Task 0.
- `incubator/` — new dir; receives `batch-issues`, `claude-notifications`, `imessage-research`, `org-roam-claude` (Task 4).
- `README.md` — rewritten in Task 4 to describe a pure marketplace.
- `scripts/extract-plugin.sh` — new helper implementing the per-plugin procedure (Task 2), reused by Task 3.
- New external repos: `nelsonlove/cc-*` (14), each with `.claude-plugin/plugin.json` at root.

---

### Task 0: Phase 0 — purge sensitive strings from history and force-push

**Files:**
- Remove: `plugins/_archived/` (tracked; contains the divorce example strings)
- Rewrite: all history of `nelsonlove/claude-code-plugins`

**Interfaces:**
- Produces: a clean `main` history with no `divorce`/family-name/secret strings, on which all later tasks build.

> **EXECUTED 2026-07-04 — scope expanded during execution.** The full-history scan
> surfaced sensitive content in FOUR history-only paths, not one:
> `plugins/_archived/`, `docs/plans/2026-03-08-claude-notifications.md` (contained the
> real cat-26 `26 Divorce/26.06 Legal email archive` path), historical
> `plugins/claude-notifications/`, and `plugins/session-name/` (example label
> `'divorce reorg'`). A separate finding — `"custody case"` in the **live public
> `nelsonlove/pim` repo** (`docs/pim-matrix-ontology.md`) — was scrubbed in that repo too.
> Actions taken: `git filter-repo` removing all four paths + replacing
> `divorce email archive`/`divorce-email-cron`/`custody case`/`26 Divorce`/`Legal email archive`;
> monorepo force-pushed `main` `4687365`→`1146c6b` (144→137 commits, all markers 0, tip intact);
> pim unarchived → force-pushed `54e0f39`→`b4acbc3` (0 custody hits) → re-archived.
> Worktree rebased onto rewritten `main`. The step-by-step below is the original plan; the
> executed command set matches it with the expanded `--path` list.

- [ ] **Step 1: Full-history scan for every sensitive term (record the hits)**

Run from a full (non-worktree) clone of the monorepo:
```bash
cd /Users/nelson/repos/claude-code-plugins
for t in divorce matilda tilly jennifer "helen morse" custody settlement; do
  echo "== $t =="; git grep -n -i "$t" $(git rev-list --all) -- 'plugins/*' 'docs/*' 'README.md' 2>/dev/null | head
done | tee /Users/nelson/.claude/jobs/edecadfc/tmp/history-scan.txt
```
Expected: hits only in `plugins/_archived/claude-notifications/server.py` (the 3 known lines) across history. If any OTHER path appears, add it to the removal set in Step 3 before proceeding.

- [ ] **Step 2: Remove the archived tree in the working branch**

```bash
git rm -r plugins/_archived
git commit -m "chore: remove deprecated _archived plugins (pre-history-purge)"
```
Expected: `plugins/_archived` gone from the working tree.

- [ ] **Step 3: Purge the strings/paths from ALL history with filter-repo**

```bash
cat > /Users/nelson/.claude/jobs/edecadfc/tmp/replacements.txt <<'EOF'
divorce email archive==>expense report archive
divorce-email-cron==>report-cron
EOF
# Remove the archived path from all history AND scrub any residual example strings:
git filter-repo --force \
  --path plugins/_archived --invert-paths \
  --replace-text /Users/nelson/.claude/jobs/edecadfc/tmp/replacements.txt
```
Expected: filter-repo rewrites history and reports rewritten commits. (If `git filter-repo` is not installed: `brew install git-filter-repo`.)

- [ ] **Step 4: Verify history is clean**

```bash
for t in divorce "divorce-email-cron" matilda tilly jennifer; do
  echo "== $t =="; git grep -n -i "$t" $(git rev-list --all) 2>/dev/null | head
done
```
Expected: no output for any term.

- [ ] **Step 5: HUMAN GATE — confirm, then force-push**

> STOP. Force-pushing rewrites public history; clones/forks diverge. Get explicit go-ahead from Nelson for this specific step.

```bash
git remote -v   # confirm origin is nelsonlove/claude-code-plugins
git push --force-with-lease origin main
```
Expected: `main` updated on GitHub; `_archived` and the strings gone from the public repo.

- [ ] **Step 6: Refresh the worktree onto rewritten history**

Because history was rewritten, recreate the working worktree from the new `main`:
```bash
git worktree remove --force .claude/worktrees/plugin-repo-split-spec 2>/dev/null || true
git worktree add .claude/worktrees/plugin-repo-split-spec -b split-work origin/main
```
Expected: fresh worktree on rewritten history. Re-apply the spec/plan commit if it was dropped by the rewrite (cherry-pick from reflog or re-add the two doc files).

---

### Task 1: Pre-flight — reconcile plugin versions

**Files:**
- Modify: `plugins/{backlog,dayone,mail,steipete-scripts}/.claude-plugin/plugin.json` (add `version`)

**Interfaces:**
- Produces: every one of the 14 `plugin.json` files has a `version` matching the tag table, so each extracted repo is self-describing and its tag is unambiguous.

- [ ] **Step 1: Write a check that fails for missing versions**

```bash
for n in backlog dayone mail steipete-scripts; do
  python3 -c "import json;v=json.load(open('plugins/$n/.claude-plugin/plugin.json')).get('version');print('$n',v);assert v,'missing'" || echo "NEEDS BACKFILL: $n"
done
```
Expected: prints `NEEDS BACKFILL` for the four plugins (version currently absent).

- [ ] **Step 2: Backfill the four versions from the tag table**

Edit each `plugin.json` to add `"version"`: `backlog` → `1.0.0`, `dayone` → `1.0.0`, `mail` → `0.0.1`, `steipete-scripts` → `0.0.1`. (Use the Edit tool; insert the `version` key alongside `name`.)

- [ ] **Step 3: Re-run the check — now clean**

```bash
for n in backlog dayone mail steipete-scripts; do
  python3 -c "import json;v=json.load(open('plugins/$n/.claude-plugin/plugin.json'))['version'];print('$n',v)"
done
```
Expected: prints a version for all four, no assertion error.

- [ ] **Step 4: Commit**

```bash
git add plugins/backlog plugins/dayone plugins/mail plugins/steipete-scripts
git commit -m "chore(plugins): backfill version field for backlog/dayone/mail/steipete-scripts"
```

---

### Task 2: Extraction procedure + shakedown on `tomatobar`

**Files:**
- Create: `scripts/extract-plugin.sh`
- Modify: `.claude-plugin/marketplace.json` (flip `tomatobar` entry)
- Remove: `plugins/tomatobar/`
- New repo: `nelsonlove/cc-tomatobar`

**Interfaces:**
- Produces: `extract-plugin.sh <name> <version>` — the reusable subroutine Task 3 applies to rows 2–14. Given a plugin name and version it: privacy-scans, subtree-splits, creates the public repo, pushes, tags, and prints the manifest entry to paste. It does NOT edit the manifest or `git rm` (those stay explicit per-plugin so each is a reviewable commit).

- [ ] **Step 1: Write the extraction helper**

Create `scripts/extract-plugin.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
name="$1"; version="$2"; repo="cc-$name"
root="$(git rev-parse --show-toplevel)"

echo "== privacy scan: $name =="
if git grep -n -iE 'divorce|matilda|tilly|jennifer|helen morse|BEGIN [A-Z ]*PRIVATE KEY|gh[posu]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}' -- "plugins/$name" ; then
  echo "PRIVACY HIT in plugins/$name — resolve before pushing" >&2; exit 1
fi
echo "clean."

echo "== subtree split =="
git branch -D "split/$name" 2>/dev/null || true
git subtree split -P "plugins/$name" -b "split/$name"

echo "== create public repo nelsonlove/$repo =="
gh repo create "nelsonlove/$repo" --public --description "$(python3 -c "import json;print(json.load(open('plugins/$name/.claude-plugin/plugin.json')).get('description',''))")" || true

echo "== push + tag v$version =="
git push "git@github.com:nelsonlove/$repo.git" "split/$name:main" --force
tmp="$(mktemp -d)"; git clone -q "git@github.com:nelsonlove/$repo.git" "$tmp/$repo"
git -C "$tmp/$repo" tag "v$version" && git -C "$tmp/$repo" push origin "v$version"

echo "== depth check (history preserved?) =="
echo "commits in new repo: $(git -C "$tmp/$repo" rev-list --count HEAD)"
test -f "$tmp/$repo/.claude-plugin/plugin.json" && echo "root plugin.json: present" || { echo "MISSING root plugin.json" >&2; exit 1; }

cat <<JSON

>>> paste into .claude-plugin/marketplace.json (replace the ./plugins/$name entry's source):
    "source": { "source": "github", "repo": "nelsonlove/$repo", "ref": "v$version" }
JSON
```
```bash
chmod +x scripts/extract-plugin.sh
git add scripts/extract-plugin.sh
git commit -m "chore: add per-plugin extraction helper"
```

- [ ] **Step 2: Run the helper on tomatobar**

```bash
scripts/extract-plugin.sh tomatobar 1.0.0
```
Expected: `clean.` → split → repo created → push + `v1.0.0` tag → `commits in new repo: N` (N>1, history preserved) → `root plugin.json: present` → prints the manifest snippet.

- [ ] **Step 3: Verify standalone install (real smoke test)**

```bash
gh api repos/nelsonlove/cc-tomatobar --jq '.visibility, .default_branch'
git ls-remote --tags git@github.com:nelsonlove/cc-tomatobar.git | grep v1.0.0
```
Then in a scratch Claude Code session: `/plugin marketplace add nelsonlove/cc-tomatobar` (root-level repos are directly addable) or install via the flipped marketplace, and confirm the `tomatobar` command loads.
Expected: repo is `public`, tag `v1.0.0` present, plugin installs and its skill/command resolves.

- [ ] **Step 4: Flip the manifest entry for tomatobar**

In `.claude-plugin/marketplace.json`, replace the `tomatobar` entry's `"source": "./plugins/tomatobar"` with:
```json
"source": { "source": "github", "repo": "nelsonlove/cc-tomatobar", "ref": "v1.0.0" }
```

- [ ] **Step 5: Validate the manifest still parses and lists 22**

```bash
python3 -c "import json;d=json.load(open('.claude-plugin/marketplace.json'));assert len(d['plugins'])==22;print('ok',len(d['plugins']))"
```
Expected: `ok 22`.

- [ ] **Step 6: Remove the embedded copy and commit**

```bash
git rm -r plugins/tomatobar
git add .claude-plugin/marketplace.json
git commit -m "refactor(tomatobar): extract to nelsonlove/cc-tomatobar; flip manifest to github source"
```

---

### Task 3: Extract the remaining 13 plugins

Apply the **exact Task 2 procedure (Steps 2→6)** once per row below, in order, using `scripts/extract-plugin.sh <name> <version>`. Each plugin is its own commit. Do not batch — validate the manifest (Task 2 Step 5) after every flip so a break is localized.

**Files (per row):** Modify `.claude-plugin/marketplace.json`; Remove `plugins/<name>/`; New repo `nelsonlove/cc-<name>`.

**Interfaces:**
- Consumes: `scripts/extract-plugin.sh` (Task 2), the tag table (Global).
- Produces: 13 more external `github` manifest entries; 13 `plugins/<name>` dirs removed.

Rows (run each through Task 2 Steps 2–6, substituting name + version):

- [ ] **calibre** — `scripts/extract-plugin.sh calibre 0.1.2` → flip to `{"source":"github","repo":"nelsonlove/cc-calibre","ref":"v0.1.2"}` → validate 22 → `git rm -r plugins/calibre` → commit `refactor(calibre): extract to cc-calibre`
- [ ] **claude-goodbye** — `scripts/extract-plugin.sh claude-goodbye 0.2.0` → ref `v0.2.0` → validate → rm → commit
- [ ] **claude-identity** — `scripts/extract-plugin.sh claude-identity 0.1.4` → ref `v0.1.4` → validate → rm → commit
- [ ] **claude-notebook** — `scripts/extract-plugin.sh claude-notebook 0.9.0` → ref `v0.9.0` → validate → rm → commit
- [ ] **claude-threads** — `scripts/extract-plugin.sh claude-threads 0.2.4` → ref `v0.2.4` → validate → rm → commit
- [ ] **claude-tone** — `scripts/extract-plugin.sh claude-tone 0.1.0` → ref `v0.1.0` → validate → rm → commit
- [ ] **homebrew-audit** — `scripts/extract-plugin.sh homebrew-audit 0.2.0` → ref `v0.2.0` → validate → rm → commit
- [ ] **marked-preview** — `scripts/extract-plugin.sh marked-preview 0.1.0` → ref `v0.1.0` → validate → rm → commit
- [ ] **zotero** — `scripts/extract-plugin.sh zotero 0.1.0` → ref `v0.1.0` → validate → rm → commit
- [ ] **backlog** — `scripts/extract-plugin.sh backlog 1.0.0` → ref `v1.0.0` → validate → rm → commit
- [ ] **dayone** — `scripts/extract-plugin.sh dayone 1.0.0` → ref `v1.0.0` → validate → rm → commit
- [ ] **mail** — `scripts/extract-plugin.sh mail 0.0.1` → ref `v0.0.1` → validate → rm → commit
- [ ] **steipete-scripts** — `scripts/extract-plugin.sh steipete-scripts 0.0.1` → ref `v0.0.1` → validate → rm → commit

- [ ] **Final step: confirm no local plugin sources remain**

```bash
python3 -c "import json;d=json.load(open('.claude-plugin/marketplace.json'));loc=[p['name'] for p in d['plugins'] if isinstance(p['source'],str)];print('local left:',loc);assert not loc"
```
Expected: `local left: []` (all 22 are external objects).

---

### Task 4: Phase 3 — incubator, drop stale jd, README rewrite

**Files:**
- Create: `incubator/` (moved WIP dirs), `incubator/README.md`
- Remove: `plugins/jd/`, empty `plugins/`
- Modify: `README.md`

> **CORRECTED during execution (2026-07-04):** only `batch-issues` and `org-roam-claude`
> are tracked WIP dirs on tip. `claude-notifications`, `imessage-research`, and
> `session-name` are **NOT tracked** (untracked local-only in Nelson's working copy, or
> already removed from history in Task 0) — so there is nothing in the repo to move or
> scrub for them. The `matilda|tilly` example was never committed; Step 1 is therefore
> a no-op on the git side (Nelson handles his local untracked copy separately).

- [ ] **Step 1: Confirm no `matilda|tilly` is tracked (no-op if clean)**

```bash
git grep -n -i -e matilda -e tilly -- plugins/ || echo "clean (nothing tracked)"
```
Expected: `clean (nothing tracked)`.

- [ ] **Step 2: Move the two tracked WIP dirs into incubator/**

```bash
mkdir -p incubator
git mv plugins/batch-issues incubator/batch-issues
git mv plugins/org-roam-claude incubator/org-roam-claude
```
Expected: two dirs now under `incubator/`.

- [ ] **Step 3: Confirm plugins/jd is a stale duplicate, then remove it**

```bash
diff -rq plugins/jd <(git -C "$(mktemp -d)" clone -q --depth 1 https://github.com/nelsonlove/jd-cli.git jd && echo) 2>/dev/null || true
git rm -r plugins/jd
```
(Manual confirm: `jd` is served from the jd-cli git-subdir entry, so the local copy is redundant regardless of drift.)
Expected: `plugins/jd` removed; the `jd` manifest entry (git-subdir) is untouched.

- [ ] **Step 4: Remove the now-empty plugins/ dir**

```bash
rmdir plugins 2>/dev/null && echo "plugins/ removed" || { echo "plugins/ not empty:"; ls plugins; }
```
Expected: `plugins/ removed`.

- [ ] **Step 5: Write incubator/README.md and rewrite top-level README**

`incubator/README.md`: one paragraph — "WIP plugins not yet published to the marketplace; each is extracted to its own `cc-*` repo when ready." Rewrite `README.md` so it describes a pure marketplace (how to add it, the two source styles, link to `docs/superpowers/specs/`), removing any "plugins live in plugins/" language.

- [ ] **Step 6: Validate + commit**

```bash
python3 -c "import json;d=json.load(open('.claude-plugin/marketplace.json'));assert len(d['plugins'])==22;print('ok')"
git add -A
git commit -m "refactor: move WIP plugins to incubator/, drop stale plugins/jd, make repo a pure marketplace"
```

---

### Task 5: Final verification

**Interfaces:**
- Consumes: the fully-flipped manifest and all 14 `cc-*` repos.

- [ ] **Step 1: Fresh clone has no embedded published plugin**

```bash
tmp="$(mktemp -d)"; git clone -q https://github.com/nelsonlove/claude-code-plugins.git "$tmp/m"
test ! -d "$tmp/m/plugins" && echo "no plugins/ dir: good" || echo "plugins/ still present"
python3 -c "import json;d=json.load(open('$tmp/m/.claude-plugin/marketplace.json'));print('plugins:',len(d['plugins']));print('all external:',all(isinstance(p['source'],dict) for p in d['plugins']))"
```
Expected: `no plugins/ dir: good`, `plugins: 22`, `all external: True`.

- [ ] **Step 2: Every cc-* repo exists, is public, and is tagged**

```bash
for r in tomatobar calibre claude-goodbye claude-identity claude-notebook claude-threads claude-tone homebrew-audit marked-preview zotero backlog dayone mail steipete-scripts; do
  vis=$(gh api "repos/nelsonlove/cc-$r" --jq .visibility 2>/dev/null || echo MISSING)
  tag=$(git ls-remote --tags "git@github.com:nelsonlove/cc-$r.git" 2>/dev/null | grep -c 'refs/tags/v')
  printf 'cc-%-16s %s tags=%s\n' "$r" "$vis" "$tag"
done
```
Expected: every row `public tags>=1`.

- [ ] **Step 3: Smoke-install two representative plugins**

In a scratch Claude Code session, add the marketplace fresh and install one skill-based plugin (`claude-notebook`) and one MCP-based plugin (`zotero` or `dayone`); confirm a command/skill from each resolves.
Expected: both install from their `github` sources and load.

- [ ] **Step 4: Open the PR for the monorepo changes**

```bash
git push -u origin split-work
gh pr create --title "Split plugins into per-repo + pure marketplace" --body "Implements docs/superpowers/specs/2026-07-03-plugin-repo-split-design.md. Extracts 14 plugins to cc-* repos, flips manifest to github sources, moves WIP to incubator/, removes plugins/. History purged of _archived divorce strings (force-pushed separately in Task 0)."
```
Then run `/code-review high` on the PR, address findings, and merge per the independent-review rule.

---

## Self-review notes

- **Spec coverage:** Phase 0 → Task 0; version reconciliation (implied by spec's "read from plugin.json") → Task 1; Phase 1 shakedown → Task 2; Phase 2 → Tasks 2–3; Phase 3 → Task 4; verification strategy → Task 5. Phase 4 cosmetic `/Users/nelson` scrub is intentionally deferred (spec marks it low-priority/optional) and not blocking; can be a follow-up per-repo.
- **Placeholders:** none — every step has concrete commands and expected output; the per-plugin procedure is fully spelled out in Task 2 and applied to concrete rows in Task 3.
- **Type/name consistency:** `extract-plugin.sh <name> <version>` signature is defined in Task 2 and used verbatim in Task 3; repo names and tags match the table throughout; manifest stays 22 entries at every checkpoint.
