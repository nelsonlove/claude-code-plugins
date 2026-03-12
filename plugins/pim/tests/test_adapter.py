# tests/test_adapter.py
from src.adapter import Adapter
import pytest

def test_adapter_is_abstract():
    with pytest.raises(TypeError):
        Adapter()

def test_adapter_contract_methods():
    """Verify the adapter ABC defines all contract methods."""
    abstract_methods = Adapter.__abstractmethods__
    expected = {
        "resolve", "reverse_resolve", "enumerate", "create_node",
        "query_nodes", "update_node", "close_node", "sync", "fetch_body",
    }
    assert expected.issubset(abstract_methods)
