#!/usr/bin/env python3
"""claude-threads MCP server. Thread CRUD only.

Identity-related operations (handle resolution, tag CRUD, list_sessions, match)
live in claude-identity. We just read its sessions-meta sidecar.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import config, thread_store
from lib.identity_client import (
    read_session_tags, read_session_handle, discover_my_session_id
)
from lib.match import match


VERSION = "0.2.0"


def send(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def home():
    return os.path.expanduser("~")


def project_root():
    return os.getcwd()


def _cfg():
    return config.load_config(home=home(), project_root=project_root())


def _self_handle():
    # MCP server is a subprocess of CC session — use parent PID, not own PID.
    # See claude-identity PR #13 for the same fix and rationale.
    sid = discover_my_session_id(home(), os.getppid())
    if sid is None:
        return None, None
    return sid, read_session_handle(home(), sid)


TOOLS = [
    {"name": "start_thread",
     "description": "Start a new thread. scope=[<tag>,...] (e.g. ['02.14', 'fern']); topic becomes filename slug; message is the first body. Author/handle is auto-resolved from caller's session.",
     "inputSchema": {"type": "object", "properties": {
         "scope": {"type": "array", "items": {"type": "string"}},
         "topic": {"type": "string"},
         "message": {"type": "string"},
     }, "required": ["scope", "topic", "message"]}},
    {"name": "reply_thread",
     "description": "Append a message to an existing thread. thread_id is 8-char (or unique prefix ≥4).",
     "inputSchema": {"type": "object", "properties": {
         "thread_id": {"type": "string"},
         "message": {"type": "string"},
     }, "required": ["thread_id", "message"]}},
    {"name": "list_threads",
     "description": "List threads; by default filters by caller's subscribed tags. Optional scope_pattern overrides the filter; status filters by enum.",
     "inputSchema": {"type": "object", "properties": {
         "scope_pattern": {"type": "string"},
         "status": {"type": "string"},
     }}},
    {"name": "get_thread",
     "description": "Read a thread fully; returns frontmatter + ordered messages.",
     "inputSchema": {"type": "object", "properties": {
         "thread_id": {"type": "string"}
     }, "required": ["thread_id"]}},
    {"name": "close_thread",
     "description": "Set thread-status to resolved.",
     "inputSchema": {"type": "object", "properties": {
         "thread_id": {"type": "string"}
     }, "required": ["thread_id"]}},
]


def _resolve_thread_id(thread_id_or_prefix, threads_dir):
    """Accept full 8-char id or a unique prefix ≥4. Raise on ambiguity."""
    if len(thread_id_or_prefix) < 4:
        raise ValueError("thread-id prefix must be at least 4 chars")
    matches = [
        t for t in thread_store.list_threads(threads_dir=threads_dir)
        if t["thread_id"].startswith(thread_id_or_prefix)
    ]
    if len(matches) == 0:
        raise KeyError(f"no thread matches '{thread_id_or_prefix}'")
    if len(matches) > 1:
        raise ValueError(f"prefix '{thread_id_or_prefix}' is ambiguous: {[m['thread_id'] for m in matches]}")
    return matches[0]["thread_id"]


def call_tool(name, args):
    cfg = _cfg()
    threads_dir = Path(cfg["threads_dir"])
    threads_dir.mkdir(parents=True, exist_ok=True)
    prefix = cfg["frontmatter_prefix"]

    sid, handle = _self_handle()
    handle = handle or "unknown"

    if name == "start_thread":
        scope = list(args["scope"])
        if cfg["auto_tag_cwd"]:
            scope.append(f"path:{os.getcwd()}")
        return thread_store.create_thread(
            threads_dir=threads_dir, opener_handle=handle,
            scope=scope, topic=args["topic"], first_message=args["message"],
            author_handle=handle, author_model=os.environ.get("CLAUDE_MODEL", "unknown"),
            prefix=prefix,
        )

    if name == "reply_thread":
        tid = _resolve_thread_id(args["thread_id"], threads_dir)
        thread_store.append_message(
            threads_dir=threads_dir, thread_id=tid,
            author_handle=handle, author_model=os.environ.get("CLAUDE_MODEL", "unknown"),
            message=args["message"], prefix=prefix,
        )
        return {"ok": True, "thread_id": tid}

    if name == "list_threads":
        all_threads = thread_store.list_threads(threads_dir=threads_dir, prefix=prefix)
        # Filter by status if requested
        if args.get("status"):
            all_threads = [t for t in all_threads if t["status"] == args["status"]]
        # Filter by scope match
        if args.get("scope_pattern"):
            sub = [args["scope_pattern"]]
        else:
            sub = list(read_session_tags(home(), sid)) if sid else []
            if handle:
                sub.append(handle)
        all_threads = [t for t in all_threads if match(sub, t["scope"])]
        return {"threads": all_threads}

    if name == "get_thread":
        tid = _resolve_thread_id(args["thread_id"], threads_dir)
        return thread_store.read_thread(threads_dir=threads_dir, thread_id=tid, prefix=prefix)

    if name == "close_thread":
        tid = _resolve_thread_id(args["thread_id"], threads_dir)
        thread_store.close_thread(threads_dir=threads_dir, thread_id=tid, prefix=prefix)
        return {"ok": True, "thread_id": tid}

    raise ValueError(f"unknown tool: {name}")


def handle_msg(msg):
    method = msg.get("method", "")
    msg_id = msg.get("id")
    if method == "initialize":
        send({"jsonrpc": "2.0", "id": msg_id, "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "claude-threads", "version": VERSION},
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
        except (KeyError, ValueError) as e:
            send({"jsonrpc": "2.0", "id": msg_id, "error": {
                "code": -32602, "message": str(e),
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
            handle_msg(json.loads(line))
        except json.JSONDecodeError:
            pass


if __name__ == "__main__":
    main()
