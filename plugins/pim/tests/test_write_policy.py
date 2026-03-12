# tests/test_write_policy.py
"""Tests for Tier 2: write policy enforcement — input validation, risk classification, confirmation flow."""

import pytest
from src.db import init_db
from src.adapters.internal import InternalAdapter
from src.orchestrator import Orchestrator


@pytest.fixture
def orch(tmp_data_dir):
    conn = init_db(tmp_data_dir / "pim.db")
    internal = InternalAdapter(conn, tmp_data_dir)
    return Orchestrator(conn=conn, internal_adapter=internal, data_dir=tmp_data_dir)


# --- Input validation tests ---

def test_invalid_type_rejected(orch):
    """Invalid object type should raise ValueError."""
    with pytest.raises(ValueError, match="Invalid type"):
        orch.create_node("invalid_type", {"title": "Bad"})


def test_invalid_type_in_query_rejected(orch):
    with pytest.raises(ValueError, match="Invalid type"):
        orch.query_nodes("bogus")


def test_invalid_register_rejected(orch):
    with pytest.raises(ValueError, match="Invalid register"):
        orch.create_node("note", {"title": "Bad"}, register="nonexistent")


def test_invalid_register_in_update_rejected(orch):
    node = orch.create_node("note", {"title": "Test"})
    with pytest.raises(ValueError, match="Invalid register"):
        orch.update_node(node["id"], {"register": "nonexistent"})


def test_invalid_close_mode_rejected(orch):
    node = orch.create_node("note", {"title": "Test"})
    with pytest.raises(ValueError, match="Invalid mode"):
        orch.close_node(node["id"], "explode")


def test_invalid_edge_type_rejected(orch):
    n1 = orch.create_node("note", {"title": "A"})
    n2 = orch.create_node("note", {"title": "B"})
    with pytest.raises(ValueError, match="Invalid edge_type"):
        orch.create_edge(n1["id"], n2["id"], "made-up-relation")


def test_valid_types_accepted(orch):
    """All 8 object types should be accepted."""
    for t in ("note", "entry", "task", "event", "message", "contact", "resource", "topic"):
        attrs = {"title": f"Test {t}"}
        if t == "task":
            attrs["status"] = "open"
        elif t == "topic":
            attrs["status"] = "active"
        node = orch.create_node(t, attrs)
        assert node["type"] == t


def test_valid_registers_accepted(orch):
    """All 4 registers should be accepted."""
    for reg in ("scratch", "working", "reference", "log"):
        node = orch.create_node("note", {"title": f"In {reg}"}, register=reg)
        assert node["register"] == reg


def test_valid_close_modes_accepted(orch):
    """All 4 close modes should be accepted without ValueError."""
    for mode in ("complete", "archive", "cancel"):
        node = orch.create_node("note", {"title": f"Close {mode}"})
        orch.close_node(node["id"], mode)


def test_valid_edge_types_accepted(orch):
    """All relation types should be accepted."""
    from src.constants import RELATION_TYPES
    n1 = orch.create_node("note", {"title": "Source"})
    n2 = orch.create_node("note", {"title": "Target"})
    for rt in RELATION_TYPES:
        edge = orch.create_edge(n1["id"], n2["id"], rt)
        assert edge["type"] == rt
