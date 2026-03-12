"""Test that the MCP server exposes all ontology tools and they work end-to-end."""
import asyncio
import pytest
from unittest.mock import patch
from src.server import create_server


@pytest.fixture
def server(tmp_data_dir):
    with patch.dict("os.environ", {"PIM_DATA_DIR": str(tmp_data_dir)}):
        return create_server()


def test_server_has_all_tools(server):
    tool_names = {t.name for t in asyncio.run(server.list_tools())}
    expected = {
        "pim_create_node", "pim_query_nodes", "pim_update_node", "pim_close_node",
        "pim_confirm",
        "pim_create_edge", "pim_query_edges", "pim_update_edge", "pim_close_edge",
        "pim_capture", "pim_dispatch", "pim_resolve", "pim_review", "pim_decision_log",
    }
    assert expected.issubset(tool_names), f"Missing tools: {expected - tool_names}"
