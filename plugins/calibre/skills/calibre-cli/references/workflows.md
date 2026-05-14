# Calibre CLI workflows

End-to-end recipes for common library curation tasks. Each recipe explains the reasoning so it can be adapted, not just copy-pasted.

## Convention used in these recipes

All recipes assume:

```bash
LIB="/path/to/your/library"
```

Replace with the actual library path. If the GUI is open, prepend `calibredb --with-library=http://localhost:8080/#yourlibname` instead of `calibredb --library-path "$LIB"` (after starting `calibre-server`).

Recipes that mutate the library start with a backup step. **Don't skip it.**

---

## Recipe 1: Pre-flight backup

Before any non-trivial mutation, snapshot the library.

```bash
LIB="/path/to/library"
PARENT="$(dirname "$LIB")"
NAME="$(basename "$LIB")"
TS="$(date +%Y-%m-%d_%H%M%S)"

# Filesystem snapshot — fast, total
cp -R "$LIB" "$PARENT/$NAME.backup-$TS"

# Force OPF refresh inside the live library too, for redundancy
calibredb backup_metadata --library-path "$LIB" --all
```

The filesystem copy is the cheap fallback. The per-book OPFs are an independent recovery path: if `metadata.db` is corrupted, `calibredb restore_database --really-do-it` rebuilds it from those OPFs.

---

## Recipe 2: Read-only library audit

Surface metadata problems without changing anything. Safe to run with the GUI open.

```bash
DB="$LIB/metadata.db"

# 1. Calibre's own filesystem integrity check
calibredb check_library --library-path "$LIB" --csv > /tmp/check_library.csv

# 2. Quick stats
sqlite3 -readonly "$DB" "
  SELECT 'books', COUNT(*) FROM books
  UNION ALL SELECT 'authors', COUNT(*) FROM authors
  UNION ALL SELECT 'tags', COUNT(*) FROM tags
  UNION ALL SELECT 'series', COUNT(*) FROM series
  UNION ALL SELECT 'identifiers', COUNT(*) FROM identifiers
  UNION ALL SELECT 'books_without_cover', COUNT(*) FROM books WHERE has_cover=0
  UNION ALL SELECT 'books_without_isbn', COUNT(*) FROM books WHERE id NOT IN (SELECT book FROM identifiers WHERE type='isbn');
"

# 3. Author dedup candidates (variant spellings)
sqlite3 -readonly "$DB" "
  SELECT a.id, a.name, COUNT(bal.book) AS books
  FROM authors a LEFT JOIN books_authors_link bal ON bal.author=a.id
  GROUP BY a.id ORDER BY a.name;
"

# 4. Likely duplicate-title pairs
sqlite3 -readonly "$DB" "
  SELECT lower(title) AS norm, GROUP_CONCAT(id), COUNT(*)
  FROM books GROUP BY norm HAVING COUNT(*) > 1;
"

# 5. Books with filename-as-title (looks like ISBN or hash)
sqlite3 -readonly "$DB" "
  SELECT id, title FROM books
  WHERE title GLOB '[0-9][0-9][0-9][0-9]*.pdf'
     OR title GLOB '[a-f0-9]{8}*'
     OR title LIKE '%.pdf'
     OR title LIKE '%.epub';
"

# 6. Books with cruft in title (publisher tags, source markers)
sqlite3 -readonly "$DB" "
  SELECT id, title FROM books
  WHERE title LIKE '%z-lib.org%'
     OR title LIKE '%libgen%'
     OR title LIKE '%(epub)%'
     OR title LIKE '%nodrm%';
"
```

Each query has a story:
- Author dedup candidates: variants ("Solomon, Robert C." vs "Robert C.Solomon" vs "Solomon, Robert C.;Higgins, Kathleen M.") that should collapse to one canonical entry.
- Duplicate-title pairs: book records that should be merged via `add_format` + `remove`.
- Filename-as-title: Calibre fell back to filename because the source PDF had no metadata. ISBN often visible in filename.
- Cruft: source-site markers ("z-lib.org") and DRM-removal markers ("nodrm") that leaked from the ripper into the title.

---

## Recipe 3: Fix a single book's metadata via ISBN

The canonical OPF round-trip.

```bash
ID=14
ISBN=0195368533

# 1. Fetch from online sources — OPF + cover
fetch-ebook-metadata --isbn="$ISBN" -o > /tmp/book.opf
fetch-ebook-metadata --isbn="$ISBN" -c /tmp/cover.jpg -o > /tmp/book.opf 2>/dev/null

# 2. Sanity-check the match (see footgun #19 — wrong ISBN returns wrong book)
PROPOSED=$(grep -m1 'dc:title' /tmp/book.opf | sed -E 's/.*<dc:title>([^<]+)<.*/\1/')
CURRENT=$(calibredb list --library-path "$LIB" --fields=title --search="id:$ID" --for-machine \
          | python3 -c "import json,sys; print(json.load(sys.stdin)[0]['title'])")
echo "Current:  $CURRENT"
echo "Proposed: $PROPOSED"
# Eyeball check, or run the word-overlap check from footgun #19.
# If they don't share at least 2 significant words, the ISBN was wrong — STOP.

# 3. Inspect proposed metadata in full
cat /tmp/book.opf
ls -la /tmp/cover.jpg

# 4. Show current state for comparison
calibredb show_metadata --library-path "$LIB" "$ID"

# 5. Apply OPF
calibredb set_metadata --library-path "$LIB" "$ID" /tmp/book.opf

# 6. Set cover (OPF doesn't carry binary)
calibredb set_metadata --library-path "$LIB" --field "cover:/tmp/cover.jpg" "$ID"

# 7. Push to the file itself (see footgun #20 if this errors on a corrupt PDF)
calibredb embed_metadata --library-path "$LIB" "$ID"

# 8. Verify
calibredb show_metadata --library-path "$LIB" "$ID"
```

If the ISBN is unknown but you have title + author:

```bash
fetch-ebook-metadata --title="In the Spirit of Hegel" --authors="Solomon" -o > /tmp/book.opf -v
```

Use `-v` to see which sources returned what; helps when the result looks wrong.

---

## Recipe 4: Batch fix by ISBN from a list

Given a CSV of `id,isbn` pairs:

```bash
LIB="/path/to/library"

while IFS=, read -r ID ISBN; do
  [ "$ID" = "id" ] && continue   # skip header
  echo "=== Fixing #$ID (ISBN $ISBN) ==="

  if fetch-ebook-metadata --isbn="$ISBN" -o > "/tmp/opf-$ID.opf" 2>/dev/null \
     && fetch-ebook-metadata --isbn="$ISBN" -c "/tmp/cover-$ID.jpg" -o > /dev/null 2>&1; then
    calibredb set_metadata --library-path "$LIB" "$ID" "/tmp/opf-$ID.opf"
    [ -s "/tmp/cover-$ID.jpg" ] && \
      calibredb set_metadata --library-path "$LIB" --field "cover:/tmp/cover-$ID.jpg" "$ID"
    echo "  OK"
  else
    echo "  FAILED — no online match"
  fi
  sleep 1   # gentle on the online metadata sources
done < /tmp/fix-list.csv

# Push everything to files
calibredb embed_metadata --library-path "$LIB" all
```

Iterate gently — Goodreads, Google, and Amazon will rate-limit aggressively if you hammer them. One second between requests is polite.

---

## Recipe 5: Merge two book records into one

```bash
KEEPER=17
DUP=29
DUP_FILE="/path/to/file/inside/library/for/dup.pdf"

# Add the dup's file as a format on the keeper (replaces same-format by default)
calibredb add_format --library-path "$LIB" "$KEEPER" "$DUP_FILE"

# Remove the dup record (goes to Trash; recoverable)
calibredb remove --library-path "$LIB" "$DUP"
```

To find the file path of a record before merging:

```bash
sqlite3 -readonly "$LIB/metadata.db" "
  SELECT b.path || '/' || d.name || '.' || lower(d.format), d.uncompressed_size
  FROM books b JOIN data d ON d.book=b.id WHERE b.id=$DUP;
"
```

This returns the relative path under `$LIB`. Prepend `$LIB/` for the absolute path.

For deciding which copy to keep (when both formats are the same), compare sizes — larger PDFs are usually better-OCR'd or higher-resolution.

---

## Recipe 6: Normalize a dirty author table

Common cleanup pattern: collapse variant spellings of the same person into one canonical entry.

```bash
LIB="/path/to/library"
CANONICAL="Robert C. Solomon"
VARIANTS=(
  "Solomon, Robert C."
  "Solomon, Robert C"
  "Solomon, Robert C.,"
  "Solomon, Robert C., author"
  "Solomon, Robert C.;"
  "Solomon, Robert C.(Author)"
  "Robert C.Solomon"
)

for VARIANT in "${VARIANTS[@]}"; do
  echo "=== Looking for books by '$VARIANT' ==="
  IDS=$(calibredb search --library-path "$LIB" "authors:\"=$VARIANT\"")
  if [ -n "$IDS" ]; then
    echo "  Found: $IDS — reassigning to '$CANONICAL'"
    # set_metadata --field authors expects & for multi-author
    # For single-author records this is fine; multi-author needs manual handling
    for ID in $(echo "$IDS" | tr ',' ' '); do
      # Read current authors so we don't clobber co-authors
      CUR=$(calibredb list --library-path "$LIB" --fields=authors --search="id:$ID" --for-machine | python3 -c "import json,sys; print(json.load(sys.stdin)[0]['authors'])")
      NEW=$(echo "$CUR" | sed "s/$VARIANT/$CANONICAL/g")
      calibredb set_metadata --library-path "$LIB" --field "authors:$NEW" "$ID"
    done
  fi
done
```

The `=` prefix on the search string forces an exact match (not substring).

After running, the orphan author rows persist with `book_count=0` until Calibre's next cleanup pass (or you can vacuum directly via the GUI Preferences → Tweaks).

---

## Recipe 7: Bulk ingest from a folder dump

For a directory tree containing thousands of ebook files (mixed formats, possibly with author subfolders):

```bash
SRC="/path/to/dump"
LIB="/path/to/library"

# 1. Backup first
cp -R "$LIB" "$LIB.backup-$(date +%Y-%m-%d_%H%M%S)"

# 2. Survey what we're about to ingest
echo "Files by extension:"
find "$SRC" -type f -not -path '*/.*' | sed -E 's/.*\.//' | tr '[:upper:]' '[:lower:]' | sort | uniq -c | sort -rn

echo "Total files:"
find "$SRC" -type f -not -path '*/.*' | wc -l

# 3. Dry-run-ish: ingest 5 books from a small sample directory, see what Calibre does
calibredb add --library-path "$LIB" \
  --recurse \
  --automerge=ignore \
  --ignore=".DS_Store" --ignore="*.txt" --ignore="*.opf" --ignore="*.htm" --ignore="*.html" --ignore="*.doc" \
  "$SRC/SampleSubfolder"

# Inspect the new records
calibredb list --library-path "$LIB" --fields=id,title,authors,formats --sort-by=timestamp --limit=5

# 4. If it looks right, ingest the full tree
calibredb add --library-path "$LIB" \
  --recurse \
  --automerge=ignore \
  --ignore=".DS_Store" --ignore="*.txt" --ignore="*.opf" --ignore="*.htm" --ignore="*.html" --ignore="*.doc" \
  "$SRC"

# 5. Post-ingest audit (Recipe 2 queries)
```

Key decisions to make before running:

- **What to ignore?** Decide whether `.txt`, `.html`, `.doc` companion files should be ingested as books or skipped. Typically skip — they're notes/READMEs, not ebooks.
- **Automerge mode?** `ignore` is safest. `overwrite` if your dump has higher-quality versions of books already in the library.
- **One book per directory?** Add `--one-book-per-directory` if the source has `Author/Book/file.epub` + `Author/Book/file.pdf` and you want each book as one record with both formats. Skip if subfolders contain unrelated books.

After ingest, expect:
- Many "Unknown" authors — books whose PDFs lacked author metadata
- Many filename-as-title records — books whose PDFs lacked title metadata (often ISBN as filename)
- Some genuine duplicates with the existing library

Run Recipe 2 (audit) to find them, then Recipe 4 (batch fix by ISBN) for the filename-as-title records.

---

## Recipe 8: Convert format with embedded metadata

Convert all EPUBs to PDF for printing, preserving metadata:

```bash
LIB="/path/to/library"

# Get IDs of EPUBs that don't already have a PDF
EPUB_ONLY=$(calibredb search --library-path "$LIB" "formats:epub AND NOT formats:pdf")

for ID in $(echo "$EPUB_ONLY" | tr ',' ' '); do
  # Find the EPUB path
  REL=$(sqlite3 -readonly "$LIB/metadata.db" "
    SELECT b.path || '/' || d.name || '.epub'
    FROM books b JOIN data d ON d.book=b.id
    WHERE b.id=$ID AND lower(d.format)='epub';
  ")
  SRC="$LIB/$REL"
  OUT="/tmp/conv-$ID.pdf"

  # Dump current metadata to OPF so the PDF carries it
  calibredb show_metadata --library-path "$LIB" --as-opf "$ID" > "/tmp/meta-$ID.opf"

  # Convert
  ebook-convert "$SRC" "$OUT" \
    --from-opf="/tmp/meta-$ID.opf" \
    --paper-size=letter \
    --pdf-default-font-size=11 \
    --smarten-punctuation

  # Attach the new PDF to the existing record
  calibredb add_format --library-path "$LIB" "$ID" "$OUT"
done
```

This gives you the original EPUB *and* a fresh PDF on the same record, with consistent metadata across both.

---

## Recipe 9: Find and remove genuine duplicates after ingest

```bash
LIB="/path/to/library"
DB="$LIB/metadata.db"

# Find candidate duplicate pairs by normalized title
sqlite3 -readonly "$DB" "
  SELECT lower(title) AS norm, GROUP_CONCAT(id), COUNT(*) AS n,
         GROUP_CONCAT(DISTINCT (
           SELECT GROUP_CONCAT(a.name, ' & ') FROM authors a
           JOIN books_authors_link bal ON bal.author=a.id WHERE bal.book=b.id
         ))
  FROM books b GROUP BY norm HAVING n > 1
  ORDER BY n DESC, norm;
" | head -50
```

For each pair, decide:
1. Are they actually the same book (same author + same edition)?
2. Which has the better metadata? → that's the keeper
3. What formats does each have? → preserve the keeper's plus any unique ones from the dup

Then apply Recipe 5 per pair.

---

## Recipe 10: Recover from a corrupted DB

Last-resort recovery if `metadata.db` is unreadable.

```bash
LIB="/path/to/library"

# 1. Move the broken DB aside (keep it for forensics — don't trash)
mv "$LIB/metadata.db" "$LIB/metadata.db.broken-$(date +%Y%m%d_%H%M%S)"

# 2. Restore from per-book OPFs
calibredb restore_database --library-path "$LIB" --really-do-it
```

`restore_database` reads `metadata.opf` from every book folder under `$LIB` and rebuilds `metadata.db`. **What you lose:**
- Saved searches
- User categories
- Plugboards
- Custom recipes
- Per-book conversion settings
- Some custom-column display settings (the column definitions and values usually survive)

What you keep: every book record, every author, every tag, every series, every cover, every format file. The actual library contents.

If `restore_database` itself fails or only partially restores, see if `metadata_db_prefs_backup.json` exists — it has Calibre prefs you may want to merge back manually.

---

## When to reach for `calibre-debug`

`calibre-debug -e script.py` runs a Python script with Calibre's full API loaded. This is for cases the CLI can't handle:

- Complex queries that go beyond `calibredb search`
- Bulk operations on custom columns with conditional logic
- Custom metadata extraction from format-specific internals
- Anything that would require writing many `calibredb` invocations in a loop

```python
# /tmp/cleanup.py — run with: calibre-debug -e /tmp/cleanup.py
from calibre.library import db

lib = db('/path/to/library').new_api
all_book_ids = lib.all_book_ids()
for book_id in all_book_ids:
    mi = lib.get_metadata(book_id)
    if not mi.identifiers.get('isbn'):
        print(f"#{book_id}: {mi.title} — no ISBN")
```

The full API is documented at https://manual.calibre-ebook.com/develop.html. Use this sparingly — the CLI is faster to iterate on for most tasks.
