---
name: calibre-cli
description: This skill should be used when the user works with a Calibre ebook library or invokes any Calibre CLI tool — calibredb, ebook-meta, fetch-ebook-metadata, ebook-convert, calibre-server. Triggers on phrases like "Calibre library", "calibredb", "ebook metadata", "EPUB/MOBI/PDF library", "add books to Calibre", "fix book metadata", "merge duplicate books", "ISBN lookup for my library", "metadata.db", or any mention of Kovid Goyal's Calibre. Also use it when the user references an Obsidian/JD path containing "Calibre libraries" or a `metadata.db` file. Captures the canonical OPF round-trip workflow, the Content Server escape hatch for the GUI-lock problem, footguns around field naming and author syntax, and patterns for merging duplicates (which Calibre has no built-in command for). Use this skill even if the user does not explicitly name "Calibre" — if you see a folder containing `metadata.db` plus author-named subfolders, that is a Calibre library and this skill applies.
---

# Calibre CLI

Calibre ships a CLI suite alongside its GUI. Most "manage my ebook library" tasks are best done from the shell — bulk operations are slow and clumsy in the GUI. The CLI is mature, well-documented, and stable across versions, but it has several footguns that are not obvious from `--help` alone. This skill captures the non-obvious parts.

## The five binaries that matter

| Binary | Purpose | Use when |
|---|---|---|
| `calibredb` | Library DB operations | Adding, removing, querying, setting metadata, merging — anything that touches `metadata.db` |
| `ebook-meta` | Single-file metadata read/write | Want to read or write metadata inside a file without involving a library |
| `fetch-ebook-metadata` | Pull metadata from online sources | Have an ISBN or title and want canonical metadata + cover |
| `ebook-convert` | Format conversion | Converting EPUB ↔ MOBI ↔ PDF ↔ AZW3 ↔ etc. |
| `calibre-server` | Content server (HTTP/OPDS) | Need to bypass the GUI lock for concurrent CLI writes |

Ignore the rest (`calibre-debug`, `calibre-smtp`, `lrf2lrs`, etc.) unless a specific need arises.

## Library connection

Always pass `--library-path` (or its alias `--with-library`) to every `calibredb` invocation. Two forms:

```bash
# Direct path — requires Calibre GUI to be closed
calibredb list --library-path "/path/to/library" --fields=id,title --limit 5

# Content Server URL — works while the GUI is running
calibredb list --with-library=http://localhost:8080/#mylibrary --fields=id,title --limit 5
```

**The GUI lock is the single most common failure mode.** If `calibredb` errors with "Another calibre program ... is running", choose one of:

1. Close the Calibre GUI (simplest).
2. Start the Content Server: in the GUI, *Preferences → Sharing over the net → Start server* (or run `calibre-server "/path/to/library" --port 8080 --enable-local-write` from a shell), then use the `http://localhost:8080/#libname` URL form.
3. For read-only operations only, query `metadata.db` directly with `sqlite3 -readonly` — this bypasses Calibre but won't update derived state (cover thumbnails, search indexes).

The `#libname` part of the URL is the library's display name as Calibre knows it. Use `#-` to list available library IDs on the server.

## The canonical OPF round-trip workflow

This is the most important pattern in the skill. For any non-trivial metadata change — fixing a corrupted record, refreshing from ISBN, normalizing a batch — do not pile up `--field` flags. Use OPF files instead.

```bash
# 1. Fetch canonical metadata from online sources into an OPF file
fetch-ebook-metadata --isbn=9780195036503 -o > /tmp/book.opf

# 2. Optionally fetch a cover into a sibling file
fetch-ebook-metadata --isbn=9780195036503 -c /tmp/cover.jpg -o > /tmp/book.opf

# 3. Apply the OPF to a book by ID
calibredb set_metadata --library-path "$LIB" 17 /tmp/book.opf

# 4. If a cover was downloaded, set it explicitly (OPF doesn't embed binary)
calibredb set_metadata --library-path "$LIB" --field cover:/tmp/cover.jpg 17

# 5. Push the new metadata into the file itself (so internal metadata matches DB)
calibredb embed_metadata --library-path "$LIB" 17
```

Why this is better than `--field title:X --field authors:Y --field ...`:

- OPF carries every field in one round trip — no risk of forgetting `sort` when changing `title`.
- The metadata download already validates ISBN, normalizes author order, and pulls publisher / pubdate / language / comments / identifiers in one shot.
- Reproducible: keep the OPF file as a record of what was applied.

To see what's currently set on a book before overwriting:

```bash
calibredb show_metadata --library-path "$LIB" --as-opf 17 > /tmp/current.opf
```

## Adding books

Single file or directory of files:

```bash
# Single ebook with explicit metadata
calibredb add --library-path "$LIB" book.epub --title "X" --authors "Author Name" --isbn 9780...

# Recursive bulk-add from a folder tree
calibredb add --library-path "$LIB" \
  --recurse \
  --automerge=ignore \
  --ignore=".DS_Store" --ignore="*.txt" --ignore="*.opf" \
  "/path/to/folder"
```

**`--automerge` modes are the entire deduplication story for ingest:**

- `ignore` — duplicate formats discarded silently (safest default)
- `overwrite` — duplicate formats in the library are replaced with the new file
- `new_record` — duplicate formats become separate book records (almost never what you want)

**`--one-book-per-directory`** is useful when a folder tree contains one directory per book with multiple format files inside (e.g., `Foo/foo.epub` + `Foo/foo.mobi` should become one book with two formats).

## Merging duplicate books

**Calibre has no built-in book-level merge subcommand.** The canonical workaround:

```bash
# Add the duplicate's format to the keeper (replaces same-format by default)
calibredb add_format --library-path "$LIB" <keeper_id> "/path/to/dup_file.ext"

# Remove the duplicate record (goes to Trash by default — recoverable)
calibredb remove --library-path "$LIB" <dup_id>
```

For same-format duplicates (two PDFs of the same book), `add_format` replaces by default. Pass `--dont-replace` to keep the keeper's existing file. Check file sizes first via `data.uncompressed_size` in `metadata.db` to decide which is better.

`calibredb remove` uses the system Trash by default; pass `--permanent` to skip the Trash. Default behavior is the safe one.

## Field naming and value syntax

The `--field` option on `calibredb set_metadata` accepts these names. **Several do not match what `--help` or other commands might suggest** — see `references/footguns.md` for the gory details.

| Field name | What it sets | Notes |
|---|---|---|
| `title` | Title | Does NOT regenerate `sort` automatically — set both |
| `sort` | Title-sort field | Field is called `sort`, not `title_sort` |
| `authors` | Authors | Multiple authors join with `&`, not `,` or `;` |
| `author_sort` | Author-sort | Does match field name; set explicitly when authors change |
| `tags` | Tags | Comma-separated |
| `series`, `series_index` | Series + position | Index is decimal (1, 1.5, 2) |
| `languages` | Languages | ISO 639 codes — `en`, `fr`, not `English` |
| `publisher`, `pubdate`, `comments`, `rating` | Self-explanatory | `rating` is 1-5 |
| `identifiers` | Cross-system IDs | `identifiers:isbn:X,goodreads:Y,doi:Z` |
| `cover` | Cover image | Pass a file path: `cover:/path/to/img.jpg` |

Run `calibredb set_metadata --list-fields` against the actual library to confirm.

## Search query language

Calibre's search syntax is shared between `calibredb search`, `--search` on most commands, and the Content Server URLs. Examples:

```text
author:Solomon
title:"Spirit of Hegel"
identifiers:isbn:9780195036503
formats:pdf
tags:philosophy
series:"true"               # has any series
comments:""                 # empty comments
id:5                        # specific record
id:5-10                     # range (exclusive on the high end!)
author:Solomon AND NOT tags:fiction
```

Search is case-insensitive by default and supports `AND` / `OR` / `NOT` (or `-` prefix).

## Backups before risky operations

Two complementary mechanisms:

```bash
# Filesystem snapshot (cheap, easy restore)
cp -R "/path/to/library" "/path/to/library.backup-$(date +%Y-%m-%d_%H%M%S)"

# Force regeneration of per-book OPF files in each book folder
calibredb backup_metadata --library-path "$LIB" --all
```

`backup_metadata` writes a `metadata.opf` into every book folder. Combined with `calibredb restore_database --really-do-it`, a completely corrupted `metadata.db` can be rebuilt from the per-book OPFs (you lose saved searches, plugboards, custom column display settings — see `references/footguns.md`).

For automated workflows, run `cp -R` before mutating operations, then `trash` (never `rm`) the backup once verified.

## When to use what — quick decision tree

- **Query / read** → `calibredb list`, `calibredb search`, `calibredb show_metadata`
- **Add a file** → `calibredb add`
- **Add a folder of files** → `calibredb add --recurse --automerge=ignore`
- **Fix one record's metadata via ISBN** → OPF round-trip (see above)
- **Merge two records** → `add_format` + `remove`
- **Convert EPUB ↔ PDF etc.** → `ebook-convert` (run `ebook-convert in.epub out.pdf --help` for full options)
- **Read/write metadata in a single file outside a library** → `ebook-meta`
- **Library health check** → `calibredb check_library`
- **GUI is open and we need writes** → start `calibre-server` or use `--with-library=http://...`

## Additional resources

Read these references as they become relevant:

- **`references/cli-reference.md`** — Per-subcommand option reference for `calibredb` and the other binaries. Consult before invoking a less common subcommand (`embed_metadata`, `catalog`, `clone`, `restore_database`).
- **`references/schema.md`** — `metadata.db` SQLite schema, file layout on disk, OPF format basics, where things live in a Calibre library. Read this for any SQLite query work or filesystem-level inspection.
- **`references/footguns.md`** — Detailed gotchas with reproductions: the `sort` vs `title_sort` field-name inconsistency, why `Solomon, Robert C.;Flores, Fernando;` becomes ONE author, `automerge` edge cases, the Trash behavior, PDF write limitations, language code requirements. Read this before any bulk edit.
- **`references/workflows.md`** — End-to-end recipes: full library audit, batch ISBN-driven metadata fix, dedup pass, large-scale ingest from a folder dump, lossless format conversion. Each recipe is copy-pasteable but explains the reasoning so it can be adapted.

If the user is doing a one-off lookup, this `SKILL.md` is enough. If they are doing a non-trivial batch operation, read the relevant reference file first.
