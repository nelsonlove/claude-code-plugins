#!/usr/bin/env python3
"""
org-roam-claude MCP server

Queries org-roam's SQLite DB for search/graph operations and reads/writes
.org files directly. Provides tools for searching, reading, creating, and
editing org-roam notes.
"""

import sys
import json
import os
import re
import signal
import sqlite3
import uuid
from datetime import datetime

signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

# --- Configuration ---

DB_PATH = os.environ.get(
    "ORG_ROAM_DB", os.path.expanduser("~/org/org-roam.db")
)
ROAM_DIR = os.environ.get(
    "ORG_ROAM_DIR",
    os.path.expanduser(
        "~/Documents/00-09 System/02 Notes/02.03 Org-roam"
    ),
)

# --- Helpers ---


def unquote(s):
    """Strip emacsql's literal double-quote wrapping."""
    if isinstance(s, str) and s.startswith('"') and s.endswith('"'):
        return s[1:-1]
    return s


def query_db(sql, params=()):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_node_by_title_or_id(identifier):
    """Find a node by exact title or ID."""
    # Try as ID first
    rows = query_db("SELECT * FROM nodes WHERE id = ?", (identifier,))
    if not rows:
        rows = query_db(
            "SELECT * FROM nodes WHERE id = ?", (f'"{identifier}"',)
        )
    if not rows:
        # Try as title
        rows = query_db(
            "SELECT * FROM nodes WHERE title = ?", (f'"{identifier}"',)
        )
    if not rows:
        rows = query_db(
            "SELECT * FROM nodes WHERE title = ?", (identifier,)
        )
    if not rows:
        # Case-insensitive title search
        rows = query_db(
            "SELECT * FROM nodes WHERE lower(title) = lower(?)",
            (f'"{identifier}"',),
        )
    if not rows:
        rows = query_db(
            "SELECT * FROM nodes WHERE lower(title) = lower(?)",
            (identifier,),
        )
    return rows[0] if rows else None


def read_org_file(filepath):
    """Read an org file and return its content."""
    try:
        with open(filepath, "r") as f:
            return f.read()
    except (FileNotFoundError, PermissionError) as e:
        return f"Error reading file: {e}"


def slugify(title):
    """Convert a title to a filename slug."""
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s-]+", "_", slug)
    slug = slug.strip("_")
    return slug


def make_org_note(title, body="", tags=None):
    """Generate org-roam note content."""
    node_id = str(uuid.uuid4())
    now = datetime.now()
    timestamp = now.strftime("[%Y-%m-%d %a %H:%M]")

    filetags = tags or ["claude"]
    tagstr = ":" + ":".join(filetags) + ":"

    lines = [
        ":PROPERTIES:",
        f":ID: {node_id}",
        f":CREATED: {timestamp}",
        ":END:",
        f"#+title: {title}",
        f"#+filetags: {tagstr}",
        "",
    ]
    if body:
        lines.append(body)
        if not body.endswith("\n"):
            lines.append("")

    return node_id, "\n".join(lines)


def try_db_sync():
    """Attempt to sync org-roam DB via emacsclient. Silent on failure."""
    try:
        import subprocess

        subprocess.run(
            [
                "/Applications/Emacs.app/Contents/MacOS/bin/emacsclient",
                "--eval",
                "(org-roam-db-sync)",
            ],
            timeout=5,
            capture_output=True,
        )
    except Exception:
        pass


# --- Tool Definitions ---

TOOLS = [
    {
        "name": "search_notes",
        "description": (
            "Search org-roam notes by title, tag, or full-text content. "
            "Returns matching node metadata. Use 'query' for title/content "
            "search, 'tag' to filter by filetag."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term for title or content",
                },
                "tag": {
                    "type": "string",
                    "description": "Filter by filetag (e.g. 'education', 'psych')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 20)",
                },
            },
        },
    },
    {
        "name": "get_note",
        "description": (
            "Read a note's full content by title or ID. Returns the org "
            "text plus metadata (tags, backlinks, forward links)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "identifier": {
                    "type": "string",
                    "description": "Note title or UUID",
                },
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "get_backlinks",
        "description": (
            "Get all notes that link TO a given note. Returns linking "
            "nodes with context snippets."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "identifier": {
                    "type": "string",
                    "description": "Note title or UUID",
                },
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "get_links",
        "description": "Get all notes that a given note links TO.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "identifier": {
                    "type": "string",
                    "description": "Note title or UUID",
                },
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "list_tags",
        "description": "List all org-roam filetags with note counts.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "find_by_tag",
        "description": "List all notes with a given filetag.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tag": {
                    "type": "string",
                    "description": "The filetag to filter by",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 50)",
                },
            },
            "required": ["tag"],
        },
    },
    {
        "name": "explore_neighborhood",
        "description": (
            "Given a note, return its links and backlinks N levels deep. "
            "Good for exploring clusters and related topics."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "identifier": {
                    "type": "string",
                    "description": "Note title or UUID",
                },
                "depth": {
                    "type": "integer",
                    "description": "Levels of links to follow (default 1, max 3)",
                },
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "create_note",
        "description": (
            "Create a new org-roam note. Uses slug-based filename, adds "
            ":ID:, :CREATED:, #+title:, and #+filetags: :claude: by default."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Note title",
                },
                "body": {
                    "type": "string",
                    "description": "Note body content (org-mode format)",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Filetags (default ['claude']). 'claude' is always "
                        "included."
                    ),
                },
            },
            "required": ["title"],
        },
    },
    {
        "name": "update_note",
        "description": (
            "Update an existing org-roam note. Can append content or "
            "replace the body (everything after the frontmatter)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "identifier": {
                    "type": "string",
                    "description": "Note title or UUID",
                },
                "content": {
                    "type": "string",
                    "description": "Content to add or replace with",
                },
                "mode": {
                    "type": "string",
                    "enum": ["append", "replace"],
                    "description": "append (default) or replace body",
                },
            },
            "required": ["identifier", "content"],
        },
    },
    {
        "name": "add_link",
        "description": (
            "Insert an org-roam link to another note. Appends an "
            "[[id:...][Title]] link to the source note."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Source note title or UUID (where to add the link)",
                },
                "target": {
                    "type": "string",
                    "description": "Target note title or UUID (what to link to)",
                },
                "context": {
                    "type": "string",
                    "description": (
                        "Optional text to wrap the link in. Use {link} as "
                        "placeholder for the link itself."
                    ),
                },
            },
            "required": ["source", "target"],
        },
    },
]

# --- Tool Handlers ---


def handle_search_notes(args):
    query = args.get("query", "")
    tag = args.get("tag", "")
    limit = min(args.get("limit", 20), 100)

    results = []

    if tag:
        # Filter by tag first
        rows = query_db(
            """
            SELECT n.id, n.title, n.file
            FROM nodes n
            JOIN tags t ON t.node_id = n.id
            WHERE t.tag = ? OR t.tag = ?
            """,
            (f'"{tag}"', tag),
        )
        if query:
            query_lower = query.lower()
            rows = [
                r
                for r in rows
                if query_lower in unquote(r["title"] or "").lower()
            ]
    elif query:
        query_lower = query.lower()
        # Title search via DB
        rows = query_db(
            "SELECT id, title, file FROM nodes WHERE lower(title) LIKE ?",
            (f"%{query_lower}%",),
        )

        # If few title matches, also grep file content
        if len(rows) < limit:
            title_files = {unquote(r["file"]) for r in rows}
            try:
                import subprocess

                grep_result = subprocess.run(
                    ["grep", "-rli", query, "--include=*.org", ROAM_DIR],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                for filepath in grep_result.stdout.strip().split("\n"):
                    if filepath and filepath not in title_files:
                        # Look up node for this file
                        file_rows = query_db(
                            "SELECT id, title, file FROM nodes WHERE file = ? OR file = ?",
                            (filepath, f'"{filepath}"'),
                        )
                        rows.extend(file_rows)
            except Exception:
                pass
    else:
        rows = query_db(
            "SELECT id, title, file FROM nodes ORDER BY rowid DESC LIMIT ?",
            (limit,),
        )

    # Deduplicate and format
    seen = set()
    for r in rows:
        node_id = unquote(r["id"])
        if node_id in seen:
            continue
        seen.add(node_id)
        title = unquote(r["title"] or "")

        # Get tags for this node
        tag_rows = query_db(
            "SELECT tag FROM tags WHERE node_id = ? OR node_id = ?",
            (r["id"], f'"{node_id}"'),
        )
        node_tags = [unquote(t["tag"]) for t in tag_rows]

        results.append(
            {"id": node_id, "title": title, "tags": node_tags}
        )
        if len(results) >= limit:
            break

    return {"count": len(results), "notes": results}


def handle_get_note(args):
    identifier = args["identifier"]
    node = get_node_by_title_or_id(identifier)
    if not node:
        return {"error": f"Note not found: {identifier}"}

    node_id = unquote(node["id"])
    title = unquote(node["title"] or "")
    filepath = unquote(node["file"])

    content = read_org_file(filepath)

    # Get tags
    tag_rows = query_db(
        "SELECT tag FROM tags WHERE node_id = ? OR node_id = ?",
        (node["id"], f'"{node_id}"'),
    )
    tags = [unquote(t["tag"]) for t in tag_rows]

    # Get forward links
    link_rows = query_db(
        """
        SELECT l.dest, n.title FROM links l
        LEFT JOIN nodes n ON n.id = l.dest
        WHERE l.source = ? OR l.source = ?
        AND l.type = '"id"'
        """,
        (node["id"], f'"{node_id}"'),
    )
    forward_links = [
        {"id": unquote(r["dest"]), "title": unquote(r["title"] or "")}
        for r in link_rows
        if r["title"]
    ]

    # Get backlinks
    back_rows = query_db(
        """
        SELECT l.source, n.title FROM links l
        LEFT JOIN nodes n ON n.id = l.source
        WHERE l.dest = ? OR l.dest = ?
        AND l.type = '"id"'
        """,
        (node["id"], f'"{node_id}"'),
    )
    backlinks = [
        {"id": unquote(r["source"]), "title": unquote(r["title"] or "")}
        for r in back_rows
        if r["title"]
    ]

    return {
        "id": node_id,
        "title": title,
        "tags": tags,
        "content": content,
        "forward_links": forward_links,
        "backlinks": backlinks,
    }


def handle_get_backlinks(args):
    identifier = args["identifier"]
    node = get_node_by_title_or_id(identifier)
    if not node:
        return {"error": f"Note not found: {identifier}"}

    node_id = unquote(node["id"])

    rows = query_db(
        """
        SELECT l.source, n.title, n.file FROM links l
        JOIN nodes n ON n.id = l.source
        WHERE (l.dest = ? OR l.dest = ?)
        AND l.type = '"id"'
        """,
        (node["id"], f'"{node_id}"'),
    )

    backlinks = []
    for r in rows:
        src_id = unquote(r["source"])
        src_title = unquote(r["title"] or "")
        filepath = unquote(r["file"])

        # Get context snippet around the link
        snippet = ""
        try:
            content = read_org_file(filepath)
            for line in content.split("\n"):
                if node_id in line:
                    snippet = line.strip()[:200]
                    break
        except Exception:
            pass

        backlinks.append(
            {"id": src_id, "title": src_title, "context": snippet}
        )

    return {
        "note": unquote(node["title"] or ""),
        "count": len(backlinks),
        "backlinks": backlinks,
    }


def handle_get_links(args):
    identifier = args["identifier"]
    node = get_node_by_title_or_id(identifier)
    if not node:
        return {"error": f"Note not found: {identifier}"}

    node_id = unquote(node["id"])

    rows = query_db(
        """
        SELECT l.dest, n.title FROM links l
        JOIN nodes n ON n.id = l.dest
        WHERE (l.source = ? OR l.source = ?)
        AND l.type = '"id"'
        """,
        (node["id"], f'"{node_id}"'),
    )

    links = [
        {"id": unquote(r["dest"]), "title": unquote(r["title"] or "")}
        for r in rows
    ]

    return {
        "note": unquote(node["title"] or ""),
        "count": len(links),
        "links": links,
    }


def handle_list_tags(args):
    rows = query_db(
        "SELECT tag, COUNT(*) as count FROM tags GROUP BY tag ORDER BY count DESC"
    )
    tags = [{"tag": unquote(r["tag"]), "count": r["count"]} for r in rows]
    return {"tags": tags}


def handle_find_by_tag(args):
    tag = args["tag"]
    limit = min(args.get("limit", 50), 200)

    rows = query_db(
        """
        SELECT n.id, n.title FROM nodes n
        JOIN tags t ON t.node_id = n.id
        WHERE t.tag = ? OR t.tag = ?
        ORDER BY n.title
        LIMIT ?
        """,
        (f'"{tag}"', tag, limit),
    )

    notes = [
        {"id": unquote(r["id"]), "title": unquote(r["title"] or "")}
        for r in rows
    ]
    return {"tag": tag, "count": len(notes), "notes": notes}


def handle_explore_neighborhood(args):
    identifier = args["identifier"]
    depth = min(args.get("depth", 1), 3)

    node = get_node_by_title_or_id(identifier)
    if not node:
        return {"error": f"Note not found: {identifier}"}

    root_id = unquote(node["id"])
    root_title = unquote(node["title"] or "")

    visited = set()
    layers = []

    current_ids = {root_id: root_title}
    visited.add(root_id)

    for level in range(depth):
        layer_nodes = []
        next_ids = {}

        for nid, ntitle in current_ids.items():
            # Forward links
            fwd = query_db(
                """
                SELECT l.dest, n.title FROM links l
                JOIN nodes n ON n.id = l.dest
                WHERE (l.source = ? OR l.source = ?)
                AND l.type = '"id"'
                """,
                (f'"{nid}"', nid),
            )
            # Backlinks
            back = query_db(
                """
                SELECT l.source, n.title FROM links l
                JOIN nodes n ON n.id = l.source
                WHERE (l.dest = ? OR l.dest = ?)
                AND l.type = '"id"'
                """,
                (f'"{nid}"', nid),
            )

            fwd_list = []
            for r in fwd:
                rid = unquote(r["dest"])
                rtitle = unquote(r["title"] or "")
                fwd_list.append({"id": rid, "title": rtitle})
                if rid not in visited:
                    next_ids[rid] = rtitle
                    visited.add(rid)

            back_list = []
            for r in back:
                rid = unquote(r["source"])
                rtitle = unquote(r["title"] or "")
                back_list.append({"id": rid, "title": rtitle})
                if rid not in visited:
                    next_ids[rid] = rtitle
                    visited.add(rid)

            layer_nodes.append(
                {
                    "id": nid,
                    "title": ntitle,
                    "links_to": fwd_list,
                    "linked_from": back_list,
                }
            )

        layers.append({"level": level + 1, "nodes": layer_nodes})
        current_ids = next_ids

    return {
        "root": {"id": root_id, "title": root_title},
        "depth": depth,
        "total_nodes_found": len(visited),
        "layers": layers,
    }


def handle_create_note(args):
    title = args["title"]
    body = args.get("body", "")
    tags = args.get("tags", [])

    # Ensure 'claude' tag is present
    if "claude" not in tags:
        tags.append("claude")

    slug = slugify(title)
    filename = f"{slug}.org"
    filepath = os.path.join(ROAM_DIR, filename)

    # Don't overwrite existing files
    if os.path.exists(filepath):
        # Add a short suffix
        slug = f"{slug}_{uuid.uuid4().hex[:6]}"
        filename = f"{slug}.org"
        filepath = os.path.join(ROAM_DIR, filename)

    node_id, content = make_org_note(title, body, tags)

    with open(filepath, "w") as f:
        f.write(content)

    try_db_sync()

    return {
        "id": node_id,
        "title": title,
        "file": filepath,
        "tags": tags,
    }


def handle_update_note(args):
    identifier = args["identifier"]
    new_content = args["content"]
    mode = args.get("mode", "append")

    node = get_node_by_title_or_id(identifier)
    if not node:
        return {"error": f"Note not found: {identifier}"}

    filepath = unquote(node["file"])

    if not os.path.exists(filepath):
        return {"error": f"File not found: {filepath}"}

    with open(filepath, "r") as f:
        original = f.read()

    if mode == "append":
        # Append to end of file
        if not original.endswith("\n"):
            original += "\n"
        updated = original + "\n" + new_content + "\n"
    elif mode == "replace":
        # Replace everything after frontmatter (properties + title + filetags)
        # Find the end of frontmatter
        lines = original.split("\n")
        frontmatter_end = 0
        in_properties = False
        for i, line in enumerate(lines):
            if line.strip() == ":PROPERTIES:":
                in_properties = True
            elif line.strip() == ":END:":
                in_properties = False
                frontmatter_end = i + 1
            elif not in_properties and line.startswith("#+"):
                frontmatter_end = i + 1
            elif not in_properties and not line.startswith("#+") and line.strip():
                break

        header = "\n".join(lines[:frontmatter_end])
        updated = header + "\n\n" + new_content + "\n"
    else:
        return {"error": f"Invalid mode: {mode}. Use 'append' or 'replace'."}

    with open(filepath, "w") as f:
        f.write(updated)

    try_db_sync()

    return {
        "id": unquote(node["id"]),
        "title": unquote(node["title"] or ""),
        "file": filepath,
        "mode": mode,
    }


def handle_add_link(args):
    source_id = args["source"]
    target_id = args["target"]
    context = args.get("context", "")

    source_node = get_node_by_title_or_id(source_id)
    if not source_node:
        return {"error": f"Source note not found: {source_id}"}

    target_node = get_node_by_title_or_id(target_id)
    if not target_node:
        return {"error": f"Target note not found: {target_id}"}

    target_nid = unquote(target_node["id"])
    target_title = unquote(target_node["title"] or "")
    source_filepath = unquote(source_node["file"])

    link_text = f"[[id:{target_nid}][{target_title}]]"
    if context:
        link_text = context.replace("{link}", link_text)

    with open(source_filepath, "r") as f:
        content = f.read()

    if not content.endswith("\n"):
        content += "\n"
    content += link_text + "\n"

    with open(source_filepath, "w") as f:
        f.write(content)

    try_db_sync()

    return {
        "source": unquote(source_node["title"] or ""),
        "target": target_title,
        "link": link_text,
    }


# --- Handler Dispatch ---

HANDLERS = {
    "search_notes": handle_search_notes,
    "get_note": handle_get_note,
    "get_backlinks": handle_get_backlinks,
    "get_links": handle_get_links,
    "list_tags": handle_list_tags,
    "find_by_tag": handle_find_by_tag,
    "explore_neighborhood": handle_explore_neighborhood,
    "create_note": handle_create_note,
    "update_note": handle_update_note,
    "add_link": handle_add_link,
}

# --- JSON-RPC stdio loop ---


def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = msg.get("method")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        if method == "initialize":
            send(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {
                            "name": "org-roam-claude",
                            "version": "0.1.0",
                        },
                    },
                }
            )
        elif method == "notifications/initialized":
            pass
        elif method == "tools/list":
            send(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"tools": TOOLS},
                }
            )
        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            handler = HANDLERS.get(tool_name)

            if handler:
                try:
                    result = handler(tool_args)
                    send(
                        {
                            "jsonrpc": "2.0",
                            "id": msg_id,
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": json.dumps(
                                            result, indent=2
                                        ),
                                    }
                                ]
                            },
                        }
                    )
                except Exception as e:
                    send(
                        {
                            "jsonrpc": "2.0",
                            "id": msg_id,
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": json.dumps(
                                            {"error": str(e)}
                                        ),
                                    }
                                ],
                                "isError": True,
                            },
                        }
                    )
            else:
                send(
                    {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {
                            "code": -32601,
                            "message": f"Unknown tool: {tool_name}",
                        },
                    }
                )
        elif msg_id is not None:
            send(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown method: {method}",
                    },
                }
            )


if __name__ == "__main__":
    main()
