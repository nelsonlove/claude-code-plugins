---
description: Snapshot a Calibre library — filesystem copy + per-book OPF refresh
argument-hint: <library-path>
allowed-tools: Bash, Read
---

Take a defensive snapshot of the Calibre library at: `$ARGUMENTS`

This command is **always safe to run end-to-end**. It does not modify the live library; it only creates a redundant copy.

## Steps

1. Verify the path exists and contains `metadata.db`. Stop if not.

2. Force per-book OPF refresh inside the live library (cheap, additive):
   ```bash
   calibredb backup_metadata --library-path "$ARGUMENTS" --all
   ```
   This guarantees every book folder has a current `metadata.opf` — independent recovery path if `metadata.db` is later corrupted.

3. Create a timestamped sibling-directory snapshot:
   ```bash
   PARENT="$(dirname "$ARGUMENTS")"
   NAME="$(basename "$ARGUMENTS")"
   TS="$(date +%Y-%m-%d_%H%M%S)"
   BACKUP="$PARENT/$NAME.backup-$TS"
   cp -R "$ARGUMENTS" "$BACKUP"
   ```

4. Report the backup path, total size, and what it includes. Suggest the user `trash` it (never `rm`) once the next session of work is verified.

## Important

- If the GUI is open during this operation, the OPF refresh may fail with a lock error. In that case, do the filesystem `cp -R` first (which doesn't need the lock), then either close the GUI or use the Content Server form before retrying the OPF refresh.
- This is the recommended prerequisite before any of: `/calibre:fix-metadata` (especially batch), `/calibre:dedup`, `/calibre:ingest`, or any `calibredb restore_database` invocation.
