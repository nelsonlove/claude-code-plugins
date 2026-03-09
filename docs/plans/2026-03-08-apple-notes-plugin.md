# Apple Notes Plugin Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Claude Code plugin that provides full Apple Notes integration — MCP server wrapping the apple-notes-cli library, day-to-day operation skills, and a guided triage/cleanup workflow.

**Architecture:** MCP server in Python imports `apple_notes` library directly from the CLI repo's venv. Plugin provides two skills (note-operations, note-triage) and one command (/notes-triage). Upstream library gets sort params and delete/move JXA operations.

**Tech Stack:** Python 3.12+, JSON-RPC stdio MCP protocol, apple-notes-cli library (SQLite + protobuf + JXA + LanceDB)

**Design doc:** `docs/plans/2026-03-08-apple-notes-plugin-design.md`

---

### Task 1: Add sort params to library

**Files:**
- Modify: `~/repos/apple-notes-cli/src/apple_notes/db.py:42-76` (get_all_notes)

**Step 1: Add sort_by and order parameters**

In `db.py`, change `get_all_notes` signature and ORDER BY clause:

```python
def get_all_notes(self, folder: str | None = None, limit: int | None = None,
                  sort_by: str = "modified", order: str = "desc") -> list[dict[str, Any]]:
    """List notes with metadata (no content blob).

    Args:
        folder: Filter by folder name.
        limit: Max notes to return.
        sort_by: "modified" or "created".
        order: "asc" or "desc".
    """
    sort_col = "note.zcreationdate1" if sort_by == "created" else "note.zmodificationdate1"
    order_dir = "ASC" if order.lower() == "asc" else "DESC"

    sql = f"""
    SELECT
        'x-coredata://' || zmd.z_uuid || '/ICNote/p' || note.z_pk AS id,
        note.z_pk AS pk,
        note.ztitle1 AS title,
        folder.ztitle2 AS folder,
        datetime(note.zmodificationdate1 + {_COREDATA_EPOCH}, 'unixepoch') AS modifiedAt,
        datetime(note.zcreationdate1 + {_COREDATA_EPOCH}, 'unixepoch') AS createdAt,
        note.zsnippet AS snippet,
        acc.zname AS account,
        note.zidentifier AS uuid,
        (note.zispasswordprotected = 1) AS locked,
        (note.zispinned = 1) AS pinned,
        (note.zhaschecklist = 1) AS checklist
    FROM ziccloudsyncingobject AS note
    INNER JOIN ziccloudsyncingobject AS folder ON note.zfolder = folder.z_pk
    LEFT JOIN ziccloudsyncingobject AS acc ON note.zaccount4 = acc.z_pk
    LEFT JOIN z_metadata AS zmd ON 1=1
    WHERE
        note.ztitle1 IS NOT NULL
        AND note.zmodificationdate1 IS NOT NULL
        AND note.z_pk IS NOT NULL
        AND note.zmarkedfordeletion != 1
        AND folder.zmarkedfordeletion != 1
        {"AND folder.ztitle2 = ?" if folder else ""}
    ORDER BY {sort_col} {order_dir}
    {"LIMIT ?" if limit else ""}
    """
    params: tuple = ()
    if folder:
        params += (folder,)
    if limit:
        params += (limit,)
    return self._query(sql, params)
```

Note: also adds `createdAt` to the SELECT which was missing from the original.

**Step 2: Verify it works**

Run: `cd ~/repos/apple-notes-cli && .venv/bin/python -c "from apple_notes.db import NotesDB; db = NotesDB(); print(db.get_all_notes(limit=3, order='asc')[0]['title'])"`

Expected: oldest note title printed.

**Step 3: Commit**

```bash
cd ~/repos/apple-notes-cli
git add src/apple_notes/db.py
git commit -m "feat: add sort_by and order params to get_all_notes"
```

---

### Task 2: Add delete and move to JXA module

**Files:**
- Modify: `~/repos/apple-notes-cli/src/apple_notes/jxa.py`

**Step 1: Add delete_note function**

Append to `jxa.py`:

```python
def delete_note(title: str) -> None:
    """Move a note to Recently Deleted (trash) by title.

    Args:
        title: Exact note title.
    """
    safe_title = json.dumps(title)
    script = f"""
    const app = Application('Notes');
    const matches = app.notes.whose({{name: {safe_title}}})();
    if (matches.length === 0) throw new Error('Note not found: ' + {safe_title});
    app.delete(matches[0]);
    """
    _run_jxa(script)


def move_note(title: str, folder_name: str) -> None:
    """Move a note to a different folder by title.

    Args:
        title: Exact note title.
        folder_name: Target folder name.
    """
    safe_title = json.dumps(title)
    safe_folder = json.dumps(folder_name)
    script = f"""
    const app = Application('Notes');
    const matches = app.notes.whose({{name: {safe_title}}})();
    if (matches.length === 0) throw new Error('Note not found: ' + {safe_title});
    const folders = app.folders.whose({{name: {safe_folder}}})();
    if (folders.length === 0) throw new Error('Folder not found: ' + {safe_folder});
    app.move(matches[0], {{to: folders[0]}});
    """
    _run_jxa(script)
```

**Step 2: Verify delete works (create a throwaway note first)**

```bash
cd ~/repos/apple-notes-cli
.venv/bin/python -c "
from apple_notes.jxa import create_note, delete_note
create_note('__test_delete_me__', '<p>test</p>')
print('created')
delete_note('__test_delete_me__')
print('deleted')
"
```

Expected: "created" then "deleted" printed. Note appears in Recently Deleted in Notes.app.

**Step 3: Verify move works**

```bash
.venv/bin/python -c "
from apple_notes.jxa import create_note, move_note
create_note('__test_move_me__', '<p>test</p>')
move_note('__test_move_me__', 'Notes')
print('moved')
"
```

Then manually verify the note is in the "Notes" folder and clean it up.

**Step 4: Commit**

```bash
cd ~/repos/apple-notes-cli
git add src/apple_notes/jxa.py
git commit -m "feat: add delete_note and move_note JXA operations"
```

---

### Task 3: Scaffold plugin structure

**Files:**
- Create: `~/repos/claude-code-plugins/plugins/apple-notes/.claude-plugin/plugin.json`
- Create: `~/repos/claude-code-plugins/plugins/apple-notes/TODO.md`

**Step 1: Create plugin manifest**

```json
{
  "name": "apple-notes",
  "version": "0.1.0",
  "description": "Apple Notes integration — read, create, search, and triage notes via MCP",
  "author": {
    "name": "Nelson Love"
  },
  "repository": "https://github.com/nelsonlove/claude-code-plugins",
  "license": "MIT",
  "keywords": ["apple-notes", "notes", "triage", "mcp"]
}
```

**Step 2: Create TODO.md**

```markdown
# Apple Notes Plugin TODO

## Done
- [x] Design doc

## In Progress
- [ ] MCP server (server.py)
- [ ] Skills (note-operations, note-triage)
- [ ] Command (/notes-triage)

## Future
- [ ] Batch delete MCP tool (multiple notes at once)
- [ ] Note update/append tool
- [ ] Folder create/delete tools
- [ ] Auto-rebuild semantic index on stale detection
```

**Step 3: Add to marketplace.json**

Add entry to `~/repos/claude-code-plugins/.claude-plugin/marketplace.json` plugins array:

```json
{
  "name": "apple-notes",
  "source": "./plugins/apple-notes",
  "description": "Apple Notes integration — read, create, search, and triage notes via MCP.",
  "version": "0.1.0",
  "author": {
    "name": "Nelson Love"
  }
}
```

**Step 4: Commit**

```bash
cd ~/repos/claude-code-plugins
git add plugins/apple-notes/.claude-plugin/plugin.json plugins/apple-notes/TODO.md .claude-plugin/marketplace.json
git commit -m "feat(apple-notes): scaffold plugin structure and marketplace entry"
```

---

### Task 4: Build MCP server

**Files:**
- Create: `~/repos/claude-code-plugins/plugins/apple-notes/server.py`
- Create: `~/repos/claude-code-plugins/plugins/apple-notes/.mcp.json`

**Step 1: Create .mcp.json**

```json
{
  "apple-notes": {
    "type": "stdio",
    "command": "/Users/nelson/repos/apple-notes-cli/.venv/bin/python3",
    "args": ["${CLAUDE_PLUGIN_ROOT}/server.py"]
  }
}
```

Note: uses the CLI venv's Python directly so all `apple_notes` imports resolve. No `python3` from PATH — that wouldn't have the deps.

**Step 2: Create server.py**

Write a JSON-RPC stdio MCP server following the session-name pattern. Tools:

- `list_notes(folder?, limit?, sort_by?, order?)` → calls `db.get_all_notes()`
- `get_note(title?, id?)` → calls `db.get_note_by_title()` or `db.get_note_by_pk()`, decodes content
- `list_folders()` → calls `db.get_folders()`
- `create_note(title, body, folder?)` → calls `jxa.create_note()` after markdown→html conversion
- `search_notes(query, mode?, limit?)` → calls `db.search_notes()` or `search.SearchIndex` methods
- `export_note(title?, id?)` → decodes and returns markdown with frontmatter
- `delete_note(title)` → calls `jxa.delete_note()`
- `move_note(title, folder)` → calls `jxa.move_note()`

The server must add the apple-notes-cli `src/` to `sys.path` so imports work:

```python
import sys
sys.path.insert(0, "/Users/nelson/repos/apple-notes-cli/src")
```

Full server.py:

```python
#!/usr/bin/env python3
"""Apple Notes MCP server — wraps apple_notes library over JSON-RPC stdio."""

import json
import sys
import traceback

# Add apple-notes-cli library to path
sys.path.insert(0, "/Users/nelson/repos/apple-notes-cli/src")

from apple_notes.db import NotesDB
from apple_notes.decode import decode_note_content, decode_note_to_markdown
from apple_notes.convert import markdown_to_html
from apple_notes.jxa import create_note, delete_note, move_note


def _get_db():
    return NotesDB()


TOOLS = [
    {
        "name": "list_notes",
        "description": "List notes with metadata. Returns title, folder, dates, snippet.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "folder": {"type": "string", "description": "Filter by folder name"},
                "limit": {"type": "integer", "description": "Max notes to return"},
                "sort_by": {"type": "string", "enum": ["modified", "created"],
                            "description": "Sort field (default: modified)"},
                "order": {"type": "string", "enum": ["asc", "desc"],
                          "description": "Sort direction (default: desc)"},
            },
        },
    },
    {
        "name": "get_note",
        "description": "Get full note content by title or primary key ID. Returns decoded text content.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Note title (exact match)"},
                "id": {"type": "integer", "description": "Note primary key"},
            },
        },
    },
    {
        "name": "list_folders",
        "description": "List all Apple Notes folders with note counts.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "create_note",
        "description": "Create a new note. Body is Markdown, converted to HTML automatically.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Note title"},
                "body": {"type": "string", "description": "Note body in Markdown"},
            },
            "required": ["title", "body"],
        },
    },
    {
        "name": "search_notes",
        "description": "Search notes. Modes: text (LIKE match), semantic (vector similarity), hybrid (RRF fusion). Falls back to text if semantic index unavailable.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "mode": {"type": "string", "enum": ["text", "semantic", "hybrid"],
                          "description": "Search mode (default: hybrid)"},
                "limit": {"type": "integer", "description": "Max results (default: 20)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "export_note",
        "description": "Export a note as Markdown with YAML frontmatter. Returns the Markdown string.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Note title"},
                "id": {"type": "integer", "description": "Note primary key"},
            },
        },
    },
    {
        "name": "delete_note",
        "description": "Move a note to Recently Deleted (trash). Recoverable for 30 days.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Exact note title to delete"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "move_note",
        "description": "Move a note to a different folder.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Exact note title"},
                "folder": {"type": "string", "description": "Target folder name"},
            },
            "required": ["title", "folder"],
        },
    },
]


def send(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def _format_frontmatter(note: dict) -> str:
    lines = ['---']
    lines.append(f'title: "{note.get("title", "")}"')
    lines.append(f'folder: "{note.get("folder", "")}"')
    if note.get("createdAt"):
        lines.append(f'created: "{note["createdAt"]}"')
    if note.get("modifiedAt"):
        lines.append(f'modified: "{note["modifiedAt"]}"')
    lines.append('---')
    return '\n'.join(lines)


def handle_tool(name, args):
    db = _get_db()

    if name == "list_notes":
        notes = db.get_all_notes(
            folder=args.get("folder"),
            limit=args.get("limit"),
            sort_by=args.get("sort_by", "modified"),
            order=args.get("order", "desc"),
        )
        # Strip content blobs, keep metadata
        return json.dumps(notes, indent=2)

    elif name == "get_note":
        if args.get("id"):
            note = db.get_note_by_pk(args["id"])
        elif args.get("title"):
            note = db.get_note_by_title(args["title"])
        else:
            return "Error: provide title or id"
        if not note:
            return "Note not found."
        text = decode_note_content(note.get("content"))
        result = {k: v for k, v in note.items() if k != "content"}
        result["content"] = text
        return json.dumps(result, indent=2)

    elif name == "list_folders":
        folders = db.get_folders()
        return json.dumps(folders, indent=2)

    elif name == "create_note":
        html = markdown_to_html(args["body"])
        create_note(args["title"], html)
        return f"Created note: {args['title']}"

    elif name == "search_notes":
        query = args["query"]
        mode = args.get("mode", "hybrid")
        limit = args.get("limit", 20)

        if mode == "text":
            results = db.search_notes(query)[:limit]
            for r in results:
                if "content" in r:
                    r["content"] = decode_note_content(r["content"])[:200]
            return json.dumps(results, indent=2)

        # semantic or hybrid — try, fall back to text
        try:
            from apple_notes.search import SearchIndex
            idx = SearchIndex()
            if mode == "semantic":
                results = idx.vector_search(query, limit=limit)
            else:
                results = idx.hybrid_search(query, limit=limit)
            return json.dumps(results, indent=2)
        except Exception:
            results = db.search_notes(query)[:limit]
            for r in results:
                if "content" in r:
                    r["content"] = decode_note_content(r["content"])[:200]
            return "(Semantic search unavailable, using text fallback)\n" + json.dumps(results, indent=2)

    elif name == "export_note":
        if args.get("id"):
            note = db.get_note_by_pk(args["id"])
        elif args.get("title"):
            note = db.get_note_by_title(args["title"])
        else:
            return "Error: provide title or id"
        if not note:
            return "Note not found."
        md = decode_note_to_markdown(note.get("content"), skip_title=True)
        fm = _format_frontmatter(note)
        return f"{fm}\n\n{md}\n" if md else f"{fm}\n"

    elif name == "delete_note":
        delete_note(args["title"])
        return f"Deleted (moved to trash): {args['title']}"

    elif name == "move_note":
        move_note(args["title"], args["folder"])
        return f"Moved '{args['title']}' to folder '{args['folder']}'"

    return f"Unknown tool: {name}"


def handle(msg):
    method = msg.get("method", "")
    msg_id = msg.get("id")

    if method == "initialize":
        send({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "apple-notes", "version": "0.1.0"},
            },
        })

    elif method == "tools/list":
        send({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"tools": TOOLS},
        })

    elif method == "tools/call":
        params = msg.get("params", {})
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        try:
            result_text = handle_tool(tool_name, tool_args)
            send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": result_text}]
                },
            })
        except Exception as e:
            send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": f"Error: {e}"}],
                    "isError": True,
                },
            })

    # Notifications (no id) — no response needed


for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        handle(json.loads(line))
    except Exception:
        pass
```

**Step 3: Smoke test the server**

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | /Users/nelson/repos/apple-notes-cli/.venv/bin/python3 ~/repos/claude-code-plugins/plugins/apple-notes/server.py
```

Expected: JSON response with protocolVersion and serverInfo.

**Step 4: Commit**

```bash
cd ~/repos/claude-code-plugins
git add plugins/apple-notes/server.py plugins/apple-notes/.mcp.json
git commit -m "feat(apple-notes): add MCP server wrapping apple-notes-cli library"
```

---

### Task 5: Create note-operations skill

**Files:**
- Create: `~/repos/claude-code-plugins/plugins/apple-notes/skills/note-operations/SKILL.md`

**Step 1: Write skill**

```markdown
---
name: note-operations
description: Use when the user asks to find, read, create, or search their Apple Notes. Also use when they mention "notes", "Apple Notes", or ask about note content, folders, or organization.
---

# Apple Notes Operations

## Available MCP Tools

### Reading
- **list_notes** — List notes with metadata. Params: `folder`, `limit`, `sort_by` (modified/created), `order` (asc/desc)
- **get_note** — Get full note content. Params: `title` (exact match) or `id` (primary key)
- **list_folders** — List all folders with note counts
- **search_notes** — Search by text, semantic similarity, or hybrid. Params: `query`, `mode` (text/semantic/hybrid), `limit`

### Writing
- **create_note** — Create a note with Markdown body. Params: `title`, `body`
- **move_note** — Move to a different folder. Params: `title`, `folder`
- **delete_note** — Move to Recently Deleted (30-day recovery). Params: `title`

### Export
- **export_note** — Return note as Markdown with YAML frontmatter. Params: `title` or `id`

## Usage Patterns

**Finding a note by topic:** Use `search_notes` with hybrid mode first. If semantic search is unavailable, it falls back to text automatically.

**Browsing a folder:** Use `list_notes` with the `folder` parameter. Use `limit` to avoid overwhelming output.

**Reading note content:** Use `get_note` — returns decoded plaintext content, not raw protobuf.

**Creating notes:** Pass Markdown in the `body` param — it's converted to HTML automatically. No need to write HTML.

**Bulk operations:** For working through many notes (triage, audit), use `list_notes` with sort/order to work through them systematically. Use the `/notes-triage` command for guided cleanup.
```

**Step 2: Commit**

```bash
cd ~/repos/claude-code-plugins
git add plugins/apple-notes/skills/note-operations/SKILL.md
git commit -m "feat(apple-notes): add note-operations skill"
```

---

### Task 6: Create note-triage skill

**Files:**
- Create: `~/repos/claude-code-plugins/plugins/apple-notes/skills/note-triage/SKILL.md`

**Step 1: Write skill**

```markdown
---
name: note-triage
description: Use when the user asks to triage, clean up, organize, or audit their Apple Notes. Also use when they mention "notes triage", "clean up notes", "sort notes", or reference the Apple Notes audit.
---

# Apple Notes Triage

## Overview

Guide the user through batch cleanup of Apple Notes. The 06.13 audit identified 741 notes with ~308 stuck in capture purgatory (01 Inbox, Notes default folder). Work through notes in batches of ~20, proposing actions for each.

## Workflow

### 1. Target Selection

Ask the user which folder to triage, or default to the worst offenders:
- "Notes" (default folder) — 95 unsorted notes
- "01 Inbox" — 213 unsorted notes

Use `list_folders` to show current folder state.

### 2. Batch Pull

Use `list_notes` with:
- `folder` — the target folder
- `limit: 20` — batch size
- `sort_by: "modified"`, `order: "asc"` — oldest first (stalest = most likely to delete/archive)

### 3. Analyze Each Note

For each note in the batch, use `get_note` to read content. Classify:

| Action | Criteria | Execution |
|--------|----------|-----------|
| **Delete** | Empty, near-empty (≤5 chars), "New Note" stub, duplicate title, obviously scratch | `delete_note` (moves to Recently Deleted, 30-day recovery) |
| **Archive** | Valuable content but stale; belongs in JD tree as Markdown | `export_note` → save to JD path via `jd` CLI → `delete_note` |
| **Keep + Refolder** | Active/useful but in wrong folder | `move_note` to correct folder |
| **Keep as-is** | Active, ephemeral, or already well-placed | No action |

### 4. Present Batch

Show a table of the batch with proposed actions:

```
| # | Title                    | Modified   | Chars | Action       | Destination          |
|---|--------------------------|------------|-------|--------------|----------------------|
| 1 | New Note                 | 2021-03-14 | 0     | Delete       | —                    |
| 2 | Adelphi syllabus draft   | 2021-07-05 | 2340  | Archive      | 52.01 Unsorted       |
| 3 | Shopping list            | 2025-12-01 | 45    | Keep+Refolder| 31.04 Inventories    |
```

Ask user to approve, modify, or skip individual items.

### 5. Execute

Process approved actions. For archives:
1. `export_note` to get Markdown
2. Write to temp file
3. Use `jd` CLI to file: `jd mv /tmp/note.md <JD-ID>`
4. `delete_note` to remove from Notes

Report results: successes, failures, skipped.

### 6. Next Batch

After each batch, show progress (X of Y notes in folder processed) and ask if user wants to continue.

## Integration with JD

When archiving, determine the target JD ID based on note content and folder:
- Notes in "52 Adelphi University" → archive to `52.xx` in JD tree
- Notes in "26.02 Notes" → archive to `26.xx` in JD tree
- Notes in "73.06 LLM outputs" → archive to `73.06` in JD tree
- Generic/unsorted → file to category unsorted (`xx.01`) in the best-fit area

Use `jd find` or `jd ls` to verify target IDs exist before filing.

## Safety

- Delete moves to Recently Deleted (30-day recovery window)
- Never delete locked/password-protected notes
- Always show the batch and get approval before executing
- Archive exports the note to Markdown BEFORE deleting from Notes
- Report failures without stopping the batch
```

**Step 2: Commit**

```bash
cd ~/repos/claude-code-plugins
git add plugins/apple-notes/skills/note-triage/SKILL.md
git commit -m "feat(apple-notes): add note-triage skill"
```

---

### Task 7: Create /notes-triage command

**Files:**
- Create: `~/repos/claude-code-plugins/plugins/apple-notes/commands/notes-triage.md`

**Step 1: Write command**

```markdown
---
name: notes-triage
description: Start an Apple Notes triage session to clean up and organize notes
---

Start a triage session for Apple Notes. Use the note-triage skill to guide the process.

If the user provided a folder name as an argument, triage that folder. Otherwise, show the current folder inventory using `list_folders` and ask which folder to start with — suggest the largest unsorted folders first.
```

**Step 2: Commit**

```bash
cd ~/repos/claude-code-plugins
git add plugins/apple-notes/commands/notes-triage.md
git commit -m "feat(apple-notes): add /notes-triage command"
```

---

### Task 8: Install and smoke test

**Step 1: Reload plugins**

User runs `/reload-plugins` in Claude Code.

**Step 2: Verify MCP server starts**

Use `list_folders` tool to confirm the server is running and can read the Notes database.

**Step 3: Test each tool**

- `list_notes` with `limit: 3`
- `get_note` with a known note title
- `search_notes` with a simple query
- `list_folders`
- `create_note` with a test note, then `delete_note` to clean up
- `export_note` on any note

**Step 4: Verify skills trigger**

Ask "what's in my Apple Notes?" — note-operations skill should activate.
Run `/notes-triage` — command should load and note-triage skill should guide the session.

**Step 5: Final commit (update TODO)**

```bash
cd ~/repos/claude-code-plugins
# Update TODO.md to mark completed items
git add plugins/apple-notes/TODO.md
git commit -m "feat(apple-notes): mark initial implementation complete in TODO"
```
