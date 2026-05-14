---
description: Bulk-add a folder of ebooks to a Calibre library with safety rails (backup, preview, confirm, audit)
argument-hint: <library-path> <source-folder>
allowed-tools: Bash, Read
---

Bulk-add ebook files from a source folder into a Calibre library, with safety rails.

Arguments:
- `$1` — destination library path
- `$2` — source folder containing the files (will be traversed recursively)

This command **modifies the library** and can be high-impact. Stop at each guardrail.

See Recipe 7 in `references/workflows.md` for the full reasoning.

## Phase 1: Survey (read-only)

1. Validate both args. The library must exist with `metadata.db`. The source folder must exist.

2. Count and classify what we're about to ingest:

   ```bash
   echo "Files by extension:"
   find "$2" -type f -not -path '*/.*' | sed -E 's/.*\.//' | tr '[:upper:]' '[:lower:]' | sort | uniq -c | sort -rn

   echo "Total files:"
   find "$2" -type f -not -path '*/.*' | wc -l
   ```

3. Report current library size:
   ```bash
   calibredb list --library-path "$1" --fields=id --for-machine | python3 -c "import sys,json; print(len(json.load(sys.stdin)), 'books currently in library')"
   ```

## Phase 2: Decide ingest parameters (interactive)

Ask the user, defaulting to safe choices:

1. **Automerge mode** — propose `ignore` (safest). Explain: `ignore` discards duplicate formats silently; `overwrite` replaces existing files in the library with new ones; `new_record` puts duplicates in a brand new record (almost never wanted).

2. **One book per directory?** — propose `--one-book-per-directory` if a quick `find $2 -maxdepth 2 -type d | head` shows author/book subfolders with multiple format files inside. Otherwise no.

3. **Ignore patterns** — propose a default set: `.DS_Store`, `*.txt`, `*.htm`, `*.html`, `*.doc`, `*.opf`. Ask the user to add to or trim this list. Reasoning: text/HTML/Word files are usually notes/READMEs, not ebooks.

4. **Languages override?** — if the dump is known to be a specific language, propose setting `--languages=en` (or whatever) so newly-added books get a language baseline. Skip if unknown.

5. **Tag override?** — propose tagging all ingested books with the source-folder basename (e.g., `--tags="WDMA philosophy"`) so they're searchable later. Mention this is reversible.

## Phase 3: Mandatory backup

Stop here and require:

```bash
# Run /calibre:backup or do it inline:
cp -R "$1" "$1.backup-$(date +%Y-%m-%d_%H%M%S)"
```

Confirm the backup completed before proceeding.

## Phase 4: Dry-run on a sample

Before the full ingest, run on a small subfolder to validate the parameters:

```bash
# Pick the first author letter folder or similar small slice
SAMPLE_DIR=$(find "$2" -maxdepth 1 -type d | sed -n '2p')   # first non-root subdir
calibredb add --library-path "$1" \
  --recurse \
  --automerge=<chosen> \
  [--one-book-per-directory if chosen] \
  --ignore=... \
  [--tags=... --languages=...] \
  "$SAMPLE_DIR"
```

Show the user what records were created. If the metadata looks wrong (lots of Unknown authors, lots of filename-as-title), pause and reconsider parameters before continuing.

## Phase 5: Full ingest

After sample validation passes user inspection, run the full ingest with the same parameters but pointing at `$2`. Show progress (Calibre prints per-book).

## Phase 6: Post-ingest audit

After ingest completes:

1. Report the delta: new total books vs original total.
2. Run a quick health check: `calibredb check_library --library-path "$1" --csv`
3. Run abbreviated audit queries to flag obvious problems:
   - How many new records have `authors='Unknown'`?
   - How many new records have filename-as-title pattern?
   - How many new records have no ISBN?
4. Suggest the user run `/calibre:audit` for the full report, then `/calibre:dedup` if duplicates are likely with existing content.

## Guardrails

- **Never proceed past Phase 3 without a backup.** Even if the user says "skip backup", explain that 2,000+ file ingests can corrupt indexes in ways that are easier to roll back from than to repair.
- **Sample-first is non-negotiable.** A 5-book sample takes 30 seconds and surfaces parameter errors that would otherwise require touching every record.
- **Watch for `--duplicates` flag** — it's NOT the right flag for "I'm not sure if these are duplicates". `--automerge=ignore` is. The names are easy to confuse.
