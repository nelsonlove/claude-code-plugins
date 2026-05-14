---
description: Read-only audit of a Calibre library — surfaces metadata problems by repair class
argument-hint: <library-path-or-content-server-url>
allowed-tools: Bash, Read
---

Run a comprehensive read-only audit of the Calibre library at: `$ARGUMENTS`

This command is **read-only**. Do not mutate anything. The output is a triage report — the user decides what to fix.

## Setup

1. Determine the library: if `$ARGUMENTS` starts with `http://` or `https://`, treat it as a Content Server URL and use `--with-library=$ARGUMENTS` on all `calibredb` invocations. Otherwise treat it as a filesystem path and use `--library-path "$ARGUMENTS"`, and identify the `metadata.db` for direct read-only SQLite queries.

2. Verify the library exists and contains `metadata.db` (filesystem case) or responds to a probe `calibredb list --limit=1` (Content Server case). If not, stop and report the error.

## What to surface

Follow Recipe 2 in `references/workflows.md` from the `calibre-cli` skill. Run these checks and report findings grouped by repair class:

- **Class A — Title/author swap**: records where `title` looks like a person's name AND `author_sort` looks like a book title
- **Class B — Filename-as-title**: titles matching ISBN patterns (`[0-9]{10}.pdf`), hash patterns, or ending in `.pdf`/`.epub` extension
- **Class C — Dirty author strings**: authors containing `;`, `(Author)`, `, author`, trailing `;`, missing-space patterns like `C.Solomon`
- **Class D — Author table dedup**: variant spellings of the same person (look for surname clusters in `authors`)
- **Class E — Duplicate books**: normalized-title collisions (`LOWER(title)` grouping with COUNT > 1)
- **Class F — Cruft in titles**: `z-lib.org`, `libgen`, `nodrm`, `(epub)` markers
- **Class G — Unknown authors**: records with `author='Unknown'` or empty
- **Health**: run `calibredb check_library --csv` and surface anything non-empty

## Output

After running the queries, present a categorized findings report. For each class, list affected IDs with title/author preview. End with a totals summary and suggested next commands:

- "X books with metadata corruption → run `/calibre:fix-metadata` per record or in batch"
- "Y duplicate pairs → run `/calibre:dedup` to merge"
- "Z books missing ISBN → can't fetch online metadata without manual research"

Do not propose fixes here. The follow-up commands handle that.

## Important

If the audit reveals serious DB corruption (check_library reports `failed_folders` or `malformed_paths`), stop and tell the user. They should run `/calibre:backup` and consider `calibredb restore_database --really-do-it` (see Recipe 10 in workflows.md) before further automated edits.
