---
description: Find and merge duplicate books in a Calibre library — pairs first, user confirms per pair
argument-hint: <library-path>
allowed-tools: Bash, Read
---

Find candidate duplicate books in the Calibre library at: `$ARGUMENTS`

This command **modifies the library** (eventually). The detection phase is read-only; the merge phase requires per-pair confirmation.

Calibre has **no built-in book-level merge subcommand**. The workaround is `calibredb add_format <keeper> <dup_file>` followed by `calibredb remove <dup>`. See Recipe 5 in `references/workflows.md`.

## Phase 1: Detect candidate pairs (read-only)

1. Verify the library exists. Identify the `metadata.db` for direct SQLite read-only queries.

2. Query for normalized-title collisions:

   ```sql
   SELECT lower(title) AS norm,
          GROUP_CONCAT(id ORDER BY id) AS ids,
          COUNT(*) AS n
   FROM books
   GROUP BY norm
   HAVING n > 1
   ORDER BY n DESC, norm;
   ```

3. For each candidate group, also pull:
   - Authors for each id (so we can confirm same author, not just same title)
   - Formats present on each id (`data` table)
   - File size of each format

4. Present each candidate pair (or group) as a table:

   ```
   Title (normalized): "in the spirit of hegel"
     #17 — Solomon, Robert C.;          — PDF (35.6 MB)
     #29 — In the Spirit of Hegel       — PDF (38.2 MB)
   ```

## Phase 2: Confirm per pair, then merge

For each candidate, ask the user:

1. **Are these the same book?** (same edition, same author) — if no, skip.
2. **Which is the keeper?** (better metadata wins, not better file). Propose a default based on which record has cleaner metadata; let the user override.
3. **For same-format duplicates**, which file to keep? Propose larger by default (usually better OCR / higher resolution).

After confirmation, execute the merge:

```bash
# If same format and we're keeping the dup's file (larger):
calibredb add_format --library-path "$LIB" <keeper_id> <dup_file>

# If different formats (different ext between keeper and dup):
calibredb add_format --library-path "$LIB" <keeper_id> <dup_file>

# Always remove the dup record (goes to Trash, recoverable):
calibredb remove --library-path "$LIB" <dup_id>
```

After each pair, confirm before moving to the next.

## Phase 3: Report

At the end, summarize:
- Number of pairs evaluated
- Number actually merged
- Number skipped (different books with same title)
- Final library size delta (records removed)

## Guardrails

- **Never auto-merge without explicit per-pair OK.** Even if 10 pairs all look obvious, ask for each.
- **Suggest `/calibre:backup` first** if the user hasn't run it recently. Mention this if you see 5+ candidates.
- **Same-format duplicates can lose data.** When `add_format` replaces a same-format file, the original is gone (well, in OS Trash). Make sure the user sees the size delta in the proposal.
- **The 5-10 range is exclusive** — if proposing a batch like "remove these ids: 5-10", Calibre removes 5,6,7,8,9 (not 10). Use explicit comma lists for clarity.
