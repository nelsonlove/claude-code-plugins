# Apple Notes Plugin Design

> **Date:** 2026-03-08
> **Status:** Approved

## Goal

Full Apple Notes integration for Claude Code: day-to-day note operations (search, read, create) plus a guided triage/cleanup workflow to work through the 308-note capture purgatory identified in the 06.13 audit.

## Architecture

Plugin at `~/repos/claude-code-plugins/plugins/apple-notes/` with four components:

### MCP Server (`server.py`)

Python server running inside the apple-notes-cli venv (`~/repos/apple-notes-cli/.venv`). Imports the `apple_notes` library directly — no CLI shelling, structured JSON returns natively.

**Tools:**

| Tool | Purpose | Params |
|------|---------|--------|
| `list_notes` | List notes with metadata | `folder?`, `limit?`, `sort_by?` (modified/created), `order?` (asc/desc) |
| `get_note` | Get full note content | `title?`, `id?` |
| `list_folders` | List folders with note counts | — |
| `create_note` | Create a note (Markdown body) | `title`, `body`, `folder?` |
| `search_notes` | Search (text/semantic/hybrid) | `query`, `mode?`, `limit?` |
| `export_notes` | Export to Markdown with frontmatter | `title?`, `id?`, `folder?`, `all?`, `output` |
| `delete_note` | Move note to Recently Deleted | `title?`, `id?` |
| `move_note` | Move note to a different folder | `title?`, `id?`, `folder` |

### Skill: note-operations

Triggers on: "find a note", "create a note", "what's in my Notes", "search Notes", general Apple Notes usage.

Teaches Claude the MCP tools and when to use each. Lightweight reference skill.

### Skill: note-triage

The batch cleanup workflow:

1. **Scan** — `list_notes` with folder filter, sorted by oldest first
2. **Analyze** — Claude reads note content in batches of ~20, proposes actions:
   - **Delete** — empty, stub, near-empty, duplicate
   - **Archive** — stale but valuable; export to Markdown, file into JD tree via `jd` CLI
   - **Keep** — active/ephemeral; optionally re-folder
3. **Present** — show the batch as a table with proposed actions
4. **Execute** — on user approval, carry out the actions; report failures at the end

Integrates with `jd-workflows` plugin for the archive-to-JD filing step.

### Command: `/notes-triage`

Entry point to start a triage session. Optional folder argument; defaults to worst offenders (01 Inbox, Notes default folder).

## Upstream Changes (apple-notes-cli)

Two additions needed in the library:

### db.py — sort parameters

Add `sort_by` and `order` params to `get_all_notes()`:

```python
def get_all_notes(self, folder=None, limit=None, sort_by="modified", order="desc"):
```

`sort_by`: "modified" (zmodificationdate1) or "created" (zcreationdate1)
`order`: "asc" or "desc"

### jxa.py — delete and move

```python
def delete_note(title_or_pk): ...  # JXA: move note to trash
def move_note(title_or_pk, folder): ...  # JXA: move note to folder
```

## Data Flow

**Day-to-day:**
```
User → note-operations skill triggers → MCP tools →
apple_notes library (SQLite read / JXA write) →
structured JSON → Claude presents results
```

**Triage:**
```
/notes-triage [folder] → note-triage skill →
list_notes (oldest first) + get_note (batch of ~20) →
Claude proposes action table → user approves/modifies →
delete: JXA trash | archive: export + jd file | keep: JXA move
```

## Error Handling

- **SQLite locked:** Read-only access; retry or ask user to close Notes briefly
- **Semantic search unavailable:** Graceful fallback to text search with a note
- **JXA write failures:** Collect and report at end of batch, don't stop
- **Delete safety:** JXA moves to Recently Deleted (30-day recovery), not permanent

## Plugin Structure

```
apple-notes/
├── .claude-plugin/
│   └── plugin.json
├── .mcp.json
├── server.py
├── commands/
│   └── notes-triage.md
├── skills/
│   ├── note-operations/
│   │   └── SKILL.md
│   └── note-triage/
│       └── SKILL.md
└── TODO.md
```
