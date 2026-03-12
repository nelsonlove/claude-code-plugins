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


# --- Risk classification tests ---

def test_create_entry_is_low_risk(orch):
    """Entries are append-only, low risk."""
    risk = orch._classify_risk("create_node", obj_type="entry")
    assert risk == "low"


def test_create_task_is_medium_risk(orch):
    risk = orch._classify_risk("create_node", obj_type="task")
    assert risk == "medium"


def test_create_note_is_medium_risk(orch):
    risk = orch._classify_risk("create_node", obj_type="note")
    assert risk == "medium"


def test_create_contact_is_medium_risk(orch):
    risk = orch._classify_risk("create_node", obj_type="contact")
    assert risk == "medium"


def test_register_transition_is_low_risk(orch):
    risk = orch._classify_risk("update_register")
    assert risk == "low"


def test_associative_edge_is_low_risk(orch):
    for edge_type in ("references", "related-to", "belongs-to"):
        risk = orch._classify_risk("create_edge", changes={"type": edge_type})
        assert risk == "low", f"{edge_type} should be low risk"


def test_agency_edge_is_medium_risk(orch):
    for edge_type in ("from", "to", "involves", "delegated-to", "sent-by", "member-of"):
        risk = orch._classify_risk("create_edge", changes={"type": edge_type})
        assert risk == "medium", f"{edge_type} should be medium risk"


def test_derivation_edge_is_medium_risk(orch):
    risk = orch._classify_risk("create_edge", changes={"type": "derived-from"})
    assert risk == "medium"


def test_delete_is_high_risk(orch):
    risk = orch._classify_risk("close_node", changes={"mode": "delete"})
    assert risk == "high"


def test_body_overwrite_is_high_risk(orch):
    """Overwriting existing body content is high risk."""
    risk = orch._classify_risk("overwrite_body")
    assert risk == "high"


def test_merge_is_high_risk(orch):
    risk = orch._classify_risk("merge")
    assert risk == "high"


def test_ambiguous_resolution_is_high_risk(orch):
    risk = orch._classify_risk("ambiguous_resolution")
    assert risk == "high"


def test_update_node_is_medium_risk(orch):
    risk = orch._classify_risk("update_node", obj_type="task")
    assert risk == "medium"


def test_query_is_low_risk(orch):
    assert orch._classify_risk("query_nodes") == "low"
    assert orch._classify_risk("query_edges") == "low"


def test_complete_close_is_not_high_risk(orch):
    """Completing a node is not high risk (only delete is)."""
    risk = orch._classify_risk("close_node", changes={"mode": "complete"})
    assert risk == "medium"


def test_archive_close_is_not_high_risk(orch):
    risk = orch._classify_risk("close_node", changes={"mode": "archive"})
    assert risk == "medium"


def test_entry_creation_logged_as_low(orch):
    """Verify the actual decision log records low risk for entries."""
    node = orch.create_node("entry", {"title": "Journal"})
    log = orch.get_decision_log(target=node["id"])
    assert log[0]["risk_tier"] == "low"


def test_note_creation_logged_as_medium(orch):
    node = orch.create_node("note", {"title": "Doc"})
    log = orch.get_decision_log(target=node["id"])
    assert log[0]["risk_tier"] == "medium"
