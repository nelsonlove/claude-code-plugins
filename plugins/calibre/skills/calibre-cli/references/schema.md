# Calibre on-disk and database schema

Where Calibre keeps things and what the SQLite schema looks like. Read this for any direct SQL inspection (read-only is safe; writes will bypass Calibre's derived state and should be avoided).

## File layout

A Calibre library is a single directory. Everything is under it:

```
<library>/
├── metadata.db                      # SQLite — the source of truth
├── metadata_db_prefs_backup.json    # Calibre prefs snapshot
├── full-text-search.db              # Optional FTS index
├── .caltrash/                       # Calibre's own deleted-record holding area
├── <Author Sort>/                   # One folder per author (uses author_sort)
│   └── <Title (id)>/                # One folder per book, title + numeric id
│       ├── <Title> - <Authors>.epub # Each format as a separate file
│       ├── <Title> - <Authors>.pdf
│       ├── cover.jpg                # Cover image
│       └── metadata.opf             # Per-book metadata backup
└── ...
```

Notes:
- The `(id)` suffix on the title folder is Calibre's book ID in the DB. **Renaming this folder breaks the link.** Always use `calibredb`, never `mv`.
- The author folder uses the `author_sort` form ("Lastname, Firstname"), not the displayed `name`.
- Multi-author books go under the *first* author's folder (alphabetical by author_sort).
- Calibre regenerates `metadata.opf` every time DB metadata changes.

## `metadata.db` schema (essentials)

This is a SQLite 3 file. Open read-only with `sqlite3 -readonly` for safe inspection.

### Core tables

```sql
-- One row per book
CREATE TABLE books (
    id INTEGER PRIMARY KEY,
    title TEXT,
    sort TEXT,             -- title_sort
    author_sort TEXT,      -- denormalized; also computed from books_authors_link
    timestamp TIMESTAMP,   -- date added to library
    pubdate TIMESTAMP,
    series_index REAL,
    isbn TEXT DEFAULT "" COLLATE NOCASE,  -- legacy; ISBN is now in `identifiers`
    lccn TEXT DEFAULT "",
    path TEXT,             -- relative folder path under library root
    flags INTEGER DEFAULT 1,
    uuid TEXT,
    has_cover BOOL DEFAULT 0,
    last_modified TIMESTAMP
);

-- One row per author entry (variant spellings → multiple rows)
CREATE TABLE authors (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE,
    sort TEXT COLLATE NOCASE,
    link TEXT NOT NULL DEFAULT ""
);

-- M:N link table
CREATE TABLE books_authors_link (
    id INTEGER PRIMARY KEY,
    book INTEGER NOT NULL,
    author INTEGER NOT NULL,
    UNIQUE(book, author)
);

-- One row per (book, format) pair
CREATE TABLE data (
    id INTEGER PRIMARY KEY,
    book INTEGER NOT NULL,
    format TEXT NOT NULL COLLATE NOCASE,   -- e.g. 'EPUB', 'PDF'
    uncompressed_size INTEGER NOT NULL,
    name TEXT NOT NULL,                    -- filename without extension
    UNIQUE(book, format)
);

-- Tags
CREATE TABLE tags (id INTEGER PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE, UNIQUE(name));
CREATE TABLE books_tags_link (id INTEGER PRIMARY KEY, book INTEGER NOT NULL, tag INTEGER NOT NULL, UNIQUE(book, tag));

-- Series (a book belongs to at most one series; index lives on `books`)
CREATE TABLE series (id INTEGER PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE, sort TEXT, UNIQUE(name));
CREATE TABLE books_series_link (id INTEGER PRIMARY KEY, book INTEGER NOT NULL, series INTEGER NOT NULL, UNIQUE(book, series));

-- Identifiers (ISBN, Goodreads, ASIN, DOI, etc.)
CREATE TABLE identifiers (
    id INTEGER PRIMARY KEY,
    book INTEGER NOT NULL,
    type TEXT NOT NULL DEFAULT "isbn" COLLATE NOCASE,
    val TEXT NOT NULL COLLATE NOCASE,
    UNIQUE(book, type)
);

-- Languages (separate table; books_languages_link is M:N)
CREATE TABLE languages (id INTEGER PRIMARY KEY, lang_code TEXT NOT NULL COLLATE NOCASE, UNIQUE(lang_code));
CREATE TABLE books_languages_link (id INTEGER PRIMARY KEY, book INTEGER NOT NULL, lang_code INTEGER NOT NULL, item_order INTEGER NOT NULL DEFAULT 0, UNIQUE(book, lang_code));

-- Publisher (M:N, but usually 1-to-1 in practice)
CREATE TABLE publishers (id INTEGER PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE, sort TEXT, UNIQUE(name));
CREATE TABLE books_publishers_link (id INTEGER PRIMARY KEY, book INTEGER NOT NULL, publisher INTEGER NOT NULL, UNIQUE(book));

-- Comments (the book description, one row per book)
CREATE TABLE comments (id INTEGER PRIMARY KEY, book INTEGER NOT NULL UNIQUE, text TEXT NOT NULL COLLATE NOCASE);

-- Ratings (1-10, stored as 0-10 doubled; UI shows 0-5)
CREATE TABLE ratings (id INTEGER PRIMARY KEY, rating INTEGER CHECK(rating > -1 AND rating < 11), UNIQUE(rating));
CREATE TABLE books_ratings_link (id INTEGER PRIMARY KEY, book INTEGER NOT NULL, rating INTEGER NOT NULL, UNIQUE(book, rating));
```

### Useful denormalized views

Calibre ships these views; lean on them for human-readable queries:

- `meta` — flattened metadata for each book (joins everything)
- `tag_browser_authors`, `tag_browser_tags`, etc. — counts per category

### Common query patterns

```sql
-- All books with their authors (group_concat over the M:N)
SELECT b.id, b.title, group_concat(a.name, ' & ') AS authors
FROM books b
LEFT JOIN books_authors_link bal ON bal.book = b.id
LEFT JOIN authors a ON a.id = bal.author
GROUP BY b.id;

-- Books missing covers
SELECT id, title FROM books WHERE has_cover = 0;

-- Books missing ISBN
SELECT id, title FROM books WHERE id NOT IN (SELECT book FROM identifiers WHERE type='isbn');

-- Duplicate-title candidates
SELECT title, COUNT(*) FROM books GROUP BY lower(title) HAVING COUNT(*) > 1;

-- Author dedup candidates (variants of the same name)
SELECT id, name, COUNT(bal.book) AS books
FROM authors a LEFT JOIN books_authors_link bal ON bal.author = a.id
GROUP BY a.id ORDER BY a.name;
```

## OPF format

OPF (Open Packaging Format) is the XML metadata format Calibre uses for OPF backups, `fetch-ebook-metadata`, and `set_metadata` round-tripping. It's a Dublin Core-based schema.

Minimal OPF:

```xml
<?xml version='1.0' encoding='utf-8'?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="uuid_id" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:identifier opf:scheme="ISBN">9780195036503</dc:identifier>
    <dc:identifier opf:scheme="uuid" id="uuid_id">d2a...</dc:identifier>
    <dc:title>In the Spirit of Hegel</dc:title>
    <dc:creator opf:role="aut" opf:file-as="Solomon, Robert C.">Robert C. Solomon</dc:creator>
    <dc:language>eng</dc:language>
    <dc:publisher>Oxford University Press</dc:publisher>
    <dc:date>1983-01-01</dc:date>
    <dc:description>The Phenomenology of Spirit...</dc:description>
    <dc:subject>Philosophy</dc:subject>
    <meta name="calibre:title_sort" content="In the Spirit of Hegel"/>
    <meta name="calibre:rating" content="2"/>
    <meta name="calibre:series" content=""/>
    <meta name="calibre:series_index" content="0"/>
    <meta name="calibre:timestamp" content="2026-05-14T00:00:00+00:00"/>
  </metadata>
</package>
```

Notes:
- `dc:creator` `opf:file-as` is the author-sort form (used to file the book).
- Tags become `<dc:subject>` (repeatable).
- Series / rating / title-sort are Calibre-specific `<meta>` extensions, not Dublin Core.
- The cover image is **not** embedded in the OPF — set it separately with `set_metadata --field cover:/path`.

`calibredb show_metadata <id> --as-opf` dumps the canonical OPF Calibre would write for a given book — useful as a template.

## File layout details for derived state

- **Cover thumbnails**: stored inside `metadata.db` itself (BLOB in a `book_thumbnail_data` table on some versions, or as files inside `<book folder>/.thumbnail` depending on Calibre version).
- **Search index for FTS**: `full-text-search.db` (separate SQLite).
- **User database for Content Server**: `users.sqlite` (often at `~/Library/Preferences/calibre/` on macOS or via `--userdb` path).

## Trash and recovery

When `calibredb remove` is called without `--permanent`:
- The book's folder is moved to your OS Trash (not the library's `.caltrash`).
- The DB row is deleted.
- Restoring from OS Trash will not re-register the book — you'd need to `add` it back.

The library's `.caltrash` subfolder is for Calibre's own automatic recovery on crashes — don't manually depend on it.

## Cross-library migration

To copy books between libraries:
- Easiest: `calibredb export` from source, `calibredb add --automerge=ignore` into target.
- Preserves all metadata via OPF round-trip.
- Custom column values transfer only if the target library has matching custom columns (use `calibredb clone` to copy column definitions first).

To merge two libraries:
- `calibredb clone target_path` — empty library with same schema
- Repeat: export from source, import into target
- Or: just move book folders + run `calibredb restore_database --really-do-it` (rebuilds DB from per-book OPFs)
