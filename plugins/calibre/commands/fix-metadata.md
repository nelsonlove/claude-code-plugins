---
description: Fix one book's metadata via the OPF round-trip (fetches from ISBN/title, previews, applies)
argument-hint: <library-path> <book-id> [isbn]
allowed-tools: Bash, Read
---

Fix the metadata for a single book in the Calibre library, using the canonical OPF round-trip workflow from the `calibre-cli` skill.

Arguments:
- `$1` — library path or Content Server URL
- `$2` — book ID (the `id` from `calibredb list`)
- `$3` — optional ISBN to look up

This command **modifies the library**. Halt and confirm before writing.

## Steps

1. **Validate arguments**. If `$1` and `$2` are not both provided, stop and explain the expected invocation.

2. **Show the current state**. Run `calibredb show_metadata --library-path "$1" --as-opf "$2"` and display it. The user should see exactly what is about to be replaced.

3. **Decide how to fetch new metadata**:
   - If `$3` (ISBN) was provided, use `fetch-ebook-metadata --isbn=$3 -o`
   - Otherwise, look at the current record's identifiers in the DB. If an ISBN is already there, use it.
   - Otherwise, attempt a title+author search: `fetch-ebook-metadata --title="..." --authors="..." -o`
   - If none of these can succeed, stop and ask the user to either provide an ISBN or do manual research.

4. **Fetch into temp files**:
   ```bash
   fetch-ebook-metadata <args> -o > /tmp/calibre-fix-$2.opf 2>/tmp/calibre-fix-$2.log
   fetch-ebook-metadata <args> -c /tmp/calibre-fix-$2-cover.jpg -o > /tmp/calibre-fix-$2.opf 2>/dev/null
   ```
   Note that fetching twice (once for OPF, once for cover) is intentional — `-c` doesn't always emit OPF reliably. If the cover doesn't download, that's fine; step 8 conditionally skips the cover-application sub-step.

5. **Sanity-check the match** (footgun #19). ISBN-based lookups return *confident wrong matches* when the ISBN is wrong — same publisher, same range, totally different book. Before showing the user anything as "proposed", do the title-overlap check:

   ```bash
   PROPOSED=$(grep -m1 'dc:title' /tmp/calibre-fix-$2.opf | sed -E 's/.*<dc:title>([^<]+)<.*/\1/')
   CURRENT=$(calibredb list --library-path "$1" --fields=title --search="id:$2" --for-machine \
             | python3 -c "import json,sys; print(json.load(sys.stdin)[0]['title'])")
   export PROPOSED CURRENT
   python3 - <<'PYEOF'
   import os, sys
   stops = {'the','a','an','of','for','in','and','&','to','on','by','from','with'}
   a = set(w.lower() for w in os.environ['PROPOSED'].split() if w.lower() not in stops)
   b = set(w.lower() for w in os.environ['CURRENT'].split()  if w.lower() not in stops)
   overlap = a & b
   print(f'Overlap: {overlap}')
   sys.exit(0 if len(overlap) >= 2 else 1)
   PYEOF
   ```

   The `export` + `os.environ` pattern is deliberate — passing the title strings via env vars rather than shell-interpolating them into the Python source. Titles routinely contain apostrophes ("The Devil's Dictionary", "Nietzsche's Genealogy of Morals"), and a single quote inside a triple-quoted Python string passed via `python3 -c "..."` closes the string early and raises a `SyntaxError`. The quoted heredoc (`<<'PYEOF'`) prevents shell expansion inside the Python source so apostrophes pass through cleanly.

   If the overlap check fails (fewer than 2 significant shared words), **do not present the metadata as if it's good**. Tell the user: "The ISBN $3 returned title '$PROPOSED' which does not match the current title '$CURRENT'. This looks like the wrong book. Want me to try a different ISBN, fall back to a title-based search, or set metadata manually?"

   Exception: if the current title is itself garbage (e.g., `0195036506.pdf`, a filename-as-title from an unmetadated ingest), the overlap will be empty even with a correct match. In that case, ask the user to provide an "expected title" or just review the proposed metadata manually.

6. **Preview the proposed metadata**. Show the diff: current title/authors/publisher/pubdate/identifiers vs proposed. Surface anything surprising (publisher change, language change, an ISBN that doesn't match what was requested).

7. **Halt and confirm**. Ask the user explicitly: "Apply this metadata to book #$2? [y/N]". Do not proceed without an affirmative answer.

8. **Apply** in this order:
   ```bash
   calibredb set_metadata --library-path "$1" "$2" /tmp/calibre-fix-$2.opf
   # Only if cover was downloaded:
   [ -s /tmp/calibre-fix-$2-cover.jpg ] && \
     calibredb set_metadata --library-path "$1" --field "cover:/tmp/calibre-fix-$2-cover.jpg" "$2"
   ```

9. **Push to the file**:
   ```bash
   calibredb embed_metadata --library-path "$1" "$2"
   ```

   If this errors with `podofo.Error: PdfErrorCode::InvalidXRef` or similar (footgun #20), the file is a corrupt PDF. Retry with `--only-formats=epub --only-formats=mobi --only-formats=azw3` to skip the PDF — the DB metadata is still correct, only the file's internal metadata stays stale.

10. **Verify**. Run `calibredb show_metadata --library-path "$1" "$2"` and confirm the new values stuck.

## Footguns to watch for

(All documented in `references/footguns.md`; surfacing the most relevant here.)

- **Footgun #19 — wrong ISBN, confident wrong match.** Step 5 enforces the title-overlap check; do not skip it. ISBN-based lookups *always* return some book, even when the ISBN identifies a totally different work.
- **Footgun #20 — corrupt PDF crashes `embed_metadata`.** Step 9 has the workaround.
- The OPF sets `title` and `sort` together — no manual sort-field maintenance needed when going through OPF.
- The cover is not in the OPF; it must be set separately as a `--field cover:` flag.
- If the book has multiple formats (EPUB + PDF + MOBI), `embed_metadata` updates all of them by default. Restrict with `--only-formats=epub` if you want to preserve a particular file's internal metadata.
- For PDFs, some metadata fields are silently dropped — see footgun #7. Title/author/identifiers/cover go in; series/rating may not.
