"""End-to-end JSON-RPC tests against the threads MCP server."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SERVER = Path(__file__).parent.parent / "server.py"


class MCPClient:
    def __init__(self, env):
        self.proc = subprocess.Popen(
            [sys.executable, str(SERVER)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env)
        self._id = 0

    def call(self, method, params=None):
        self._id += 1
        msg = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            msg["params"] = params
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        return json.loads(self.proc.stdout.readline())

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=2)


@pytest.fixture
def mcp(tmp_home, write_registry_entry, write_sidecar):
    write_registry_entry(pid=os.getpid(),
                         session_id="self-uuid-aaaa-bbbb-cccc-dddddddddddd",
                         name="testself")
    write_sidecar("self-uuid-aaaa-bbbb-cccc-dddddddddddd", tags=["02.*"])
    env = os.environ.copy()
    env["HOME"] = str(tmp_home)
    c = MCPClient(env)
    yield c
    c.close()


def test_initialize(mcp):
    r = mcp.call("initialize")
    assert r["result"]["serverInfo"]["name"] == "claude-threads"


def test_start_thread_returns_id_and_path(mcp, threads_dir):
    r = mcp.call("tools/call", {
        "name": "start_thread",
        "arguments": {"scope": ["02.14"], "topic": "test topic", "message": "hello"}
    })
    body = json.loads(r["result"]["content"][0]["text"])
    assert "thread_id" in body
    assert len(body["thread_id"]) == 8


def test_reply_thread(mcp, threads_dir):
    r1 = mcp.call("tools/call", {
        "name": "start_thread",
        "arguments": {"scope": ["02.14"], "topic": "t", "message": "first"}
    })
    tid = json.loads(r1["result"]["content"][0]["text"])["thread_id"]
    r2 = mcp.call("tools/call", {
        "name": "reply_thread",
        "arguments": {"thread_id": tid, "message": "second"}
    })
    assert "error" not in r2


def test_list_threads_filters_by_subscriber(mcp, threads_dir):
    mcp.call("tools/call", {"name": "start_thread", "arguments": {
        "scope": ["02.14"], "topic": "match", "message": "x"}})
    mcp.call("tools/call", {"name": "start_thread", "arguments": {
        "scope": ["77.99"], "topic": "nomatch", "message": "x"}})
    r = mcp.call("tools/call", {"name": "list_threads", "arguments": {}})
    body = json.loads(r["result"]["content"][0]["text"])
    titles = [t["title"] for t in body["threads"]]
    assert "match" in titles
    assert "nomatch" not in titles  # subscriber tags = ["02.*"], 77.99 doesn't match
