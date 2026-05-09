"""End-to-end JSON-RPC tests against the MCP server. Spawns server.py as a
subprocess, pipes JSON-RPC messages on stdin, asserts on stdout responses."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SERVER = Path(__file__).parent.parent / "server.py"


class MCPClient:
    """Simple sync JSON-RPC client over a subprocess pipe."""

    def __init__(self, env):
        self.proc = subprocess.Popen(
            [sys.executable, str(SERVER)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env,
        )
        self._id = 0

    def call(self, method, params=None):
        self._id += 1
        msg = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            msg["params"] = params
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        return json.loads(line)

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=2)


@pytest.fixture
def mcp_client(tmp_home):
    env = os.environ.copy()
    env["HOME"] = str(tmp_home)
    client = MCPClient(env)
    yield client
    client.close()


def test_initialize(mcp_client):
    resp = mcp_client.call("initialize")
    assert resp["result"]["serverInfo"]["name"] == "claude-identity"


def test_tools_list_includes_all_expected(mcp_client):
    resp = mcp_client.call("tools/list")
    names = [t["name"] for t in resp["result"]["tools"]]
    expected = {"whoami", "list_sessions", "add_tag", "remove_tag", "list_tags", "match"}
    assert expected.issubset(set(names))


def test_add_tag_self(mcp_client, tmp_home, sample_registry_entry):
    sample_registry_entry(pid=mcp_client.proc.pid, session_id="aaaa1111-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    resp = mcp_client.call("tools/call", {"name": "add_tag", "arguments": {"tag": "02.14"}})
    text = resp["result"]["content"][0]["text"]
    body = json.loads(text)
    assert body["added"] is True
    assert "02.14" in body["tags"]


def test_list_tags_returns_current(mcp_client, tmp_home, sample_registry_entry):
    sample_registry_entry(pid=mcp_client.proc.pid, session_id="bbbb2222-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    mcp_client.call("tools/call", {"name": "add_tag", "arguments": {"tag": "x"}})
    mcp_client.call("tools/call", {"name": "add_tag", "arguments": {"tag": "y"}})
    resp = mcp_client.call("tools/call", {"name": "list_tags", "arguments": {}})
    body = json.loads(resp["result"]["content"][0]["text"])
    assert set(body["tags"]) == {"x", "y"}


def test_match_uses_implicit_handle(mcp_client, tmp_home, sample_registry_entry):
    sample_registry_entry(pid=mcp_client.proc.pid,
                          session_id="cccc3333-cccc-cccc-cccc-cccccccccccc",
                          name="fern")
    # No tags; matching on handle alone
    resp = mcp_client.call("tools/call", {"name": "match", "arguments": {"scope": ["fern"]}})
    body = json.loads(resp["result"]["content"][0]["text"])
    assert body["matches"] is True


def test_match_no_match(mcp_client, tmp_home, sample_registry_entry):
    sample_registry_entry(pid=mcp_client.proc.pid,
                          session_id="dddd4444-dddd-dddd-dddd-dddddddddddd",
                          name="alice")
    resp = mcp_client.call("tools/call", {"name": "match", "arguments": {"scope": ["bob"]}})
    body = json.loads(resp["result"]["content"][0]["text"])
    assert body["matches"] is False


def test_unknown_session_returns_error(mcp_client):
    resp = mcp_client.call("tools/call", {
        "name": "list_tags", "arguments": {"session_id": "nonexistent"}
    })
    assert "error" in resp
