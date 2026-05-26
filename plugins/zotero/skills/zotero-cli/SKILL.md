---
name: zotero-cli
description: This skill should be used when the user works with a Zotero research library or invokes any zotero-mcp-server CLI — `zotero-cli` (standalone library access) or `zotero-mcp` (MCP server / setup). Triggers on phrases like "Zotero library", "zotero-cli", "BibTeX key", "citation", "DOI lookup", "PDF annotations", "Better BibTeX", "reading list", "literature review", or any reference to `~/Zotero/zotero.sqlite` or a `storage/` PDF attachments folder. Also use it when the user asks to add a paper by DOI/arXiv URL, extract annotations, search a personal reference library, or manage collections. Captures the local/web/hybrid library-access modes, the SQLite-lock problem (writes require Zotero.app closed), the canonical DOI-ingestion workflow, annotation extraction, and the **`zotero-cli config` footgun that prints OPENAI_API_KEY and other secrets verbatim**. Use this skill even if the user does not name "Zotero" by name — if you see a `zotero.sqlite` next to a `storage/` directory of hash-named subfolders, that is a Zotero data directory and this skill applies.
---

# Zotero CLI

Zotero is a desktop reference manager (Mac/Win/Linux) with a SQLite-backed library at `~/Zotero/zotero.sqlite` and PDF attachments under `~/Zotero/storage/<8-char-hash>/`. The `zotero-mcp-server` PyPI package (upstream: 54yyyu/zotero-mcp) ships two binaries:

- **`zotero-cli`** — standalone library access, no MCP server, no AI assistant needed. The right tool for Claude Code via Bash.
- **`zotero-mcp`** — MCP server for Claude Desktop / Cursor / ChatGPT. Same library, heavier integration.

For Claude Code, prefer **`zotero-cli` via Bash** — every MCP tool schema costs context tokens whether or not it's used, but a CLI binary only costs tokens when actually invoked.

## Library access modes

Zotero MCP supports three modes, controlled by env vars:

| Mode | Reads | Writes | Setup |
|---|---|---|---|
| **Local** (`ZOTERO_LOCAL=true`) | direct from `zotero.sqlite` | direct to `zotero.sqlite` — **requires Zotero.app closed** | no API key |
| **Web** (`ZOTERO_API_KEY` + `ZOTERO_LIBRARY_ID`) | Zotero web API | Zotero web API | API key from zotero.org/settings/keys |
| **Hybrid** (both set) | local reads (fast) | web writes (no GUI lock) | both |

**The SQLite lock is the single most common failure mode.** Zotero.app holds a write lock on `zotero.sqlite` while running. Local-mode writes will error with `database is locked`. Either:

1. Quit Zotero.app before writing (simplest for one-off).
2. Switch to **hybrid mode**: keep `ZOTERO_LOCAL=true` for reads, add `ZOTERO_API_KEY`/`ZOTERO_LIBRARY_ID` so writes go via the web API. This is the durable answer if you both use Zotero.app and want CLI writes.

Local **reads** are safe while Zotero.app is open — SQLite supports concurrent readers.

Check current mode with `zotero-cli library list` (shows count of items) — but **do NOT run `zotero-cli config`** until you read the next section.

## CRITICAL FOOTGUN: `zotero-cli config` leaks `OPENAI_API_KEY` and `GOOGLE_API_KEY`

`zotero-cli config` prints the recognized env vars. **`ZOTERO_API_KEY` is obfuscated to `<first4>****` by default** — `--show-secrets` is required to see it in full. But `OPENAI_API_KEY` and `GOOGLE_API_KEY` are **not** in the obfuscation list — they print verbatim regardless of flags. These end up in shell scrollback, terminal logs, and (worst) any LLM session transcript.

**Never run `zotero-cli config` in a Claude Code session.** Use targeted checks instead:

```bash
# Confirm local mode without exposing secrets
echo "${ZOTERO_LOCAL:-unset}"

# Confirm library is reachable
zotero-cli library list
```

If you must inspect config, do it in a local terminal with no recording, and redact before sharing.

## The five subcommands that matter

`zotero-cli` has many subcommands; in practice you use these five:

| Subcommand | Aliases | Use when |
|---|---|---|
| `search` | `s` | Find items by title/author/content/tag/citation key |
| `get` | `g` | Pull metadata, recent items, collections, or attachments by key |
| `annotations` | `ann` | Extract/list PDF highlights and comments |
| `add` | — | Ingest by DOI, arXiv URL, web URL, or local file |
| `edit` | — | Update fields on an existing item |

The rest (`notes`, `collections`, `tags`, `duplicates`, `db`, `library`, `outline`) are useful when their need comes up — not daily tools.

## Search

```bash
# Default mode: title + author + content
zotero-cli search "phenomenology consciousness"

# By tag (comma-separated, AND logic)
zotero-cli search --mode tag "philosophy,husserl"

# Semantic / vector search (requires [semantic] extra + indexed DB)
zotero-cli search --mode semantic "the hard problem of consciousness"

# By Better BibTeX citation key (if BBT installed in Zotero)
zotero-cli search --mode citekey heidegger2010being

# Filter results
zotero-cli search --limit 5 "Husserl"
zotero-cli search --collection "PhD reading" "..."
```

Output is markdown with item key, type, date, authors, abstract preview, tags. The **item key** (e.g. `YHRALHP7`) is the local DB identifier — use it for subsequent `get`, `edit`, `annotations` calls.

Semantic search requires:

```bash
uv tool install 'zotero-mcp-server[semantic]'  # adds embedding deps
zotero-cli db update                           # one-time index (~10 min for 3k items)
zotero-cli db status                           # check sync state
```

## Get item details

```bash
# Full metadata
zotero-cli get metadata YHRALHP7

# As BibTeX (dedicated subcommand)
zotero-cli get bibtex YHRALHP7

# Recent additions
zotero-cli get recent --limit 20

# All collections (tree view)
zotero-cli get collections
```

## Adding items

`zotero-cli add` handles four kinds of input:

```bash
# DOI — fetches canonical metadata, attempts open-access PDF cascade
# (Unpaywall → arXiv → Semantic Scholar → PMC)
zotero-cli add doi 10.1007/s10670-019-00220-4 --collections "Inbox"

# arXiv ID or URL — abstract + PDF
zotero-cli add url https://arxiv.org/abs/2103.05456

# Generic web page — uses Zotero translators
zotero-cli add url "https://example.com/some-paper"

# Local file (PDF/EPUB) — note --filepath flag and --collections (plural)
zotero-cli add file --filepath /tmp/paper.pdf --collections "Inbox"
```

DOI ingestion is the canonical workflow — Zotero fetches publisher metadata, then runs the PDF cascade, then deduplicates against existing items by DOI. If a duplicate is found, it skips (won't double-add).

**Pass `--collections <name>`** (plural — not `--collection`) to file the new item directly. Without it, items land in "My Library / no collection" and have to be filed manually in the GUI. To skip the PDF download for metadata-only ingestion: `--attach-mode linked_url`.

## Annotations

PDF highlights and comments live in Zotero as child items of the parent paper. Extract them:

```bash
# All annotations for one paper (output is markdown by default)
zotero-cli annotations list --item-key YHRALHP7

# Include direct PDF extraction (slower, but catches annotations Zotero hasn't indexed yet)
zotero-cli annotations list --item-key YHRALHP7 --pdf-extraction

# Limit
zotero-cli annotations list --item-key YHRALHP7 --limit 50
```

The CLI scopes annotations by `--item-key` — there's no collection-scoped variant. For a whole collection, iterate items first (`zotero-cli get collection-items <COLL_KEY>`) and then call `annotations list` per item.

Each annotation includes page number, text content, color, and any comment. **PDF annotations are only available if Zotero's PDF reader (or a sync) has indexed the file** — if you imported via DOI but never opened the PDF, the annotations array will be empty. `--pdf-extraction` forces a fresh extraction directly from the PDF, which works around stale Zotero indexes.

## Edit fields

```bash
# Set a field — every editable field has its own named flag
zotero-cli edit YHRALHP7 --title "Corrected Title"

# Add/remove tags
zotero-cli edit YHRALHP7 --add-tags "reviewed,important" --remove-tags "todo"

# Set multiple at once — chain the per-field flags
zotero-cli edit YHRALHP7 --publisher "MIT Press" --date "2010" --doi "10.7551/mitpress/example"
```

Available edit flags include `--title`, `--creators` (JSON array), `--date`, `--publication-title`, `--abstract`, `--tags` (replace all), `--add-tags`, `--remove-tags`, `--collections`, `--doi`, `--url`, `--volume`, `--issue`, `--pages`, `--publisher`, `--isbn`, `--issn`, `--language`, `--short-title`, `--edition`, `--book-title`, `--extra`. There is no generic `--field key=value` form — each editable field has its own flag.

**Edits go through the configured mode.** Local mode requires Zotero.app closed. Web/hybrid mode writes through the API and works with the GUI running.

## Duplicates

Zotero's GUI duplicate detection is shallow (matches title + first author + year). `zotero-cli duplicates` exposes a deeper matcher:

```bash
# List duplicate candidates
zotero-cli duplicates find

# Merge — explicit named flags required, no positional args
zotero-cli duplicates merge --keeper-key ABC12345 --duplicate-keys XYZ98765

# Preview the merge first
zotero-cli duplicates merge --keeper-key ABC12345 --duplicate-keys XYZ98765 --dry-run

# Multiple duplicates collapse into one keeper — comma-separated
zotero-cli duplicates merge --keeper-key ABC12345 --duplicate-keys XYZ98765,DEF11111
```

Always run `find` before `merge`. Merge is destructive (the second item is removed). Make a backup first:

```bash
cp -R ~/Zotero "/tmp/zotero-backup-$(date +%Y-%m-%d-%H%M%S)"
```

## Footguns

1. **`zotero-cli config` exposes secrets** — see the section above. Never run it in a recorded session.
2. **SQLite lock** — local-mode writes fail when Zotero.app is running. Either quit Zotero or switch to hybrid mode.
3. **Item keys are case-sensitive** — `YHRALHP7` and `yhralhp7` are different. Copy them verbatim.
4. **DOI normalization** — Zotero stores DOIs lowercase. Search by DOI should also use lowercase or the canonical form returned by `doi.org`.
5. **Better BibTeX is a separate Zotero plugin** — without it, `search --mode citekey` silently returns nothing. Install BBT in Zotero first if you rely on stable citation keys.
6. **Semantic search needs `[semantic]` extra + index** — first attempts return "no semantic DB found" until `zotero-cli db update` completes.
7. **PDF cascade can take 30+ seconds** — `add doi` will try multiple sources for the OA PDF. Use `--attach-mode linked_url` for metadata-only ingestion.
8. **`--collection` vs `--collections`** — search uses singular `--collection`, while `add doi` / `add file` / `edit` use plural `--collections`. Easy to swap by accident.
9. **Edit has no generic `--field` flag** — every editable attribute has its own named flag (`--title`, `--publisher`, etc.). There's no `--field key=value` form.
10. **`duplicates merge` requires named flags** — `--keeper-key` and `--duplicate-keys`. Positional args (e.g. `duplicates merge K1 K2`) will error.

## When to use what — quick decision tree

- **"What's in my library on topic X?"** → `search` (default mode for general queries, `--mode semantic` for concept-level)
- **"Get the metadata / citation for paper Y"** → `get metadata <KEY>` or `get bibtex <KEY>`
- **"Add this paper I just read"** → `add doi <DOI> --collections <NAME>`
- **"Extract my highlights from paper Y"** → `annotations list --item-key <KEY>` (add `--pdf-extraction` if Zotero hasn't indexed yet)
- **"Fix this paper's metadata"** → `edit <KEY> --<field-name> "<value>"` (per-field flag, see Edit fields)
- **"Find duplicates"** → `duplicates find` then `duplicates merge --keeper-key <K> --duplicate-keys <K1,K2,...>`
- **"What collections do I have?"** → `get collections`
- **"Recently added papers"** → `get recent --limit N`

## Library location and direct SQLite

If `zotero-cli` is misbehaving, you can read `zotero.sqlite` directly with `sqlite3 -readonly` — useful for sanity checks and one-off queries Zotero's schema doesn't expose well.

```bash
# Item count
sqlite3 -readonly ~/Zotero/zotero.sqlite "SELECT COUNT(*) FROM items WHERE itemTypeID NOT IN (SELECT itemTypeID FROM itemTypes WHERE typeName IN ('attachment', 'note', 'annotation'));"

# Recent additions (item key → title)
# Join on items.itemID (integer PK), NOT items.key (the 8-char string).
sqlite3 -readonly ~/Zotero/zotero.sqlite \
  "SELECT i.key, idv.value
   FROM items i
   JOIN itemData id ON id.itemID = i.itemID
   JOIN itemDataValues idv ON idv.valueID = id.valueID
   JOIN fields f ON f.fieldID = id.fieldID AND f.fieldName = 'title'
   ORDER BY i.dateAdded DESC LIMIT 10;"
```

The schema is documented at <https://www.zotero.org/support/dev/client_coding/direct_sqlite_database_access>. **Read-only only** — writing to `zotero.sqlite` while Zotero is running corrupts the journal.

## Related plugins worth knowing about

- **Better BibTeX (BBT)** — install inside Zotero. Adds stable citation keys, auto-export to .bib files, JabRef-compatible field mappings. Without BBT, `zotero-cli search --mode citekey <key>` returns nothing.
- **ZotPilot** — separate MCP server focused on semantic search and literature-review drafting from your local library. Complementary to zotero-mcp-server for research-heavy workflows.
- **Scite** — `zotero-mcp-server[scite]` extra adds citation tallies (support/contrast/mention counts) and retraction alerts. No Scite account required (uses public API).
