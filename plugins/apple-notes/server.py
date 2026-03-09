#!/usr/bin/env python3
"""
apple-notes MCP server

Wraps the apple-notes-cli library over JSON-RPC stdio, exposing tools for
listing, reading, searching, creating, exporting, deleting, and moving notes.
"""
import sys
import json
import signal

# Add the apple-notes-cli source to the path so imports resolve
sys.path.insert(0, "/Users/nelson/repos/apple-notes-cli/src")

from apple_notes.db import NotesDB
from apple_notes.decode import decode_note_content, decode_note_to_markdown
from apple_notes.convert import markdown_to_html
from apple_notes.jxa import create_note, delete_note, move_note

signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

TOOLS = [
    {
        "name": "list_notes",
        "description": "List notes from Apple Notes with metadata (no content). Supports filtering by folder and sorting.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "folder": {"type": "string", "description": "Filter by folder name"},
                "limit": {"type": "integer", "description": "Max notes to return"},
                "sort_by": {"type": "string", "enum": ["modified", "created"], "description": "Sort field (default: modified)"},
                "order": {"type": "string", "enum": ["asc", "desc"], "description": "Sort order (default: desc)"},
            },
        },
    },
    {
        "name": "get_note",
        "description": "Get a single note by title or ID, with decoded text content.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Exact note title"},
                "id": {"type": "integer", "description": "Note primary key (pk)"},
            },
        },
    },
    {
        "name": "list_folders",
        "description": "List all folders in Apple Notes.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "create_note",
        "description": "Create a new note in Apple Notes. Body is markdown, converted to HTML automatically.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Note title"},
                "body": {"type": "string", "description": "Note body in markdown"},
            },
            "required": ["title", "body"],
        },
    },
    {
        "name": "search_notes",
        "description": "Search notes by text, semantic similarity, or hybrid. Falls back to text if semantic is unavailable.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "mode": {"type": "string", "enum": ["text", "semantic", "hybrid"], "description": "Search mode (default: text)"},
                "limit": {"type": "integer", "description": "Max results (default: 20)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "export_note",
        "description": "Export a note as markdown with YAML frontmatter.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Exact note title"},
                "id": {"type": "integer", "description": "Note primary key (pk)"},
            },
        },
    },
    {
        "name": "delete_note",
        "description": "Delete a note from Apple Notes by title.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Exact note title"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "move_note",
        "description": "Move a note to a different folder in Apple Notes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Exact note title"},
                "folder": {"type": "string", "description": "Destination folder name"},
            },
            "required": ["title", "folder"],
        },
    },
]


def send(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def _get_note(db, title=None, pk=None):
    """Fetch a note by title or pk, return dict or None."""
    if title:
        return db.get_note_by_title(title)
    if pk:
        return db.get_note_by_pk(pk)
    return None


def _decode_note(note):
    """Decode a note's content blob to text, returning a new dict."""
    if note is None:
        return None
    result = dict(note)
    raw = result.get("content")
    if raw:
        result["content"] = decode_note_content(raw)
    return result


def handle_tool(tool, args):
    db = NotesDB()

    if tool == "list_notes":
        notes = db.get_all_notes(
            folder=args.get("folder"),
            limit=args.get("limit"),
            sort_by=args.get("sort_by", "modified"),
            order=args.get("order", "desc"),
        )
        return json.dumps(notes, default=str)

    elif tool == "get_note":
        note = _get_note(db, title=args.get("title"), pk=args.get("id"))
        if note is None:
            raise ValueError("Note not found")
        decoded = _decode_note(note)
        return json.dumps(decoded, default=str)

    elif tool == "list_folders":
        folders = db.get_folders()
        return json.dumps(folders, default=str)

    elif tool == "create_note":
        body_html = markdown_to_html(args["body"])
        create_note(args["title"], body_html)
        return f"Created note: {args['title']}"

    elif tool == "search_notes":
        query = args["query"]
        mode = args.get("mode", "text")
        limit = args.get("limit", 20)

        if mode in ("semantic", "hybrid"):
            try:
                from apple_notes.search import SearchIndex
                idx = SearchIndex()
                results = idx.hybrid_search(query, limit=limit)
            except Exception:
                results = db.search_notes(query)[:limit]
        else:
            results = db.search_notes(query)[:limit]

        # Truncate decoded content to 200 chars for search results
        for r in results:
            raw = r.get("content")
            if raw:
                try:
                    text = decode_note_content(raw) if isinstance(raw, bytes) else str(raw)
                    r["content"] = text[:200] + ("..." if len(text) > 200 else "")
                except Exception:
                    r["content"] = str(raw)[:200]

        return json.dumps(results, default=str)

    elif tool == "export_note":
        note = _get_note(db, title=args.get("title"), pk=args.get("id"))
        if note is None:
            raise ValueError("Note not found")

        # Build YAML frontmatter
        fm_fields = {
            "title": note.get("title", ""),
            "folder": note.get("folder", ""),
            "created": str(note.get("createdAt", "")),
            "modified": str(note.get("modifiedAt", "")),
            "account": note.get("account", ""),
            "id": note.get("pk", ""),
            "uuid": note.get("uuid", ""),
        }
        fm_lines = ["---"]
        for k, v in fm_fields.items():
            fm_lines.append(f"{k}: {v}")
        fm_lines.append("---")
        frontmatter = "\n".join(fm_lines)

        md_body = decode_note_to_markdown(note.get("content"), skip_title=True)
        return frontmatter + "\n\n" + md_body

    elif tool == "delete_note":
        delete_note(args["title"])
        return f"Deleted note: {args['title']}"

    elif tool == "move_note":
        move_note(args["title"], args["folder"])
        return f"Moved note '{args['title']}' to folder '{args['folder']}'"

    else:
        raise ValueError(f"Unknown tool: {tool}")


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
                "serverInfo": {"name": "apple-notes", "version": "1.0.0"},
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
        tool = params.get("name")
        args = params.get("arguments", {})
        try:
            result_text = handle_tool(tool, args)
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

    # Notifications (no id) get no response


for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        handle(json.loads(line))
    except Exception:
        pass
