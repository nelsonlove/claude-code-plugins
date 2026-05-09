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
