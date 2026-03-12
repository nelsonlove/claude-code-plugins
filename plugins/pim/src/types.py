"""Object type schemas derived from the ontology."""

# Axis coordinates for each type
TYPE_AXES = {
    "note":     {"diachronic": False, "sovereign": True,  "structured": False},
    "entry":    {"diachronic": True,  "sovereign": True,  "structured": False},
    "task":     {"diachronic": True,  "sovereign": True,  "structured": True},
    "event":    {"diachronic": True,  "sovereign": False, "structured": True},
    "message":  {"diachronic": True,  "sovereign": False, "structured": False},
    "contact":  {"diachronic": False, "sovereign": False, "structured": True},
    "resource": {"diachronic": False, "sovereign": False, "structured": False},
    "topic":    {"diachronic": False, "sovereign": True,  "structured": True},
}

# Attribute schemas per type
# Each field: (type, required, enum_values_or_None)
TYPE_SCHEMAS = {
    "note": {
        "title":  ("str", False, None),
        "format": ("str", False, ("plaintext", "markdown", "richtext")),
    },
    "entry": {
        "title":     ("str", False, None),
        "format":    ("str", False, ("plaintext", "markdown", "richtext")),
        "timestamp": ("datetime", False, None),
    },
    "task": {
        "title":      ("str", True, None),
        "status":     ("str", False, ("open", "completed", "cancelled", "deferred")),
        "due_date":   ("str", False, None),
        "defer_date": ("str", False, None),
        "priority":   ("str", False, None),
        "context":    ("str", False, None),
    },
    "event": {
        "title":      ("str", True, None),
        "start":      ("str", True, None),
        "end":        ("str", False, None),
        "duration":   ("str", False, None),
        "location":   ("str", False, None),
        "recurrence": ("str", False, None),
        "status":     ("str", False, ("confirmed", "tentative", "cancelled")),
    },
    "message": {
        "subject":   ("str", False, None),
        "sent_at":   ("str", False, None),
        "channel":   ("str", False, ("email", "sms", "imessage", "chat")),
        "direction": ("str", False, ("inbound", "outbound", "draft")),
        "thread_id": ("str", False, None),
    },
    "contact": {
        "name":         ("str", True, None),
        "email":        ("str", False, None),
        "phone":        ("str", False, None),
        "address":      ("str", False, None),
        "organization": ("str", False, None),
        "role":         ("str", False, None),
    },
    "resource": {
        "uri":         ("str", True, None),
        "title":       ("str", False, None),
        "description": ("str", False, None),
        "media_type":  ("str", False, None),
        "read_status": ("str", False, ("unread", "read", "archived")),
    },
    "topic": {
        "title":       ("str", True, None),
        "description": ("str", False, None),
        "status":      ("str", False, ("active", "on_hold", "completed", "archived")),
        "taxonomy_id": ("str", False, None),
    },
}


def type_properties(obj_type: str) -> dict:
    """Return the ontology axis coordinates for a type."""
    return TYPE_AXES[obj_type]


def validate_attributes(obj_type: str, attributes: dict) -> list[str]:
    """Validate attributes against the type schema. Returns a list of error strings."""
    schema = TYPE_SCHEMAS.get(obj_type)
    if schema is None:
        return [f"Unknown type: {obj_type}"]

    errors = []
    for field, (field_type, required, enum_values) in schema.items():
        if required and field not in attributes:
            errors.append(f"Missing required field: {field}")
        if field in attributes and enum_values is not None:
            if attributes[field] not in enum_values:
                errors.append(f"Invalid value for {field}: {attributes[field]} (expected one of {enum_values})")
    return errors
