---
description: Read-only audit of a Calibre library — surfaces metadata problems by repair class
argument-hint: <library-path-or-content-server-url>
allowed-tools: Bash, Read
---

Run a comprehensive read-only audit of the Calibre library at: `$ARGUMENTS`

This command is **read-only**. Do not mutate anything. The output is a triage report — the user decides what to fix.

## Setup

1. Determine the library: if `$ARGUMENTS` starts with `http://` or `https://`, treat it as a Content Server URL and use `--with-library=$ARGUMENTS` on all `calibredb` invocations. Otherwise treat it as a filesystem path, use `--library-path "$ARGUMENTS"`, and identify the `metadata.db` for direct read-only SQLite queries.

2. Verify the library exists and contains `metadata.db` (filesystem case) or responds to a probe `calibredb list --limit=1` (Content Server case). If not, stop and report the error.

3. **For the filesystem case**, export `DB` as an env var once for the whole audit so each Python block can read it via `os.environ['DB']` without restating the path:
   ```bash
   export DB="<path to metadata.db>"
   ```
   (Skip this if running against a Content Server — Python-based class checks need direct DB access and aren't applicable in that mode; fall back to `calibredb`-based versions if a future PR adds them.)

## What to surface

Use the queries below, grouped by repair class. The heuristics here are tuned to **minimize false positives** at the cost of occasionally missing edge cases — see notes in each section. For deeper detail, consult Recipe 2 in `references/workflows.md` from the `calibre-cli` skill.

### Class A — Title/author swap

Records where the title and author got flipped during import. Signature: `author_sort` contains stopwords (`the`, `of`, `and`, `for`, `in`, etc.) that are essentially never present in a person's name but extremely common in book titles. Do **not** key on comma count — multi-author entries naturally have multiple commas (one per author).

```bash
python3 - <<'PYEOF'
import sqlite3, os
conn = sqlite3.connect(f"file:{os.environ['DB']}?mode=ro", uri=True)
# Note: " by " deliberately omitted — would false-positive on real author_sort
# entries like "Foreword by Smith, John" or "Illustrated by Robertson, Keith".
STOPS = [" the ", " of ", " and ", " for ", " in ", " what ", " did ", " from ", " to "]
hits = 0
for id_, title, asort in conn.execute("SELECT id, title, author_sort FROM books"):
    padded = " " + (asort or "").lower() + " "
    matched = [s.strip() for s in STOPS if s in padded]
    if matched:
        hits += 1
        print(f"  #{id_}: title={title[:55]!r}")
        print(f"       author_sort={asort[:60]!r}  [matched: {matched}]")
print(f"  Class A total: {hits}")
PYEOF
```

### Class B — Filename-as-title

Titles that are clearly raw filenames (Calibre fell back to filename because the source file lacked metadata):

```sql
SELECT id, title FROM books
WHERE title GLOB '[0-9][0-9][0-9][0-9]*'   -- ISBN-shaped numeric prefix
   OR title LIKE '%.pdf'
   OR title LIKE '%.epub'
   OR title GLOB '*[a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9]*';  -- hash-like
```

### Class C — Dirty author strings

Author records with syntactic cruft from import-time string mangling:

```sql
SELECT id, name FROM authors
WHERE name LIKE '%;%'
   OR name LIKE '%(Author)%'
   OR name LIKE '%, author%'
   OR name LIKE '%;'
   OR name GLOB '*[A-Z].[A-Z]*';   -- missing space like 'C.Solomon'
```

### Class D — Author table dedup

Variant spellings of the same person. Normalize each author's name to a sorted token set (lowercased, punctuation stripped) and flag exact collisions. This catches `Robert C. Solomon` / `Robert C.Solomon` / `Solomon, Robert C.` / `Solomon, Robert C.;` — all collapse to `{c, robert, solomon}`. Known limitation: variants with different token counts (`Kathleen Higgins` vs `Kathleen M. Higgins` vs `Kathleen Marie Higgins`) won't collide — fuzzy match is a v0.1.2 goal.

```bash
python3 - <<'PYEOF'
import sqlite3, os, re
conn = sqlite3.connect(f"file:{os.environ['DB']}?mode=ro", uri=True)
def norm(name):
    return " ".join(sorted(re.findall(r"[a-z]+", name.lower())))
groups = {}
for id_, name in conn.execute("SELECT id, name FROM authors"):
    groups.setdefault(norm(name), []).append((id_, name))
hits = 0
for key, variants in sorted(groups.items()):
    if len(variants) > 1:
        hits += 1
        ids = ",".join(str(i) for i, _ in variants)
        names = " | ".join(n for _, n in variants)
        print(f"  [{key}] ({len(variants)}× / ids {ids}): {names}")
print(f"  Class D total dedup groups: {hits}")
PYEOF
```

### Class E — Duplicate-title candidates

Books with the same normalized title (potential duplicate records to merge):

```sql
SELECT lower(title) AS norm, GROUP_CONCAT(id), COUNT(*) AS n
FROM books GROUP BY norm HAVING n > 1 ORDER BY n DESC, norm;
```

Note: SQLite's `GROUP_CONCAT` does not accept `ORDER BY` inside the aggregate (that syntax is MySQL-only); IDs come back in undefined order.

### Class F — Cruft in titles

```sql
SELECT id, title FROM books
WHERE title LIKE '%z-lib.org%' OR title LIKE '%libgen%'
   OR title LIKE '%(epub)%'   OR title LIKE '%nodrm%';
```

### Class G — Unknown authors

```sql
SELECT b.id, b.title FROM books b
WHERE b.id IN (SELECT book FROM books_authors_link WHERE author IN (SELECT id FROM authors WHERE name='Unknown'))
   OR b.id NOT IN (SELECT book FROM books_authors_link);
```

### Health — filesystem vs DB integrity

`calibredb check_library` requires either the Calibre GUI closed OR a running Content Server. Wrap the call in error detection and surface the lock condition clearly rather than letting the error bleed into the report:

```bash
HEALTH=$(calibredb check_library --library-path "$LIB" --csv 2>&1)
if echo "$HEALTH" | grep -q "Another calibre program"; then
  echo "  Skipped — Calibre GUI is open and holds an exclusive lock."
  echo "  To enable this check, either:"
  echo "    1) Close the Calibre GUI and re-run the audit, or"
  echo "    2) Start the Content Server (calibre-server --enable-local-write \"\$LIB\")"
  echo "       and re-run with --with-library=http://localhost:8080/#libname"
elif [ -z "$HEALTH" ]; then
  echo "  Clean — no filesystem/DB discrepancies."
else
  echo "$HEALTH"
fi
```

## Output

After running every section, present a single categorized findings report. For each class, list affected IDs with title/author preview. End with a totals summary and suggested next commands:

- "X books with title/author swaps → run `/calibre:fix-metadata` per record"
- "Y duplicate pairs → run `/calibre:dedup` to merge"
- "Z books with Unknown authors and no ISBN → manual research needed"

Do not propose fixes here. The follow-up commands handle that.

## Important

- If `calibredb check_library` (when it runs) reports `failed_folders` or `malformed_paths`, **stop and tell the user**. They should run `/calibre:backup` and consider `calibredb restore_database --really-do-it` (see Recipe 10 in workflows.md) before further automated edits.
- The Class A heuristic is intentionally conservative — it catches the obvious swap pattern (book-title-shaped strings ending up in `author_sort`) but not every possible swap. If you suspect specific records are swapped but Class A didn't flag them, eyeball `calibredb show_metadata <id>` directly.
