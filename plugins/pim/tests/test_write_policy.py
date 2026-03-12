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


# --- Confirmation flow tests ---

def test_high_risk_delete_returns_confirmation_request(orch):
    """Deleting a node should return a confirmation request, not execute."""
    node = orch.create_node("note", {"title": "Important"})
    result = orch.close_node(node["id"], "delete")
    assert result["status"] == "pending_confirmation"
    assert "log_id" in result
    assert result["operation"] == "close_node"
    assert result["mode"] == "delete"
    # Node should still exist
    nodes = orch.query_nodes("note")
    assert len(nodes) == 1


def test_confirm_operation_executes_pending(orch):
    """Confirming a pending operation should execute it."""
    node = orch.create_node("note", {"title": "To delete"})
    result = orch.close_node(node["id"], "delete")
    log_id = result["log_id"]

    # Confirm the operation
    confirm_result = orch.confirm_operation(log_id)
    assert confirm_result["status"] == "confirmed"
    assert confirm_result["log_id"] == log_id

    # Now the node should be gone
    nodes = orch.query_nodes("note")
    assert len(nodes) == 0


def test_confirm_invalid_log_id_raises(orch):
    """Confirming a non-existent log_id should raise ValueError."""
    with pytest.raises(ValueError, match="No pending operation"):
        orch.confirm_operation("dl-nonexistent")


def test_confirm_already_confirmed_raises(orch):
    """Confirming an already-confirmed operation should raise ValueError."""
    node = orch.create_node("note", {"title": "To delete"})
    result = orch.close_node(node["id"], "delete")
    log_id = result["log_id"]
    orch.confirm_operation(log_id)
    # Second confirmation should fail
    with pytest.raises(ValueError, match="No pending operation"):
        orch.confirm_operation(log_id)


def test_pending_logged_as_pending_confirmation(orch):
    """The decision log should record pending_confirmation for high-risk ops."""
    node = orch.create_node("note", {"title": "Important"})
    result = orch.close_node(node["id"], "delete")
    log = orch.get_decision_log(target=node["id"], operation="close_node")
    assert len(log) == 1
    assert log[0]["approval"] == "pending_confirmation"
    assert log[0]["risk_tier"] == "high"


def test_confirmed_log_updated(orch):
    """After confirmation, the decision log should show 'confirmed'."""
    node = orch.create_node("note", {"title": "To delete"})
    result = orch.close_node(node["id"], "delete")
    orch.confirm_operation(result["log_id"])
    log = orch.get_decision_log(target=node["id"], operation="close_node")
    assert log[0]["approval"] == "confirmed"


def test_low_risk_operations_execute_immediately(orch):
    """Low risk ops should not require confirmation."""
    node = orch.create_node("entry", {"title": "Journal"})
    assert node["type"] == "entry"
    # Should execute without pending


def test_medium_risk_operations_execute_immediately(orch):
    """Medium risk ops execute after validation (no user confirmation)."""
    node = orch.create_node("task", {"title": "Do thing", "status": "open"})
    assert node["type"] == "task"


def test_non_delete_close_executes_immediately(orch):
    """Non-delete close modes should execute immediately (medium risk)."""
    node = orch.create_node("task", {"title": "Done", "status": "open"})
    result = orch.close_node(node["id"], "complete")
    assert result is None  # No confirmation needed
    nodes = orch.query_nodes("task", {"register": "log"})
    assert len(nodes) == 1
