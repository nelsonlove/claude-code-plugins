# Calibre CLI footguns

The non-obvious behaviors that bite. Each entry has the symptom, the cause, and the fix. Read this before any bulk edit or automation.

## 1. `title` and `sort` are independent — changing one does not update the other

**Symptom:** You run `calibredb set_metadata 17 --field title:"New Title"`. The title changes in `list` output, but the book still sorts under the old title.

**Cause:** `title_sort` is stored as `books.sort` in the DB. `set_metadata --field title:X` updates `books.title` only. There is no automatic regeneration.

**Fix:** Always set both, or use the OPF round-trip (which sets both):

```bash
calibredb set_metadata 17 \
  --field "title:New Title" \
  --field "sort:New Title"
```

Same gotcha applies to `authors` ↔ `author_sort`, except `--field authors:X` is more forgiving — Calibre will regenerate `author_sort` from the new author string. But if you explicitly want a non-default sort form, set both.

**Also note:** the title-sort field is named `sort` in `--field` syntax, but everywhere else (DB schema, OPF) it's referred to as `title_sort`. Inconsistent and easy to get wrong.

## 2. Author syntax — `&` not `,` or `;`

**Symptom:** You add a book with `--authors="Solomon, Robert C.;Flores, Fernando"`. One author entry appears in the library named `Solomon, Robert C.;Flores, Fernando`.

**Cause:** Calibre treats commas inside an author string as "Lastname, Firstname" (per the file-as convention). Semicolons are treated as literal characters. The only separator that splits one author string into multiple author records is `&`.

**Fix:** Always use `&` to separate authors:

```bash
--authors="Robert C. Solomon & Fernando Flores"
```

Note that `--authors` expects **display order** (Firstname Lastname). Calibre will generate the sort form ("Solomon, Robert C." & "Flores, Fernando") automatically.

To merge variant author entries that already exist (e.g., `Robert C. Solomon` and `Robert C.Solomon`), you need to:
1. Find every book attached to the wrong variant.
2. `set_metadata --field authors:` to reassign them to the canonical variant.
3. The orphan author row will remain in `authors` table but with `book_count=0`. Calibre cleans these up on next library refresh.

## 3. Language codes must be ISO 639

**Symptom:** Setting `--field languages:English` silently fails or sets a malformed language.

**Cause:** Calibre stores languages as ISO 639 codes. Some plain-English names are recognized as a convenience but it's brittle.

**Fix:** Use the ISO 639 code:

```bash
--field "languages:en"          # not "English"
--field "languages:fr"          # not "French"
--field "languages:en,fr"       # multilingual
```

For ancient languages: `grc` (ancient Greek), `lat` (Latin), `chu` (Old Church Slavonic), etc. Same as `dc:language` in OPF.

## 4. Identifiers use a nested syntax

**Symptom:** `--field "isbn:9780..."` doesn't work. Or you can't figure out how to set both ISBN and Goodreads ID.

**Cause:** Identifiers are namespaced. The field name is `identifiers` (plural), and the value is comma-separated `type:value` pairs:

```bash
calibredb set_metadata 17 --field "identifiers:isbn:9780195036503,goodreads:396359,doi:10.1093/oso/9780195036503.001.0001"
```

This **replaces** all existing identifiers. To add without removing, you must first read existing ones with `show_metadata`, merge, then set.

For one-by-one: `ebook-meta` accepts repeatable `--identifier=type:value` flags, but only against a single file outside a library.

## 5. `automerge` modes — pick the right one for ingest

**Symptom:** A bulk `calibredb add --recurse` either creates many duplicate records, or silently loses files you wanted to add.

**Cause:** The three `--automerge` modes have very different semantics:

| Mode | Behavior | When to use |
|---|---|---|
| `ignore` (default if `--duplicates` not set) | Duplicate formats discarded; new title+author combos still added | Safest — never overwrites, never duplicates |
| `overwrite` | Duplicate formats replace existing files in the library | When the incoming files are higher-quality versions |
| `new_record` | Duplicate formats go into a brand-new book record | Almost never — produces noise |

Without `--automerge` AND without `--duplicates`, Calibre's default behavior is more conservative: it skips files that look like duplicates. `--duplicates` flips this to "add everything regardless". `--automerge` overrides both.

**Recommendation:** For most bulk-ingest workflows, `--automerge=ignore` is the right default. Sample 5 books afterward, decide if you want `overwrite` for a re-run, then re-run on the same folder.

## 6. `calibredb remove` uses your OS Trash by default

**Symptom:** You delete a record with `calibredb remove 5`, but the file is still on disk somewhere.

**Cause:** Calibre moves the book's folder to the system Trash (not the library's `.caltrash`). The DB row is gone, but the files are recoverable.

**Implication:** Bulk removals can balloon your Trash. Empty it after verifying.

**Fix:** Use `--permanent` to skip the Trash:

```bash
calibredb remove 5,8,13 --permanent
```

But the default behavior is the safer one — keep it unless you're confident.

## 7. PDF metadata writing has format limits

**Symptom:** `ebook-meta book.pdf --series="Foo" --series-index=2.5` runs without error, but the values don't appear when read back.

**Cause:** PDF metadata write support is a subset of read support. Title, authors, identifiers, comments, cover all work. Series, series_index, rating, tags may be silently dropped.

**Fix:** For PDFs, keep rich metadata in the Calibre DB (via `calibredb set_metadata`) and rely on `embed_metadata` for what PDF can hold. For everything else, don't depend on the PDF's internal metadata.

When in doubt, after running `ebook-meta`, run `ebook-meta` again to read back what stuck.

## 8. `id:5-10` is exclusive on the high end

**Symptom:** `calibredb remove 5-10` removes ids 5, 6, 7, 8, 9 — not 5 through 10.

**Cause:** Calibre's range syntax is half-open (Python-style), not inclusive.

**Fix:** Use `5-11` to actually include 10. Verify with `calibredb list --search="id:5-11"` first.

This applies anywhere a range is accepted: `remove`, `embed_metadata`, `search`.

## 9. The GUI lock — and how to avoid it

**Symptom:** `calibredb` errors with "Another calibre program ... is running. Having multiple programs that can make changes to a calibre library running at the same time is a bad idea."

**Cause:** Calibre takes an exclusive lock on `metadata.db` when the GUI is open or another writer is active. The lock is held even when the GUI is idle.

**Three escapes:**

1. **Close the GUI.** Simplest. Works for one-off commands.
2. **Use the Content Server.** Start it (GUI: Preferences → Sharing over the net → Start server; or run `calibre-server --port 8080 --enable-local-write "$LIB"`), then call `calibredb --with-library=http://localhost:8080/#libname ...`. The server serializes writes for you. GUI can stay open.
3. **Direct SQLite read-only.** For audit-only operations, `sqlite3 -readonly "$LIB/metadata.db"` works without taking the lock. **Never write directly to `metadata.db`** — Calibre maintains derived state (indexes, thumbnails) that won't update.

The lock check is process-based; if Calibre crashed and left a stale lock, restart Calibre once to clear it.

## 10. `calibredb catalog` requires the filename before any flags

**Symptom:** `calibredb catalog --help` returns "Must specify the catalog output filename before any options".

**Cause:** Catalog parses the positional output filename first to determine the format-specific option set.

**Fix:** Always provide a dummy filename:

```bash
calibredb catalog dummy.csv --help     # CSV-specific options
calibredb catalog dummy.epub --help    # EPUB catalog options
```

## 11. `ebook-convert --help` is format-dependent

**Symptom:** `ebook-convert --help` returns only 26 lines of options. Where are the PDF margin options?

**Cause:** The help text shows only options relevant to the input AND output format pair. Without a file pair, only the top-level shared options appear.

**Fix:** Pass dummy input/output filenames to see the full set:

```bash
ebook-convert dummy.epub dummy.pdf --help    # ~700 lines including PDF-specific options
```

## 12. `restore_database` loses non-metadata state

**Symptom:** After running `calibredb restore_database --really-do-it`, your saved searches are gone, your custom column display rules are reset, and per-book conversion settings vanished.

**Cause:** `restore_database` rebuilds `metadata.db` from per-book OPF files only. Calibre stores plenty of state outside the OPFs:
- Saved searches
- User categories
- Plugboards
- Per-book conversion settings
- Custom recipes
- Custom column display options (the column definitions survive, the per-book values survive, but display formatting may reset)

**Fix:** Treat `restore_database` as last-resort recovery. Before running it, back up `metadata.db` itself. After running, manually re-create lost state.

## 13. Embedded metadata drifts from the DB

**Symptom:** You fixed metadata in Calibre. You email the EPUB to a Kindle. Kindle shows the old metadata.

**Cause:** `calibredb set_metadata` updates `metadata.db` only. The book file on disk still has the old internal metadata.

**Fix:** After bulk metadata fixes, run:

```bash
calibredb embed_metadata <id>
# or
calibredb embed_metadata all
# or restrict to formats that actually carry metadata
calibredb embed_metadata all --only-formats=epub --only-formats=mobi --only-formats=azw3
```

## 14. `fetch-ebook-metadata` writes the data to stdout, log to stderr

**Symptom:** Capturing OPF output mixes log messages with XML.

**Cause:** With `-v`, the log goes to stderr. Without `-v`, there's still occasional warning chatter on stderr.

**Fix:** Redirect explicitly:

```bash
fetch-ebook-metadata --isbn=9780195036503 -o > /tmp/book.opf 2>/tmp/fetch.log
```

The `Skia Graphite backend = ""` messages on macOS are noise from the embedded Qt; ignore them.

## 15. Trashing files outside Calibre breaks the library

**Symptom:** You manually delete a book's folder from Finder. Calibre still lists the book but shows it as having no files.

**Cause:** The DB row outlives the filesystem deletion. `check_library` reports it as `missing_formats` / `failed_folders`.

**Fix:** Always use `calibredb remove` instead of `rm`/`trash`. If you've already done it, run `calibredb check_library --report=failed_folders,missing_formats` to find affected records, then `calibredb remove` them.

## 16. Author sort form is auto-generated only when authors changes

**Symptom:** You manually correct an author from `Solomon, Robert C.` to `Robert C. Solomon` to fix display, then everything sorts under "R" instead of "S".

**Cause:** When `authors` is updated, `author_sort` is regenerated using Calibre's "Lastname, Firstname" heuristic. The heuristic is decent but not perfect for compound names ("van der", "de la", etc.).

**Fix:** Set `author_sort` explicitly when authors have non-standard naming:

```bash
calibredb set_metadata 17 \
  --field "authors:Hilary van der Linden" \
  --field "author_sort:van der Linden, Hilary"
```

For typical Western names, auto-generation is fine.

## 17. Custom column field names use `*` prefix in `list`, `#` prefix elsewhere

**Symptom:** You created custom column `myrating`. `calibredb list --fields=myrating` doesn't recognize the field; `calibredb set_custom myrating` works fine.

**Cause:** Custom columns have two reference forms. In `list --fields`, the syntax is `*myrating`. In `set_custom`, the syntax is the bare label `myrating`. In search and in templates, it's `#myrating`. Three different prefixes for the same column.

**Fix:** Memorize the table:

| Context | Prefix | Example |
|---|---|---|
| `calibredb list --fields` | `*` | `--fields=*myrating` |
| `calibredb set_custom`, `custom_columns` | none | `set_custom myrating 17 5` |
| Search expressions, templates | `#` | `--search="#myrating:5"` |

## 18. The Content Server URL format is `http://host:port/#libname`

**Symptom:** `calibredb --with-library=http://localhost:8080/mylibrary` fails.

**Cause:** The library name comes after a `#` (URL fragment style), not a `/`.

**Fix:**

```bash
--with-library=http://localhost:8080/#mylibrary
```

To list available library IDs on a server:

```bash
calibredb --with-library=http://localhost:8080/#- list --limit=0
```

The special `#-` means "list libraries". The library names you pass are the display names from the GUI (case-sensitive, spaces allowed if URL-encoded).

## 19. ISBN-based lookup returns a *confident wrong match* when the ISBN is wrong

**Symptom:** `fetch-ebook-metadata --isbn=X -o` returns plausible-looking metadata — real title, real authors, real publisher, real cover — but it's a completely different book than you wanted.

**Cause:** Metadata sources (Goodreads, Google Books, Amazon, Open Library) treat the ISBN as authoritative. They do not sanity-check against any `--title` or `--authors` hints you pass alongside. They return whatever book that ISBN actually identifies — even if your `--title` hint says "Spirituality for the Skeptic" and the ISBN you guessed is actually a book about the Virgin Mary in art.

Especially dangerous for:
- **Series volumes** — ISBN ranges across volumes are not sequential. Routledge History of Philosophy Vol VI has ISBN 9780415053785 in one source but 9780415053792 in another; guessing the next-volume ISBN routinely hits the wrong volume.
- **Multiple editions** — hardcover/softcover/eBook/large-print all have distinct ISBNs.
- **Compilations and festschrifts** — small academic publishers often have weak ISBN coverage; the "Sophia Studies in Cross-cultural Philosophy" festschrift for Solomon (Springer 2012) has at least three ISBNs floating around in different sources.

**Fix:** Before applying any ISBN-fetched OPF, **diff the proposed title against the current title (or a user-provided expected title)**:

```bash
PROPOSED=$(grep -m1 'dc:title' /tmp/book.opf | sed -E 's/.*<dc:title>([^<]+)<.*/\1/')
CURRENT=$(calibredb list --library-path "$LIB" --fields=title --search="id:$ID" --for-machine | python3 -c "import json,sys; print(json.load(sys.stdin)[0]['title'])")

# Tokenize both, drop stopwords, check word overlap
python3 -c "
import sys
stops = {'the','a','an','of','for','in','and','&','to','on','by','from','with'}
a = set(w.lower() for w in '''$PROPOSED'''.split() if w.lower() not in stops)
b = set(w.lower() for w in '''$CURRENT'''.split() if w.lower() not in stops)
overlap = a & b
if not overlap or len(overlap) < 2:
    print('NO SIGNIFICANT OVERLAP — likely wrong ISBN. Do not apply.')
    sys.exit(1)
print(f'Overlap: {overlap} — looks plausible')
"
```

If overlap is empty or trivially small, **do not apply** — the ISBN was wrong. For series volumes and other tricky cases, prefer fetching by exact title + author + publisher hints rather than guessing the ISBN. If a title-based fetch returns multiple plausible matches and you can't disambiguate online, set metadata manually with `--field` flags based on what you know about the book.

## 20. `embed_metadata` crashes on corrupt PDFs

**Symptom:** `calibredb embed_metadata <id>` errors with `podofo.Error: PdfErrorCode::InvalidXRef` or `Stack overflow`. The DB metadata stays correct but the file's internal metadata didn't update for that record.

**Cause:** Calibre uses `podofo` (a C++ PDF library) to write PDF metadata. Some PDFs have corrupt cross-reference tables, recursive object graphs, or other structural pathologies that crash podofo's writer. The crash is contained to the worker process — Calibre continues processing remaining books and remaining formats.

**Fix:** Skip PDFs for the offending record:

```bash
calibredb embed_metadata --library-path "$LIB" <id> \
  --only-formats=epub --only-formats=mobi --only-formats=azw3
```

The DB metadata is what Calibre uses internally; only the file's internal metadata stays stale. External readers (Kindle, iBooks, etc.) will see the old metadata until the PDF is rewritten through another tool.

To proactively detect which PDFs are corrupt: `ebook-meta book.pdf --to-opf=/tmp/probe.opf` will error out cleanly on broken files. `qpdf --check book.pdf` (if qpdf is installed) does a deeper structural validation.
