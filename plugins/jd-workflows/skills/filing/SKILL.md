---
name: jd-filing
description: Use when filing items into the Johnny Decimal tree, moving files between JD locations, sorting category unsorted folders, or when asked to "file this", "sort xx.01", or "move this to the right place".
---

# Two-Tier JD Filing

File items into the Johnny Decimal tree using the two-tier system from POLICY.md.

## The tiers

```
01.xx (Capture)  →  xx.01 (Category unsorted)  →  xx.yy (Final ID)
```

**Tier 1 — Capture to category:** Quick domain sort. "This is a health thing" → `jd mv file 13.01`. Only requires knowing the broad domain.

**Tier 2 — Category to ID:** Precise filing. "This is lab results" → `jd mv file 13.05`. Requires domain knowledge of what IDs exist.

You don't have to do both tiers at once. Tier 1 is a fast sweep; Tier 2 happens when context is available.

## Rules

- **Always use `jd` CLI** — `jd mv`, `jd which`, `jd new`, `jd search`. Never hardcode paths.
- **Use `mv` semantics** — files move, not copy. `jd mv` handles this.
- **When unsure of the ID, file to `xx.01`** — category unsorted is better than wrong ID.
- **When unsure of the category, file to `01.01`** — capture unsorted is better than wrong category.
- **Check before creating new IDs** — use `jd search` and `jd index` to see if a matching ID already exists.
- **Ask before `jd new`** — don't create new IDs without user approval.

## Workflow

1. **Identify what you're filing** — read the file/directory to understand its contents
2. **Find the right destination** — `jd search <keyword>` or `jd index <category>` to find existing IDs
3. **If no ID exists** — propose a new one with `jd new <category> "Name"`, but ask first
4. **Move it** — `jd mv <source> <id>`
5. **Verify** — `jd which <id>` to confirm it landed correctly
