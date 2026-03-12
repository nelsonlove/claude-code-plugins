from src.types import TYPE_SCHEMAS, validate_attributes, type_properties

def test_all_eight_types_defined():
    expected = {"note", "entry", "task", "event", "message", "contact", "resource", "topic"}
    assert set(TYPE_SCHEMAS.keys()) == expected

def test_type_properties():
    props = type_properties("task")
    assert props["diachronic"] is True
    assert props["sovereign"] is True
    assert props["structured"] is True

    props = type_properties("note")
    assert props["diachronic"] is False
    assert props["sovereign"] is True
    assert props["structured"] is False

def test_validate_attributes_valid():
    errors = validate_attributes("task", {"title": "Buy milk", "status": "open"})
    assert errors == []

def test_validate_attributes_missing_required():
    errors = validate_attributes("task", {})
    assert any("title" in e for e in errors)

def test_validate_attributes_invalid_enum():
    errors = validate_attributes("task", {"title": "Buy milk", "status": "exploded"})
    assert any("status" in e for e in errors)

def test_validate_attributes_optional_fields_ok():
    errors = validate_attributes("task", {"title": "Buy milk", "status": "open", "due_date": "2026-03-15"})
    assert errors == []
