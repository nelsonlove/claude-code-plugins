# Calibre CLI Reference

Per-binary and per-subcommand reference for the five Calibre CLIs that matter. This is the place to look up specific options, flags, and exact invocation syntax. The main `SKILL.md` covers the high-level workflows; this file is the lookup table.

## Table of contents

1. `calibredb` — library DB operations (24 subcommands)
2. `ebook-meta` — single-file metadata
3. `fetch-ebook-metadata` — online metadata lookup
4. `ebook-convert` — format conversion
5. `calibre-server` — Content Server

## `calibredb`

All subcommands accept these global options:

- `--library-path` / `--with-library` — library path or `http://host:port/#libname` for the Content Server. Required (or set via env / Calibre prefs).
- `--username` / `--password` — for Content Server auth. Password supports `<stdin>` and `<f:/path/to/file>` forms.
- `--timeout` — network timeout in seconds (default 120).

### `list` — query the library

```bash
calibredb list --fields=id,title,authors,formats,identifiers,languages,size
calibredb list --search="author:Solomon" --sort-by=pubdate --ascending
calibredb list --for-machine  # JSON output, ideal for piping into jq/python
```

Available fields: `author_sort, authors, comments, cover, formats, identifiers, isbn, languages, last_modified, pubdate, publisher, rating, series, series_index, size, tags, template, timestamp, title, uuid`. Plus `all` for everything. Custom columns are referenced as `*column_name`.

Notable flags:
- `--for-machine` — JSON output, much easier to parse than the ASCII table
- `--prefix` — prefix prepended to file paths in output
- `--separator` — column separator (default space)
- `--limit` — cap results
- `--template` — Calibre template language (e.g. `{title:|:}` etc.)

### `add` — add new books

```bash
# Single file
calibredb add book.epub --title "X" --authors "A & B" -i 978...

# Recursive bulk
calibredb add --recurse \
  --one-book-per-directory \
  --automerge=ignore \
  --ignore=".DS_Store" --ignore="*.txt" \
  /path/to/folder

# Empty record (placeholder)
calibredb add --empty --title "Pending Scan" --authors "Unknown"
```

Key options:
- `-r, --recurse` — recurse into folders
- `-1, --one-book-per-directory` — group all files in a directory as formats of one book
- `--ignore=PATTERN` — repeatable glob for files to skip
- `--add=PATTERN` — repeatable glob to include non-ebook files
- `-d, --duplicates` — add even if it looks like a duplicate
- `-m, --automerge=ignore|overwrite|new_record` — overrides `--duplicates`
- Metadata flags: `-t/--title`, `-a/--authors`, `-i/--isbn`, `-I/--identifier`, `-T/--tags`, `-s/--series`, `-S/--series-index`, `-c/--cover`, `-l/--languages`

### `remove` — delete books

```bash
calibredb remove 5,8,13     # comma-separated
calibredb remove 5-10        # range (the high end is NOT included — 5,6,7,8,9 only)
calibredb remove 5 --permanent  # skip Trash
```

The default Trash behavior is recoverable via your OS Trash. Files end up in the system Trash, not Calibre's internal `.caltrash`.

### `add_format` — attach a file as a format to an existing book

```bash
calibredb add_format 17 /path/to/file.pdf            # replaces existing PDF if any
calibredb add_format 17 /path/to/file.pdf --dont-replace
calibredb add_format 17 /path/to/file.txt --as-extra-data-file  # attaches as data, not ebook
```

Replaces same-format files by default — useful for the merge pattern. `--as-extra-data-file` attaches arbitrary files (notes, errata, supplementary PDFs) without registering them as readable formats.

### `remove_format` — drop one format from a book

```bash
calibredb remove_format 17 PDF
calibredb remove_format 17 EPUB
```

Format names are the uppercase extension. Removing the last format leaves an empty book record.

### `show_metadata` / `set_metadata` — read/write per-record metadata

```bash
# Read
calibredb show_metadata 17
calibredb show_metadata 17 --as-opf > /tmp/current.opf

# Write via OPF (preferred for batch fixes)
calibredb set_metadata 17 /tmp/new.opf

# Write via --field (one-off changes)
calibredb set_metadata 17 --field title:"New Title" --field sort:"New Title"
calibredb set_metadata 17 --field "tags:philosophy,ethics"
calibredb set_metadata 17 --field "identifiers:isbn:9780195036503,goodreads:396359"
calibredb set_metadata 17 --field "languages:en"
calibredb set_metadata 17 --field "cover:/path/to/cover.jpg"

# List all settable fields
calibredb set_metadata --list-fields
```

**Footgun:** the title-sort field is named `sort` here, not `title_sort`. Author-sort is `author_sort`. Inconsistent — easy to get wrong.

### `embed_metadata` — push DB metadata back into files

```bash
calibredb embed_metadata 17
calibredb embed_metadata 1-100 200        # ranges + individual ids
calibredb embed_metadata all              # everything in the library
calibredb embed_metadata 17 --only-formats=epub --only-formats=mobi
```

Without this, the file's internal metadata can drift from the DB. After bulk metadata fixes, run `embed_metadata all` to sync.

### `export` — save books to a directory tree

```bash
calibredb export 5,8,13 --to-dir=/tmp/exported
calibredb export --all --to-dir=/tmp/full-export
```

Default template is `{author_sort}/{title}/{title} - {authors}`. Switches to disable parts:
- `--dont-write-opf` — skip the per-book OPF
- `--dont-save-cover` — skip the cover image
- `--dont-update-metadata` — don't embed DB metadata into the exported files
- `--single-dir` — flat layout, no subfolders
- `--formats=epub,pdf` — restrict to specific formats
- `--template` — custom path template

### `catalog` — generate a catalog file

```bash
calibredb catalog /tmp/catalog.csv
calibredb catalog /tmp/catalog.epub
calibredb catalog /tmp/catalog.xml --search="author:Solomon"
```

Output format is determined by the destination file's extension. Supported: csv, epub, mobi, xml, bib (with the corresponding plugin enabled). Options vary by output format — run `calibredb catalog dummy.csv --help` to see format-specific options.

### `search` — return matching IDs as a comma-separated list

```bash
calibredb search "author:Solomon"
calibredb search "formats:pdf AND tags:philosophy"
calibredb search "author:Solomon" --limit=5
```

The output is `5,8,13,17,18`. Useful for piping into `remove`, `set_metadata`, `embed_metadata`, etc.

### `check_library` — filesystem vs DB integrity report

```bash
calibredb check_library
calibredb check_library --csv
calibredb check_library --report=missing_formats,malformed_paths
calibredb check_library --vacuum-fts-db
```

Reports: `invalid_titles, extra_titles, invalid_authors, extra_authors, missing_formats, extra_formats, extra_files, missing_covers, extra_covers, malformed_formats, malformed_paths, failed_folders`.

Run after any large operation that touched the filesystem directly.

### `backup_metadata` — write per-book OPFs

```bash
calibredb backup_metadata           # only books with stale OPFs
calibredb backup_metadata --all     # all books
```

OPFs land at `<library>/<author>/<title (id)>/metadata.opf`. Calibre normally does this automatically; `--all` forces a full rewrite.

### `restore_database` — rebuild metadata.db from per-book OPFs

```bash
calibredb restore_database --really-do-it
```

Reads every `metadata.opf` in the library tree and rebuilds the DB. **Loses saved searches, user categories, plugboards, stored per-book conversion settings, custom recipes** — only the per-book metadata is restored. Last-resort recovery.

### `clone` — empty library with same custom-column/Virtual-Library settings

```bash
calibredb clone /path/to/new/library
```

Creates a new empty library that inherits the source library's custom columns, Virtual Libraries, and prefs. **Contains no books.** For copying a library with books, use `cp -R` on the source folder.

### `add_custom_column`, `custom_columns`, `remove_custom_column`, `set_custom`

For per-library custom columns (e.g. "My rating" `#myrating`, "Read on" `#readdate`). Datatypes: `bool, comments, composite, datetime, enumeration, float, int, rating, series, text`. Mostly out of scope for bulk curation; useful for personal annotation columns.

```bash
calibredb add_custom_column myrating "My rating" rating
calibredb custom_columns --details
calibredb set_custom myrating 17 5    # 1-5 stars
```

### `saved_searches` — manage stored search queries

```bash
calibredb saved_searches list
calibredb saved_searches add no-cover "cover:false"
calibredb saved_searches remove no-cover
```

Then reference via `--search="search:no-cover"`.

### `list_categories` — Tag Browser-style breakdown

```bash
calibredb list_categories
calibredb list_categories --csv
calibredb list_categories --item_count   # just counts per category
```

Useful for sanity-checking tags / series / publishers after edits.

### `fts_index`, `fts_search` — full-text search

```bash
calibredb fts_index enable
calibredb fts_index status
calibredb fts_index reindex --wait-for-completion
calibredb fts_search "phenomenology of spirit" --include-snippets
calibredb fts_search "freedom" --restrict-to=author:Solomon --output-format=json
```

FTS is opt-in per library. Indexing can take a while on large libraries; reindex after format changes.

## `ebook-meta`

Reads metadata from many formats; writes to fewer (the GUI manages the asymmetry). Operates on a single file at a time, no library involved.

```bash
# Read
ebook-meta book.epub
ebook-meta book.epub --to-opf=/tmp/meta.opf
ebook-meta book.epub --get-cover=/tmp/cover.jpg

# Write
ebook-meta book.epub --title "X" --authors "A & B"
ebook-meta book.epub --from-opf=/tmp/meta.opf
ebook-meta book.epub --cover=/tmp/cover.jpg
ebook-meta book.epub --identifier=isbn:978... --identifier=asin:B00...
ebook-meta book.epub --identifier=isbn:   # delete that identifier
```

**Read formats:** azw, azw1, azw3, azw4, cb7, cbc, cbr, cbz, chm, docx, epub, fb2, fbz, html, htmlz, imp, kepub, lit, lrf, lrx, mobi, odt, oebzip, opf, pdb, pdf, pml, pmlz, pobi, prc, rar, rb, rtf, snb, tpz, txt, txtz, updb, zip.

**Write formats:** azw, azw1, azw3, azw4, docx, epub, fb2, fbz, htmlz, kepub, lrf, mobi, odt, pdb, pdf, prc, rtf, tpz, txtz.

Notably: HTML, TXT, RAR, CBR cannot have metadata written. PDF write support is partial — title/author/identifiers OK; some fields silently ignored.

When `--authors` is set without `--author-sort`, the sort form is auto-generated as "Lastname, Firstname" — same convention as Calibre's DB. Use `&` to separate multiple authors.

## `fetch-ebook-metadata`

Pulls metadata from online sources. Specify at least one of `--title`, `--authors`, `--isbn`.

```bash
fetch-ebook-metadata --isbn=9780195036503
fetch-ebook-metadata --isbn=9780195036503 -o > /tmp/book.opf
fetch-ebook-metadata --isbn=9780195036503 -c /tmp/cover.jpg
fetch-ebook-metadata --title="Spirit of Hegel" --authors="Solomon"
fetch-ebook-metadata --identifier=goodreads:396359 -o
fetch-ebook-metadata --isbn=9780195036503 -p Goodreads -p Google -v
```

Flags:
- `-o, --opf` — output OPF XML (otherwise human-readable)
- `-c COVER` — download cover to that path
- `-d TIMEOUT` — default 30s
- `-p PLUGIN` — restrict sources, repeatable. Available: `Apple Books covers, Goodreads, Kindle hi-res covers, Google, Google Images, Amazon.com, Edelweiss, Open Library`
- `-v` — log to stderr (useful for debugging which source returned what)

When multiple plugins find matches, Calibre merges them. The OPF output is everything; the human-readable output is a subset.

## `ebook-convert`

```bash
# Basic
ebook-convert in.epub out.pdf
ebook-convert in.epub .pdf       # output name derived from input
ebook-convert in.epub out_folder # OEB folder of HTML files

# With metadata
ebook-convert in.epub out.pdf --from-opf=/tmp/meta.opf
ebook-convert in.epub out.epub --title "X" --authors "Y" --cover /tmp/c.jpg

# Help for a specific conversion
ebook-convert in.epub out.pdf --help    # PDF-specific options appear
```

The help text **depends on the input + output formats** — to see PDF options, you must pass a PDF output filename to `--help`.

Common option groups:
- **OUTPUT** — format-specific (PDF page margins, EPUB profile, etc.)
- **LOOK AND FEEL** — font size, line height, margins, justification, smarten/unsmarten punctuation, embed fonts
- **HEURISTIC PROCESSING** — `--enable-heuristics` to enable, then disable specific behaviors (`--disable-dehyphenate`, `--disable-renumber-headings`, etc.)
- **SEARCH AND REPLACE** — regex `--sr1-search` / `--sr1-replace`, up to sr3
- **STRUCTURE DETECTION** — XPath-based chapter detection
- **TABLE OF CONTENTS** — `--level1-toc`, `--level2-toc`, `--use-auto-toc`, `--toc-filter`
- **METADATA** — `--title`, `--authors`, `--title-sort`, `--author-sort`, `--cover`, `--publisher`, `--isbn`, etc.

Conversion is lossy in some directions (PDF → EPUB struggles with reflow, MOBI → EPUB usually fine).

## `calibre-server`

```bash
# Bare-minimum start
calibre-server "/path/to/library"

# Local-only with writes from CLI
calibre-server "/path/to/library" \
  --port=8080 \
  --listen-on=127.0.0.1 \
  --enable-local-write

# Background with PID file
calibre-server "/path/to/library" --port=8080 --pidfile=/tmp/calibre.pid &
```

Key options:
- `--port` — HTTP port (default 8080)
- `--listen-on` — interface; `127.0.0.1` for localhost only, `0.0.0.0` for all IPv4
- `--enable-local-write` — let unauthenticated local connections make changes (needed for `calibredb --with-library=http://localhost:...`)
- `--enable-auth` / `--auth-mode=basic|auto` / `--userdb` — user-authenticated multi-user setup
- `--trusted-ips` — IP allowlist for write access
- `--url-prefix` — for reverse-proxy deployments
- `--pidfile` — write PID for systemd / launchctl integration
- `--access-log` / `--log` — log destinations

Use the Content Server when the GUI must stay open during CLI writes, or to expose the library over the network for OPDS-capable apps (Marvin, KOReader, Foliate, etc.).
