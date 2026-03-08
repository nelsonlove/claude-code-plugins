#!/usr/bin/env python3
"""
session-name MCP server

Exposes a single tool: set_session_name(name)
Writes the name to ~/.claude/session-names/<PPID> so the status line
script can read it using $PPID (both are children of the same Claude process).
Cleans up on exit.
"""
import sys
import json
import os
import atexit
import signal

NAMES_DIR = os.path.expanduser("~/.claude/session-names")
os.makedirs(NAMES_DIR, exist_ok=True)

name_file = os.path.join(NAMES_DIR, str(os.getppid()))


def cleanup():
    try:
        os.unlink(name_file)
    except FileNotFoundError:
        pass


atexit.register(cleanup)
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))


def send(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


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
                "serverInfo": {"name": "session-name", "version": "1.0.0"},
            },
        })

    elif method == "tools/list":
        send({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": [
                    {
                        "name": "set_session_name",
                        "description": (
                            "Set a human-readable name for the current Claude session. "
                            "The name appears in the terminal status line. "
                            "Call this at the start of a session to label what you're working on."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": "Short session label (e.g. 'divorce reorg', 'wham studio')",
                                }
                            },
                            "required": ["name"],
                        },
                    }
                ]
            },
        })

    elif method == "tools/call":
        params = msg.get("params", {})
        tool = params.get("name")
        args = params.get("arguments", {})

        if tool == "set_session_name":
            name = args.get("name", "").strip()
            with open(name_file, "w") as f:
                f.write(name)
            send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": f"Session name set to: {name}"}]
                },
            })
        else:
            send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Unknown tool: {tool}"},
            })

    # Notifications have no id — no response needed


for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        handle(json.loads(line))
    except Exception:
        pass
