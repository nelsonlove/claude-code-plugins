#!/usr/bin/env python3
"""
claude-notifications MCP server

Persistent cross-session notification inbox for automated agents and cron jobs.
Stores notifications as .md files with YAML frontmatter in ~/.claude/inbox/.

Tools: post_notification, get_notifications, dismiss_notification
"""
import sys
import json
import os
import re
import subprocess
from datetime import datetime, timezone

INBOX_DIR = os.path.expanduser("~/.claude/inbox")
os.makedirs(INBOX_DIR, exist_ok=True)

TERMINAL_NOTIFIER = "/opt/homebrew/bin/terminal-notifier"


def send(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def fire_notification(source, message):
    """Send a macOS notification via terminal-notifier (best-effort)."""
    if not os.path.isfile(TERMINAL_NOTIFIER):
        return
    try:
        subprocess.Popen(
            [TERMINAL_NOTIFIER, "-title", f"Claude: {source}",
             "-message", message[:200], "-group", "claude-notifications"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def make_filename(tags, source):
    """Generate notification filename: {ISO-timestamp}_{primary-tag}_{source}.md"""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    primary_tag = tags[0] if tags else "misc"
    safe_source = re.sub(r'[^a-zA-Z0-9_-]', '-', source)
    safe_source = re.sub(r'-+', '-', safe_source).strip('-') or 'unknown'
    return f"{ts}_{primary_tag}_{safe_source}.md"


def write_notification(tags, source, message):
    """Write a notification file and fire terminal-notifier."""
    filename = make_filename(tags, source)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    tags_yaml = json.dumps(tags)

    content = f"""---
tags: {tags_yaml}
source: {source}
created: {ts}
---
{message}
"""
    filepath = os.path.join(INBOX_DIR, filename)
    with open(filepath, "w") as f:
        f.write(content)

    fire_notification(source, message)
    return filename


def parse_frontmatter(text):
    """Parse YAML frontmatter from notification file (no PyYAML dependency)."""
    m = re.match(r'^---\n(.*?)\n---\n(.*)', text, re.DOTALL)
    if not m:
        return {}, text

    fm_text, body = m.group(1), m.group(2)
    meta = {}

    # Parse tags: ["a", "b"]
    tags_match = re.search(r'tags:\s*\[([^\]]*)\]', fm_text)
    if tags_match:
        meta["tags"] = [t.strip().strip('"').strip("'") for t in tags_match.group(1).split(",") if t.strip()]

    # Parse source:
    source_match = re.search(r'source:\s*(.+)', fm_text)
    if source_match:
        meta["source"] = source_match.group(1).strip()

    # Parse created:
    created_match = re.search(r'created:\s*(.+)', fm_text)
    if created_match:
        meta["created"] = created_match.group(1).strip()

    return meta, body.strip()


def read_notifications(filter_tags=None):
    """Read all notifications, optionally filtering by tags (intersection match)."""
    results = []
    for fname in sorted(os.listdir(INBOX_DIR)):
        if not fname.endswith(".md"):
            continue
        filepath = os.path.join(INBOX_DIR, fname)
        try:
            with open(filepath, "r") as f:
                text = f.read()
        except Exception:
            continue

        meta, body = parse_frontmatter(text)

        if filter_tags:
            note_tags = set(meta.get("tags", []))
            if not note_tags.intersection(set(filter_tags)):
                continue

        results.append({
            "id": fname,
            "tags": meta.get("tags", []),
            "source": meta.get("source", ""),
            "created": meta.get("created", ""),
            "message": body,
        })

    return results


def dismiss(notification_id):
    """Delete a notification file by its id (filename)."""
    filepath = os.path.join(INBOX_DIR, notification_id)
    if not os.path.isfile(filepath):
        return False
    os.unlink(filepath)
    return True


# --- MCP JSON-RPC handler ---

TOOLS = [
    {
        "name": "post_notification",
        "description": (
            "Post a notification to the persistent inbox (~/.claude/inbox/). "
            "Use tags to classify by Johnny Decimal ID — e.g. ['26.06', '26', '20-29'] "
            "for the divorce email archive. The source identifies who/what posted it "
            "(e.g. 'divorce-email-cron'). Fires a macOS notification as a side effect."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "JD tags for classification (e.g. ['26.06', '26', '20-29'])",
                },
                "source": {
                    "type": "string",
                    "description": "Identifier for the notification source (e.g. 'divorce-email-cron')",
                },
                "message": {
                    "type": "string",
                    "description": "The notification message body",
                },
            },
            "required": ["tags", "source", "message"],
        },
    },
    {
        "name": "get_notifications",
        "description": (
            "Retrieve notifications from the inbox. Optionally filter by JD tags "
            "(intersection match — returns notifications that have any of the given tags). "
            "Results are sorted oldest-first."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional JD tags to filter by (intersection match)",
                },
            },
        },
    },
    {
        "name": "dismiss_notification",
        "description": (
            "Remove a notification from the inbox by its id (the filename). "
            "Use get_notifications first to find the id."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "The notification filename (returned by get_notifications)",
                },
            },
            "required": ["id"],
        },
    },
]


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
                "serverInfo": {"name": "claude-notifications", "version": "0.1.0"},
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

        if tool == "post_notification":
            tags = args.get("tags", [])
            source = args.get("source", "unknown")
            message = args.get("message", "")
            filename = write_notification(tags, source, message)
            send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": f"Notification posted: {filename}"}]
                },
            })

        elif tool == "get_notifications":
            filter_tags = args.get("tags")
            notes = read_notifications(filter_tags)
            if not notes:
                text = "Inbox is empty."
            else:
                lines = []
                for n in notes:
                    lines.append(
                        f"**{n['id']}**\n"
                        f"  tags: {', '.join(n['tags'])}  |  source: {n['source']}  |  {n['created']}\n"
                        f"  {n['message']}"
                    )
                text = f"{len(notes)} notification(s):\n\n" + "\n\n".join(lines)
            send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": text}]
                },
            })

        elif tool == "dismiss_notification":
            nid = args.get("id", "")
            if dismiss(nid):
                text = f"Dismissed: {nid}"
            else:
                text = f"Not found: {nid}"
            send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": text}]
                },
            })

        else:
            send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Unknown tool: {tool}"},
            })

    # Notifications (no id) — no response needed


for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    parsed = None
    try:
        parsed = json.loads(line)
        handle(parsed)
    except json.JSONDecodeError:
        pass  # Malformed JSON — can't determine id, skip
    except Exception as e:
        # If the message had an id, send an error response
        msg_id = parsed.get("id") if parsed else None
        if msg_id is not None:
            send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32603, "message": str(e)},
            })
