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

## CRITICAL FOOTGUN: `zotero-cli config` dumps secrets

`zotero-cli config` (or `zotero-mcp` equivalent) prints **every recognized env var verbatim** — including `OPENAI_API_KEY` and `ZOTERO_API_KEY`. These end up in the shell scrollback, terminal logs, and (worst) any LLM session transcript.

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
zotero-cli get bbt-key heidegger2010being

# Filter results
zotero-cli search --limit 5 --type book "Husserl"
zotero-cli search --collection "PhD reading" "..."
```

Output is markdown with item key, type, date, authors, abstract preview, tags. The **item key** (e.g. `YHRALHP7`) is the local DB identifier — use it for subsequent `get`, `edit`, `annotations` calls.

Semantic search requires:

```bash
uv tool install 'zotero-mcp-server[semantic]'  # adds embedding deps
zotero-cli db build                            # one-time index (~10 min for 3k items)
zotero-cli db status                           # check sync state
```

## Get item details

```bash
# Full metadata
zotero-cli get metadata YHRALHP7

# As BibTeX
zotero-cli get metadata YHRALHP7 --format bibtex

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
zotero-cli add doi 10.1007/s10670-019-00220-4

# arXiv ID or URL — abstract + PDF
zotero-cli add url https://arxiv.org/abs/2103.05456

# Generic web page — uses Zotero translators
zotero-cli add url "https://example.com/some-paper"

# Local file (PDF/EPUB)
zotero-cli add file /tmp/paper.pdf --collection "Inbox"
```

DOI ingestion is the canonical workflow — Zotero fetches publisher metadata, then runs the PDF cascade, then deduplicates against existing items by DOI. If a duplicate is found, it skips (won't double-add).

**Pass `--collection <name>`** to file the new item directly. Without it, items land in "My Library / no collection" and have to be filed manually in the GUI.

## Annotations

PDF highlights and comments live in Zotero as child items of the parent paper. Extract them:

```bash
# All annotations for one paper
zotero-cli annotations list --item-key YHRALHP7

# All annotations across a collection
zotero-cli annotations list --collection "Dissertation core"

# Export as Markdown (good for literature review notes)
zotero-cli annotations list --item-key YHRALHP7 --format markdown
```

Each annotation includes page number, text content, color, and any comment. **PDF annotations are only available if Zotero's PDF reader (or a sync) has indexed the file** — if you imported via DOI but never opened the PDF, the annotations array will be empty.

## Edit fields

```bash
# Set a field
zotero-cli edit YHRALHP7 --title "Corrected Title"

# Add/remove tags
zotero-cli edit YHRALHP7 --add-tags "reviewed,important" --remove-tags "todo"

# Set multiple at once
zotero-cli edit YHRALHP7 --field "publisher=MIT Press" --field "place=Cambridge, MA"
```

**Edits go through the configured mode.** Local mode requires Zotero.app closed. Web/hybrid mode writes through the API and works with the GUI running.

## Duplicates

Zotero's GUI duplicate detection is shallow (matches title + first author + year). `zotero-cli duplicates` exposes a deeper matcher:

```bash
# Dry-run, show candidates
zotero-cli duplicates find

# Merge a specific pair (keeps first item's metadata, moves children)
zotero-cli duplicates merge ABC12345 XYZ98765
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
5. **Better BibTeX is a separate Zotero plugin** — without it, `bbt-key` lookups silently return nothing. Install BBT in Zotero first if you rely on stable citation keys.
6. **Semantic search needs `[semantic]` extra + index** — first attempts return "no semantic DB found" until `zotero-cli db build` completes.
7. **PDF cascade can take 30+ seconds** — `add doi` will try multiple sources for the OA PDF. Set `--no-pdf` for metadata-only ingestion.
8. **Collections are nested** — `get collections` shows a tree; `--collection` flags accept the full path (`Parent/Child`) or the leaf name if unambiguous.

## When to use what — quick decision tree

- **"What's in my library on topic X?"** → `search` (default mode for general queries, `--mode semantic` for concept-level)
- **"Get the metadata / citation for paper Y"** → `get metadata <KEY>` (or `--format bibtex`)
- **"Add this paper I just read"** → `add doi <DOI>` (with `--collection`)
- **"Extract my highlights from paper Y"** → `annotations list --item-key <KEY> --format markdown`
- **"Fix this paper's metadata"** → `edit <KEY> --field key=value`
- **"Find duplicates"** → `duplicates find` (then `merge` on specific pairs)
- **"What collections do I have?"** → `get collections`
- **"Recently added papers"** → `get recent --limit N`

## Library location and direct SQLite

If `zotero-cli` is misbehaving, you can read `zotero.sqlite` directly with `sqlite3 -readonly` — useful for sanity checks and one-off queries Zotero's schema doesn't expose well.

```bash
# Item count
sqlite3 -readonly ~/Zotero/zotero.sqlite "SELECT COUNT(*) FROM items WHERE itemTypeID NOT IN (SELECT itemTypeID FROM itemTypes WHERE typeName IN ('attachment', 'note', 'annotation'));"

# Recent additions (item key → title)
sqlite3 -readonly ~/Zotero/zotero.sqlite \
  "SELECT i.key, idv.value FROM items i
   JOIN itemDataValues idv ON idv.valueID = (
     SELECT valueID FROM itemData WHERE itemID = i.key AND fieldID = (
       SELECT fieldID FROM fields WHERE fieldName = 'title'
     )
   )
   ORDER BY i.dateAdded DESC LIMIT 10;"
```

The schema is documented at <https://www.zotero.org/support/dev/client_coding/direct_sqlite_database_access>. **Read-only only** — writing to `zotero.sqlite` while Zotero is running corrupts the journal.

## Related plugins worth knowing about

- **Better BibTeX (BBT)** — install inside Zotero. Adds stable citation keys, auto-export to .bib files, JabRef-compatible field mappings. Without BBT, `zotero-cli get bbt-key` returns nothing.
- **ZotPilot** — separate MCP server focused on semantic search and literature-review drafting from your local library. Complementary to zotero-mcp-server for research-heavy workflows.
- **Scite** — `zotero-mcp-server[scite]` extra adds citation tallies (support/contrast/mention counts) and retraction alerts. No Scite account required (uses public API).
