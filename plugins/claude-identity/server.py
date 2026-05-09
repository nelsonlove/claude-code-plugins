#!/usr/bin/env python3
"""claude-identity MCP server.

Provides session-identity primitives for cross-plugin use. Stdlib only; modeled
on the existing claude-notifications/server.py JSON-RPC stdio pattern.

Tools:
  - whoami           : own session info (id, handle, pid, cwd, status, tags)
  - list_sessions    : all live sessions, same fields
  - add_tag          : add tag to self or other session (--session)
  - remove_tag       : remove tag (only original assigner in v2; v1: anyone)
  - list_tags        : list a session's tags
  - match            : test whether a session's tags match a given scope
"""
import json
import os
import sys
from pathlib import Path

# Ensure lib is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import config, registry, sidecar
from lib.match import match as match_fn


VERSION = "0.1.0"


def send(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def home():
    return os.path.expanduser("~")


def _resolve_session_or_self(target):
    """Return a session UUID; if target is None, use the current process's session.

    The MCP server runs as a subprocess of its CC session, so os.getppid()
    gives the CC PID — not os.getpid(), which is the server's own PID and
    has no registry entry.
    """
    if target is None:
        entry = registry.find_my_session(home(), os.getppid())
        if entry is None:
            raise RuntimeError("Could not resolve own session (no registry entry for parent PID)")
        return entry["sessionId"], entry["handle"]
    sid = registry.resolve_handle_or_uuid_to_session_id(home(), target)
    return sid, registry.resolve_handle(home(), sid)


TOOLS = [
    {
        "name": "whoami",
        "description": "Return this session's identity: session_id, handle, pid, cwd, status, subscribed tags.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_sessions",
        "description": "List all live Claude Code sessions with handle, pid, cwd, status, and subscribed tags.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "add_tag",
        "description": "Add a subscription tag to a session. session_id defaults to self; can be a handle or UUID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tag": {"type": "string"},
                "session_id": {"type": "string", "description": "handle or UUID; default self"},
            },
            "required": ["tag"],
        },
    },
    {
        "name": "remove_tag",
        "description": "Remove a subscription tag from a session. session_id defaults to self.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tag": {"type": "string"},
                "session_id": {"type": "string"},
            },
            "required": ["tag"],
        },
    },
    {
        "name": "list_tags",
        "description": "List a session's subscription tags. session_id defaults to self.",
        "inputSchema": {
            "type": "object",
            "properties": {"session_id": {"type": "string"}},
        },
    },
    {
        "name": "match",
        "description": "Test whether a session's tags (plus implicit handle) match the given scope.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "scope": {"type": "array", "items": {"type": "string"}},
                "session_id": {"type": "string"},
            },
            "required": ["scope"],
        },
    },
]


def call_tool(name, args):
    if name == "whoami":
        entry = registry.find_my_session(home(), os.getppid())
        if entry is None:
            return {"error": "no registry entry for parent PID"}
        tags = sidecar.list_tags(home(), entry["sessionId"])
        return {
            "session_id": entry["sessionId"], "handle": entry["handle"],
            "pid": entry["pid"], "cwd": entry["cwd"],
            "status": entry.get("status"), "tags": tags,
        }
    if name == "list_sessions":
        out = []
        for e in registry.list_live_sessions(home()):
            tags = sidecar.list_tags(home(), e["sessionId"])
            out.append({
                "session_id": e["sessionId"], "handle": e["handle"],
                "pid": e["pid"], "cwd": e["cwd"], "status": e.get("status"),
                "tags": tags,
            })
        return {"sessions": out}
    if name == "add_tag":
        sid, _ = _resolve_session_or_self(args.get("session_id"))
        added = sidecar.add_tag(home(), sid, args["tag"])
        return {"ok": True, "added": added, "tags": sidecar.list_tags(home(), sid)}
    if name == "remove_tag":
        sid, _ = _resolve_session_or_self(args.get("session_id"))
        removed = sidecar.remove_tag(home(), sid, args["tag"])
        return {"ok": True, "removed": removed, "tags": sidecar.list_tags(home(), sid)}
    if name == "list_tags":
        sid, _ = _resolve_session_or_self(args.get("session_id"))
        return {"tags": sidecar.list_tags(home(), sid)}
    if name == "match":
        sid, handle = _resolve_session_or_self(args.get("session_id"))
        sub = list(sidecar.list_tags(home(), sid))
        if handle:
            sub.append(handle)  # implicit handle subscription
        return {"matches": match_fn(sub, args["scope"])}
    raise ValueError(f"Unknown tool: {name}")


def handle(msg):
    method = msg.get("method", "")
    msg_id = msg.get("id")
    if method == "initialize":
        send({"jsonrpc": "2.0", "id": msg_id, "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "claude-identity", "version": VERSION},
        }})
    elif method == "tools/list":
        send({"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}})
    elif method == "tools/call":
        params = msg.get("params", {})
        try:
            result = call_tool(params["name"], params.get("arguments", {}))
            send({"jsonrpc": "2.0", "id": msg_id, "result": {
                "content": [{"type": "text", "text": json.dumps(result)}]
            }})
        except registry.AmbiguousHandle as e:
            send({"jsonrpc": "2.0", "id": msg_id, "error": {
                "code": -32602, "message": str(e),
                "data": {"candidates": e.candidates},
            }})
        except KeyError as e:
            send({"jsonrpc": "2.0", "id": msg_id, "error": {
                "code": -32602, "message": f"Unknown session: {e}",
            }})
        except Exception as e:
            send({"jsonrpc": "2.0", "id": msg_id, "error": {
                "code": -32603, "message": str(e),
            }})


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            handle(json.loads(line))
        except json.JSONDecodeError:
            pass


if __name__ == "__main__":
    main()
