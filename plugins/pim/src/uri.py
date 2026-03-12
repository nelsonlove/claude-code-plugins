"""PIM URI generation and parsing."""

import uuid
from datetime import datetime

TYPE_PREFIXES = {
    "note": "n",
    "entry": "en",
    "task": "t",
    "event": "ev",
    "message": "m",
    "contact": "cn",
    "resource": "r",
    "topic": "top",
}


def pim_uri(obj_type: str, adapter: str, native_id: str) -> str:
    """Construct a PIM URI: pim://{type}/{adapter}/{native_id}"""
    return f"pim://{obj_type}/{adapter}/{native_id}"


def parse_uri(uri: str) -> dict:
    """Parse a PIM URI into its components."""
    if not uri.startswith("pim://"):
        raise ValueError(f"Invalid PIM URI: {uri}")
    parts = uri[len("pim://"):].split("/", 2)
    if len(parts) != 3:
        raise ValueError(f"Invalid PIM URI: {uri}")
    return {"type": parts[0], "adapter": parts[1], "native_id": parts[2]}


def generate_id(obj_type: str) -> str:
    """Generate a unique native ID for the internal adapter."""
    prefix = TYPE_PREFIXES.get(obj_type, obj_type[:3])
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    short_uuid = uuid.uuid4().hex[:8]
    return f"{prefix}-{timestamp}-{short_uuid}"
