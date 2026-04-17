# Batch Issues

Process multiple GitHub Issues in parallel — analyze for independence, implement in isolated worktrees, test, and open PRs.

## Usage

Run `/batch-issues` in any repo with GitHub Issues. Optionally pass a max count or label filter:

- `/batch-issues` — process up to 5 independent issues
- `/batch-issues 3` — process up to 3
- `/batch-issues label:bug` — only bug-labeled issues

## Process

### Phase 1: Analyze

1. Run `gh issue list --json number,title,body,labels --limit 20` to get open issues
2. For each issue, identify which files it likely touches (from issue body, title keywords, label hints)
3. Score independence: issues touching different files/directories are independent
4. Select up to N issues with no file overlap
5. Present the selection to the user for approval before proceeding

**Output a table:**
```
# | Title                              | Files likely touched        | Independent?
1 | Fix config write path              | adapters/config.py          | ✓
4 | Add --dry-run to omnifocus create  | cli/omnifocus.py            | ✓
7 | Standardize stderr output          | cli/__init__.py, cli/*.py   | ✗ (overlaps #4)
```

Wait for user approval. If they remove or add issues, adjust.

### Phase 2: Implement

For each approved issue, dispatch a subagent with `isolation: "worktree"`:

```
Agent(
  description: "Fix issue #N: title",
  isolation: "worktree",
  prompt: """
    You are fixing GitHub issue #N: {title}

    Issue body:
    {body}

    Repository: {repo}

    Your job:
    1. Read the relevant code
    2. Implement the fix with tests
    3. Run the test suite: {test_command}
    4. Commit with message: "fix: {title} (#{number})"
    5. Push to a new branch: fix/issue-{number}
    6. Open a PR via: gh pr create --title "fix: {title}" --body "Closes #{number}"

    Report back: PR URL, test results, files changed.
  """
)
```

IMPORTANT: Dispatch agents sequentially, not in parallel. Each agent gets its own worktree (via `isolation: "worktree"`), but dispatching in parallel can cause git conflicts on push.

### Phase 3: Dashboard

After all agents complete, present results:

```
## Batch Issues Results

| # | Title                    | Status | PR    | Tests        |
|---|--------------------------|--------|-------|--------------|
| 1 | Fix config write path    | ✓ Done | #42   | 362 passed   |
| 4 | Add --dry-run            | ✓ Done | #43   | 362 passed   |
| 9 | Remove staging commands  | ✗ Fail | —     | 3 failures   |

3 issues processed, 2 PRs opened, 1 failed.

Skipped (file overlap): #7, #12
Skipped (too complex): #15
```

## Determining file overlap

Use these heuristics to guess which files an issue touches:

1. **Issue body mentions file paths** — grep for patterns like `path/to/file.py`, `cli/__init__.py`
2. **Issue title mentions a command** — `jd validate` → `cli/validate.py`; `jd notes` → `cli/notes.py`
3. **Labels** — `bug` + mentions of a specific feature map to specific files
4. **If unclear** — mark as "unknown overlap" and skip unless the user explicitly includes it

Conservative is better — skipping an ambiguous issue is cheaper than two agents colliding on the same file.

## Test command detection

Check for these in order:
1. `pyproject.toml` with `[tool.pytest]` → `python -m pytest tests/ -q`
2. `package.json` with `"test"` script → `npm test`
3. `Makefile` with `test` target → `make test`
4. Fall back to asking the user

## Requirements

- `gh` CLI authenticated (`gh auth status`)
- Git repo with GitHub remote
- At least 2 open issues
