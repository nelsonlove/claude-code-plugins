# PIM Tier 1: Foundation — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a functional PIM graph with internal storage, exposing ontology-derived tools via a single MCP server.

**Architecture:** One Python MCP server (`server.py`) backed by SQLite. An internal adapter handles all 8 types and 4 registers. The adapter contract (from `docs/architecture.md`) is implemented as a Python ABC. The MCP server exposes 13 tools matching the ontology's 10 operations + 3 convenience functions.

**Tech Stack:** Python 3.11+, `fastmcp`, `sqlite3` (stdlib), `pytest`

**Reference docs (read these before starting):**
- `docs/ontology.md` — Part III (type schemas), Part IV (registers), Part V (relations)
- `docs/architecture.md` — Data Model section (schema, addressing, FTS), Tool Interface section
- `docs/2026-03-12-pim-design.md` — Implementation decisions, XDG paths

---

## Task 1: Plugin Scaffold

**Files:**
- Create: `plugin.json`
- Create: `.mcp.json`
- Create: `requirements.txt`
- Create: `src/__init__.py`
- Create: `src/constants.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Step 1: Create plugin manifest**

```json
// plugin.json
{
  "name": "pim",
  "version": "0.1.0",
  "description": "Personal information management — unified graph across notes, tasks, calendar, email, contacts, and more.",
  "author": {
    "name": "Nelson Love"
  },
  "repository": "https://github.com/nelsonlove/claude-code-plugins",
  "license": "MIT",
  "keywords": ["pim", "gtd", "notes", "tasks", "calendar", "contacts", "graph"]
}
```

**Step 2: Create MCP server declaration**

```json
// .mcp.json
{
  "mcpServers": {
    "pim": {
      "command": "python3",
      "args": ["-m", "src.server"],
      "cwd": "${CLAUDE_PLUGIN_ROOT}",
      "env": {
        "PIM_DATA_DIR": "~/.local/share/pim"
      }
    }
  }
}
```

**Step 3: Create requirements.txt**

```
fastmcp>=2.0.0
pytest>=8.0.0
```

**Step 4: Create constants**

```python
# src/constants.py
from pathlib import Path
import os

DATA_DIR = Path(os.environ.get("PIM_DATA_DIR", "~/.local/share/pim")).expanduser()
DB_PATH = DATA_DIR / "pim.db"
BLOBS_DIR = DATA_DIR / "blobs"
BACKUPS_DIR = DATA_DIR / "backups"

OBJECT_TYPES = ("note", "entry", "task", "event", "message", "contact", "resource", "topic")

REGISTERS = ("scratch", "working", "reference", "log")

RELATION_TYPES = (
    # Structural
    "belongs-to",
    # Agency
    "from", "to", "involves", "delegated-to", "sent-by", "member-of",
    # Derivation
    "derived-from",
    # Temporal
    "precedes", "occurs-during",
    # Annotation
    "annotation-of",
    # Generic
    "references", "related-to",
    # Domain-specific
    "blocks",
)

CLOSE_MODES = ("complete", "archive", "cancel", "delete")

# Write policy risk tiers
RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"

# Body externalization threshold
BODY_SIZE_THRESHOLD = 100_000  # 100KB
```

**Step 5: Create test conftest**

```python
# tests/conftest.py
import os
import tempfile
import pytest

@pytest.fixture
def tmp_data_dir(tmp_path):
    """Provide a temporary PIM data directory."""
    os.environ["PIM_DATA_DIR"] = str(tmp_path)
    yield tmp_path
    del os.environ["PIM_DATA_DIR"]
```

**Step 6: Create `__init__.py` files**

Empty files: `src/__init__.py`, `tests/__init__.py`

**Step 7: Install deps and verify**

Run: `cd ~/repos/claude-code-plugins/plugins/pim && pip install -r requirements.txt`
Expected: success

**Step 8: Commit**

```bash
git add plugin.json .mcp.json requirements.txt src/ tests/
git commit -m "feat(pim): scaffold plugin with manifest, MCP config, and constants"
```

---

## Task 2: SQLite Schema and Database Initialization

**Files:**
- Create: `src/db.py`
- Create: `tests/test_db.py`

**Step 1: Write the failing test**

```python
# tests/test_db.py
import sqlite3
from src.db import init_db

def test_init_db_creates_tables(tmp_data_dir):
    db_path = tmp_data_dir / "pim.db"
    conn = init_db(db_path)

    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]

    assert "nodes" in tables
    assert "edges" in tables
    assert "decision_log" in tables

def test_init_db_creates_fts(tmp_data_dir):
    db_path = tmp_data_dir / "pim.db"
    conn = init_db(db_path)

    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='nodes_fts'")
    assert cursor.fetchone() is not None

def test_init_db_creates_indexes(tmp_data_dir):
    db_path = tmp_data_dir / "pim.db"
    conn = init_db(db_path)

    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
    indexes = [row[0] for row in cursor.fetchall()]

    assert "idx_nodes_type" in indexes
    assert "idx_nodes_register" in indexes
    assert "idx_edges_source" in indexes
    assert "idx_edges_target" in indexes
    assert "idx_edges_type" in indexes

def test_init_db_idempotent(tmp_data_dir):
    db_path = tmp_data_dir / "pim.db"
    conn1 = init_db(db_path)
    conn1.execute("INSERT INTO nodes (id, type, adapter, attributes) VALUES ('pim://note/internal/test-1', 'note', 'internal', '{}')")
    conn1.commit()
    conn1.close()

    conn2 = init_db(db_path)
    cursor = conn2.execute("SELECT id FROM nodes")
    assert cursor.fetchone() is not None
```

**Step 2: Run test to verify it fails**

Run: `cd ~/repos/claude-code-plugins/plugins/pim && python -m pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.db'`

**Step 3: Write implementation**

```python
# src/db.py
"""PIM database initialization and connection management."""

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id              TEXT PRIMARY KEY,
    type            TEXT NOT NULL,
    register        TEXT NOT NULL DEFAULT 'scratch',
    adapter         TEXT NOT NULL DEFAULT 'internal',
    native_id       TEXT,
    attributes      JSON NOT NULL DEFAULT '{}',
    body            TEXT,
    body_path       TEXT,
    source_op       TEXT,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS edges (
    id          TEXT PRIMARY KEY,
    source      TEXT NOT NULL REFERENCES nodes(id),
    target      TEXT NOT NULL REFERENCES nodes(id),
    type        TEXT NOT NULL,
    metadata    JSON DEFAULT '{}',
    source_op   TEXT,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS decision_log (
    id                  TEXT PRIMARY KEY,
    timestamp           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    operation           TEXT NOT NULL,
    target              TEXT,
    risk_tier           TEXT NOT NULL,
    approval            TEXT NOT NULL DEFAULT 'automatic',
    evidence            JSON,
    candidates          JSON,
    resolution          TEXT,
    reversible          BOOLEAN DEFAULT TRUE,
    reversed            BOOLEAN DEFAULT FALSE,
    reversed_by         TEXT
);

CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
CREATE INDEX IF NOT EXISTS idx_nodes_register ON nodes(register);
CREATE INDEX IF NOT EXISTS idx_nodes_adapter ON nodes(adapter);
CREATE INDEX IF NOT EXISTS idx_nodes_modified ON nodes(modified_at);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target);
CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(type);
CREATE INDEX IF NOT EXISTS idx_edges_source_type ON edges(source, type);
CREATE INDEX IF NOT EXISTS idx_edges_target_type ON edges(target, type);
CREATE INDEX IF NOT EXISTS idx_decision_log_target ON decision_log(target);
CREATE INDEX IF NOT EXISTS idx_decision_log_operation ON decision_log(operation);

CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
    id, type, attributes, body,
    content='nodes', content_rowid='rowid'
);
"""

# FTS triggers to keep nodes_fts in sync with nodes table
FTS_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS nodes_fts_insert AFTER INSERT ON nodes BEGIN
    INSERT INTO nodes_fts(rowid, id, type, attributes, body)
    VALUES (new.rowid, new.id, new.type, new.attributes, new.body);
END;

CREATE TRIGGER IF NOT EXISTS nodes_fts_delete BEFORE DELETE ON nodes BEGIN
    INSERT INTO nodes_fts(nodes_fts, rowid, id, type, attributes, body)
    VALUES('delete', old.rowid, old.id, old.type, old.attributes, old.body);
END;

CREATE TRIGGER IF NOT EXISTS nodes_fts_update AFTER UPDATE ON nodes BEGIN
    INSERT INTO nodes_fts(nodes_fts, rowid, id, type, attributes, body)
    VALUES('delete', old.rowid, old.id, old.type, old.attributes, old.body);
    INSERT INTO nodes_fts(rowid, id, type, attributes, body)
    VALUES (new.rowid, new.id, new.type, new.attributes, new.body);
END;
"""


def init_db(db_path: Path) -> sqlite3.Connection:
    """Initialize the PIM database, creating tables if needed. Returns a connection."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.executescript(FTS_TRIGGERS)
    return conn
```

**Step 4: Run test to verify it passes**

Run: `cd ~/repos/claude-code-plugins/plugins/pim && python -m pytest tests/test_db.py -v`
Expected: all 4 tests PASS

**Step 5: Commit**

```bash
git add src/db.py tests/test_db.py
git commit -m "feat(pim): SQLite schema with nodes, edges, decision_log, and FTS"
```

---

## Task 3: PIM URI Generation and Parsing

**Files:**
- Create: `src/uri.py`
- Create: `tests/test_uri.py`

**Step 1: Write the failing tests**

```python
# tests/test_uri.py
from src.uri import pim_uri, parse_uri, generate_id

def test_pim_uri_format():
    uri = pim_uri("note", "internal", "n-001")
    assert uri == "pim://note/internal/n-001"

def test_pim_uri_with_adapter():
    uri = pim_uri("task", "omnifocus", "hLarPeCbbib")
    assert uri == "pim://task/omnifocus/hLarPeCbbib"

def test_parse_uri():
    parts = parse_uri("pim://message/himalaya/acct1-inbox-4527")
    assert parts == {"type": "message", "adapter": "himalaya", "native_id": "acct1-inbox-4527"}

def test_parse_uri_invalid():
    import pytest
    with pytest.raises(ValueError):
        parse_uri("not-a-pim-uri")

def test_generate_id_unique():
    id1 = generate_id("note")
    id2 = generate_id("note")
    assert id1 != id2
    assert id1.startswith("n-")

def test_generate_id_prefixes():
    assert generate_id("note").startswith("n-")
    assert generate_id("entry").startswith("en-")
    assert generate_id("task").startswith("t-")
    assert generate_id("event").startswith("ev-")
    assert generate_id("message").startswith("m-")
    assert generate_id("contact").startswith("cn-")
    assert generate_id("resource").startswith("r-")
    assert generate_id("topic").startswith("top-")
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_uri.py -v`
Expected: FAIL

**Step 3: Write implementation**

```python
# src/uri.py
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
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_uri.py -v`
Expected: all 6 tests PASS

**Step 5: Commit**

```bash
git add src/uri.py tests/test_uri.py
git commit -m "feat(pim): PIM URI generation and parsing"
```

---

## Task 4: Type Schemas

**Files:**
- Create: `src/types.py`
- Create: `tests/test_types.py`

**Step 1: Write the failing tests**

```python
# tests/test_types.py
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
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_types.py -v`
Expected: FAIL

**Step 3: Write implementation**

```python
# src/types.py
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
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_types.py -v`
Expected: all 6 tests PASS

**Step 5: Commit**

```bash
git add src/types.py tests/test_types.py
git commit -m "feat(pim): type schemas with axis coordinates and attribute validation"
```

---

## Task 5: Adapter Base Class (ABC)

**Files:**
- Create: `src/adapter.py`
- Create: `tests/test_adapter.py`

**Step 1: Write the failing tests**

```python
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
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_adapter.py -v`
Expected: FAIL

**Step 3: Write implementation**

```python
# src/adapter.py
"""Adapter base class — the contract every adapter implements."""

from abc import ABC, abstractmethod
from typing import Any


class Node(dict):
    """A node returned by an adapter. Dict-like with convenience accessors."""
    @property
    def id(self): return self["id"]
    @property
    def type(self): return self["type"]


class Edge(dict):
    """An edge returned by an adapter."""
    @property
    def id(self): return self["id"]


class SyncResult(dict):
    """Result of a sync operation."""
    pass


class Adapter(ABC):
    """
    Base class for PIM adapters.

    Every adapter covers one or more object types. The orchestrator routes
    operations to adapters based on the routing table.

    See docs/architecture.md "Adapter Contract" for the full specification.
    """

    adapter_id: str = "base"
    supported_types: tuple[str, ...] = ()
    supported_operations: tuple[str, ...] = ()
    supported_registers: tuple[str, ...] = ()

    @abstractmethod
    def resolve(self, native_id: str) -> Node | None:
        """Given a native ID, return the node with attributes."""
        ...

    @abstractmethod
    def reverse_resolve(self, pim_uri: str) -> str | None:
        """Given a PIM URI, return the native ID."""
        ...

    @abstractmethod
    def enumerate(self, obj_type: str, filters: dict | None = None, limit: int = 100, offset: int = 0) -> list[Node]:
        """List all nodes of a type, with optional filters and pagination."""
        ...

    @abstractmethod
    def create_node(self, obj_type: str, attributes: dict, body: str | None = None) -> Node:
        """Create a new node. Returns the created node with its native_id."""
        ...

    @abstractmethod
    def query_nodes(self, obj_type: str, filters: dict | None = None) -> list[Node]:
        """Find nodes by type and filters (attributes, text search, etc.)."""
        ...

    @abstractmethod
    def update_node(self, native_id: str, changes: dict) -> Node:
        """Update a node's attributes or body."""
        ...

    @abstractmethod
    def close_node(self, native_id: str, mode: str) -> None:
        """Close a node (complete, archive, cancel, delete)."""
        ...

    @abstractmethod
    def sync(self, since: str | None = None) -> SyncResult:
        """Return changed nodes since the given timestamp. For index building."""
        ...

    @abstractmethod
    def fetch_body(self, native_id: str) -> str | None:
        """Fetch the full content body for an unstructured node."""
        ...

    # Optional — not all adapters support these
    def create_edge(self, source: str, target: str, edge_type: str, metadata: dict | None = None) -> Edge | None:
        return None

    def query_edges(self, node_id: str, direction: str = "both", edge_type: str | None = None) -> list[Edge]:
        return []

    def update_edge(self, edge_id: str, changes: dict) -> Edge | None:
        return None

    def close_edge(self, edge_id: str) -> None:
        pass

    def dispatch(self, native_id: str, method: str | None = None, params: dict | None = None) -> Any:
        raise NotImplementedError(f"{self.adapter_id} does not support dispatch")

    def health_check(self) -> bool:
        """Return True if the adapter is operational."""
        return True
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_adapter.py -v`
Expected: all 2 tests PASS

**Step 5: Commit**

```bash
git add src/adapter.py tests/test_adapter.py
git commit -m "feat(pim): adapter ABC with full contract from architecture doc"
```

---

## Task 6: Internal Adapter

**Files:**
- Create: `src/adapters/__init__.py`
- Create: `src/adapters/internal.py`
- Create: `tests/test_internal_adapter.py`

**Step 1: Write the failing tests**

```python
# tests/test_internal_adapter.py
import pytest
from src.db import init_db
from src.adapters.internal import InternalAdapter

@pytest.fixture
def adapter(tmp_data_dir):
    db_path = tmp_data_dir / "pim.db"
    conn = init_db(db_path)
    return InternalAdapter(conn, tmp_data_dir)

def test_create_node(adapter):
    node = adapter.create_node("note", {"title": "Test note"}, body="Hello world")
    assert node["type"] == "note"
    assert node["attributes"]["title"] == "Test note"
    assert node["id"].startswith("pim://note/internal/")

def test_query_nodes_by_type(adapter):
    adapter.create_node("note", {"title": "Note 1"})
    adapter.create_node("note", {"title": "Note 2"})
    adapter.create_node("task", {"title": "Task 1", "status": "open"})

    notes = adapter.query_nodes("note")
    assert len(notes) == 2
    tasks = adapter.query_nodes("task")
    assert len(tasks) == 1

def test_query_nodes_text_search(adapter):
    adapter.create_node("note", {"title": "Quantum physics"}, body="Schrodinger's cat is both alive and dead")
    adapter.create_node("note", {"title": "Grocery list"}, body="Buy milk and eggs")

    results = adapter.query_nodes("note", {"text_search": "quantum"})
    assert len(results) == 1
    assert results[0]["attributes"]["title"] == "Quantum physics"

def test_update_node(adapter):
    node = adapter.create_node("task", {"title": "Old title", "status": "open"})
    native_id = node["native_id"]

    updated = adapter.update_node(native_id, {"attributes": {"title": "New title"}})
    assert updated["attributes"]["title"] == "New title"

def test_close_node_delete(adapter):
    node = adapter.create_node("note", {"title": "Doomed"})
    native_id = node["native_id"]

    adapter.close_node(native_id, "delete")
    results = adapter.query_nodes("note")
    assert len(results) == 0

def test_resolve_and_reverse_resolve(adapter):
    node = adapter.create_node("contact", {"name": "Sarah Chen"})
    native_id = node["native_id"]
    pim_id = node["id"]

    resolved = adapter.resolve(native_id)
    assert resolved["id"] == pim_id

    reverse = adapter.reverse_resolve(pim_id)
    assert reverse == native_id

def test_fetch_body(adapter):
    node = adapter.create_node("note", {"title": "Test"}, body="The body content")
    body = adapter.fetch_body(node["native_id"])
    assert body == "The body content"

def test_body_externalization(adapter):
    big_body = "x" * 200_000  # over 100KB threshold
    node = adapter.create_node("note", {"title": "Big"}, body=big_body)
    assert node.get("body_path") is not None
    fetched = adapter.fetch_body(node["native_id"])
    assert fetched == big_body

def test_enumerate(adapter):
    for i in range(5):
        adapter.create_node("note", {"title": f"Note {i}"})
    page = adapter.enumerate("note", limit=3, offset=0)
    assert len(page) == 3
    page2 = adapter.enumerate("note", limit=3, offset=3)
    assert len(page2) == 2

def test_register_default_scratch(adapter):
    node = adapter.create_node("note", {"title": "New"})
    assert node["register"] == "scratch"

def test_update_register(adapter):
    node = adapter.create_node("note", {"title": "New"})
    updated = adapter.update_node(node["native_id"], {"register": "working"})
    assert updated["register"] == "working"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_internal_adapter.py -v`
Expected: FAIL

**Step 3: Write implementation**

```python
# src/adapters/__init__.py
```

```python
# src/adapters/internal.py
"""Internal adapter — SQLite-backed storage for all 8 types."""

import json
import sqlite3
from pathlib import Path

from src.adapter import Adapter, Node, Edge, SyncResult
from src.uri import pim_uri, parse_uri, generate_id
from src.constants import OBJECT_TYPES, REGISTERS, BODY_SIZE_THRESHOLD


class InternalAdapter(Adapter):
    adapter_id = "internal"
    supported_types = OBJECT_TYPES
    supported_operations = ("create", "query", "update", "close")
    supported_registers = REGISTERS

    def __init__(self, conn: sqlite3.Connection, data_dir: Path):
        self.conn = conn
        self.data_dir = data_dir
        self.blobs_dir = data_dir / "blobs"

    def resolve(self, native_id: str) -> Node | None:
        row = self.conn.execute(
            "SELECT * FROM nodes WHERE native_id = ?", (native_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_node(row)

    def reverse_resolve(self, uri: str) -> str | None:
        row = self.conn.execute(
            "SELECT native_id FROM nodes WHERE id = ?", (uri,)
        ).fetchone()
        return row["native_id"] if row else None

    def enumerate(self, obj_type: str, filters: dict | None = None, limit: int = 100, offset: int = 0) -> list[Node]:
        rows = self.conn.execute(
            "SELECT * FROM nodes WHERE type = ? AND adapter = 'internal' ORDER BY modified_at DESC LIMIT ? OFFSET ?",
            (obj_type, limit, offset)
        ).fetchall()
        return [self._row_to_node(r) for r in rows]

    def create_node(self, obj_type: str, attributes: dict, body: str | None = None) -> Node:
        native_id = generate_id(obj_type)
        uri = pim_uri(obj_type, "internal", native_id)

        body_field = None
        body_path = None
        if body is not None:
            if len(body.encode("utf-8")) > BODY_SIZE_THRESHOLD:
                self.blobs_dir.mkdir(parents=True, exist_ok=True)
                blob_path = self.blobs_dir / native_id
                blob_path.write_text(body, encoding="utf-8")
                body_path = str(blob_path)
            else:
                body_field = body

        self.conn.execute(
            """INSERT INTO nodes (id, type, register, adapter, native_id, attributes, body, body_path)
               VALUES (?, ?, 'scratch', 'internal', ?, ?, ?, ?)""",
            (uri, obj_type, native_id, json.dumps(attributes), body_field, body_path)
        )
        self.conn.commit()

        return self.resolve(native_id)

    def query_nodes(self, obj_type: str, filters: dict | None = None) -> list[Node]:
        filters = filters or {}
        text_search = filters.pop("text_search", None)

        if text_search:
            rows = self.conn.execute(
                """SELECT nodes.* FROM nodes
                   JOIN nodes_fts ON nodes.rowid = nodes_fts.rowid
                   WHERE nodes.type = ? AND nodes.adapter = 'internal'
                   AND nodes_fts MATCH ?
                   ORDER BY rank""",
                (obj_type, text_search)
            ).fetchall()
        else:
            query = "SELECT * FROM nodes WHERE type = ? AND adapter = 'internal'"
            params: list = [obj_type]

            if "register" in filters:
                query += " AND register = ?"
                params.append(filters["register"])

            if "attributes" in filters:
                for key, value in filters["attributes"].items():
                    query += " AND json_extract(attributes, ?) = ?"
                    params.extend([f"$.{key}", value])

            query += " ORDER BY modified_at DESC"

            if "limit" in filters:
                query += " LIMIT ?"
                params.append(filters["limit"])

            rows = self.conn.execute(query, params).fetchall()

        return [self._row_to_node(r) for r in rows]

    def update_node(self, native_id: str, changes: dict) -> Node:
        node = self.resolve(native_id)
        if node is None:
            raise ValueError(f"Node not found: {native_id}")

        if "attributes" in changes:
            current_attrs = node["attributes"]
            current_attrs.update(changes["attributes"])
            self.conn.execute(
                "UPDATE nodes SET attributes = ?, modified_at = CURRENT_TIMESTAMP WHERE native_id = ?",
                (json.dumps(current_attrs), native_id)
            )

        if "register" in changes:
            self.conn.execute(
                "UPDATE nodes SET register = ?, modified_at = CURRENT_TIMESTAMP WHERE native_id = ?",
                (changes["register"], native_id)
            )

        if "body" in changes:
            body = changes["body"]
            if len(body.encode("utf-8")) > BODY_SIZE_THRESHOLD:
                self.blobs_dir.mkdir(parents=True, exist_ok=True)
                blob_path = self.blobs_dir / native_id
                blob_path.write_text(body, encoding="utf-8")
                self.conn.execute(
                    "UPDATE nodes SET body = NULL, body_path = ?, modified_at = CURRENT_TIMESTAMP WHERE native_id = ?",
                    (str(blob_path), native_id)
                )
            else:
                self.conn.execute(
                    "UPDATE nodes SET body = ?, body_path = NULL, modified_at = CURRENT_TIMESTAMP WHERE native_id = ?",
                    (body, native_id)
                )

        self.conn.commit()
        return self.resolve(native_id)

    def close_node(self, native_id: str, mode: str) -> None:
        node = self.resolve(native_id)
        if node is None:
            raise ValueError(f"Node not found: {native_id}")

        if mode == "delete":
            # Clean up edges
            uri = node["id"]
            self.conn.execute("DELETE FROM edges WHERE source = ? OR target = ?", (uri, uri))
            # Clean up blob
            if node.get("body_path"):
                blob = Path(node["body_path"])
                if blob.exists():
                    blob.unlink()
            self.conn.execute("DELETE FROM nodes WHERE native_id = ?", (native_id,))
        elif mode == "complete":
            self.conn.execute(
                "UPDATE nodes SET register = 'log', modified_at = CURRENT_TIMESTAMP WHERE native_id = ?",
                (native_id,)
            )
            attrs = node["attributes"]
            if "status" in attrs:
                attrs["status"] = "completed"
                self.conn.execute(
                    "UPDATE nodes SET attributes = ? WHERE native_id = ?",
                    (json.dumps(attrs), native_id)
                )
        elif mode == "archive":
            self.conn.execute(
                "UPDATE nodes SET register = 'reference', modified_at = CURRENT_TIMESTAMP WHERE native_id = ?",
                (native_id,)
            )
        elif mode == "cancel":
            self.conn.execute(
                "UPDATE nodes SET register = 'log', modified_at = CURRENT_TIMESTAMP WHERE native_id = ?",
                (native_id,)
            )
            attrs = node["attributes"]
            if "status" in attrs:
                attrs["status"] = "cancelled"
                self.conn.execute(
                    "UPDATE nodes SET attributes = ? WHERE native_id = ?",
                    (json.dumps(attrs), native_id)
                )

        self.conn.commit()

    def sync(self, since: str | None = None) -> SyncResult:
        # Internal adapter is always in sync — no-op
        return SyncResult({"changed_nodes": [], "changed_edges": []})

    def fetch_body(self, native_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT body, body_path FROM nodes WHERE native_id = ?", (native_id,)
        ).fetchone()
        if row is None:
            return None
        if row["body_path"]:
            return Path(row["body_path"]).read_text(encoding="utf-8")
        return row["body"]

    def _row_to_node(self, row: sqlite3.Row) -> Node:
        return Node({
            "id": row["id"],
            "type": row["type"],
            "register": row["register"],
            "adapter": row["adapter"],
            "native_id": row["native_id"],
            "attributes": json.loads(row["attributes"]),
            "body": row["body"],
            "body_path": row["body_path"],
            "source_op": row["source_op"],
            "created_at": row["created_at"],
            "modified_at": row["modified_at"],
        })
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_internal_adapter.py -v`
Expected: all 12 tests PASS

**Step 5: Commit**

```bash
git add src/adapters/ tests/test_internal_adapter.py
git commit -m "feat(pim): internal adapter — full CRUD, FTS, body externalization"
```

---

## Task 7: Edge Operations on Internal Adapter

**Files:**
- Modify: `src/adapters/internal.py`
- Create: `tests/test_internal_edges.py`

**Step 1: Write the failing tests**

```python
# tests/test_internal_edges.py
import pytest
from src.db import init_db
from src.adapters.internal import InternalAdapter

@pytest.fixture
def adapter(tmp_data_dir):
    conn = init_db(tmp_data_dir / "pim.db")
    return InternalAdapter(conn, tmp_data_dir)

@pytest.fixture
def two_nodes(adapter):
    note = adapter.create_node("note", {"title": "Design doc"})
    topic = adapter.create_node("topic", {"title": "PIM Project", "status": "active"})
    return note, topic

def test_create_edge(adapter, two_nodes):
    note, topic = two_nodes
    edge = adapter.create_edge(note["id"], topic["id"], "belongs-to")
    assert edge is not None
    assert edge["source"] == note["id"]
    assert edge["target"] == topic["id"]
    assert edge["type"] == "belongs-to"

def test_query_edges_outbound(adapter, two_nodes):
    note, topic = two_nodes
    adapter.create_edge(note["id"], topic["id"], "belongs-to")

    edges = adapter.query_edges(note["id"], direction="outbound")
    assert len(edges) == 1
    assert edges[0]["target"] == topic["id"]

def test_query_edges_inbound(adapter, two_nodes):
    note, topic = two_nodes
    adapter.create_edge(note["id"], topic["id"], "belongs-to")

    edges = adapter.query_edges(topic["id"], direction="inbound")
    assert len(edges) == 1
    assert edges[0]["source"] == note["id"]

def test_query_edges_by_type(adapter, two_nodes):
    note, topic = two_nodes
    adapter.create_edge(note["id"], topic["id"], "belongs-to")
    adapter.create_edge(note["id"], topic["id"], "annotation-of")

    edges = adapter.query_edges(note["id"], direction="outbound", edge_type="belongs-to")
    assert len(edges) == 1

def test_close_edge(adapter, two_nodes):
    note, topic = two_nodes
    edge = adapter.create_edge(note["id"], topic["id"], "belongs-to")
    adapter.close_edge(edge["id"])

    edges = adapter.query_edges(note["id"], direction="outbound")
    assert len(edges) == 0

def test_duplicate_edge_idempotent(adapter, two_nodes):
    note, topic = two_nodes
    edge1 = adapter.create_edge(note["id"], topic["id"], "belongs-to")
    edge2 = adapter.create_edge(note["id"], topic["id"], "belongs-to")
    assert edge1["id"] == edge2["id"]  # same edge returned
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_internal_edges.py -v`
Expected: FAIL (edge methods return None/empty)

**Step 3: Add edge operations to InternalAdapter**

Add these methods to `src/adapters/internal.py` in the `InternalAdapter` class (replacing the inherited no-op defaults):

```python
    def create_edge(self, source: str, target: str, edge_type: str, metadata: dict | None = None) -> Edge:
        # Idempotent: check for existing edge with same source, target, type
        existing = self.conn.execute(
            "SELECT * FROM edges WHERE source = ? AND target = ? AND type = ?",
            (source, target, edge_type)
        ).fetchone()
        if existing:
            return self._row_to_edge(existing)

        edge_id = f"e-{generate_id('edge')}"
        self.conn.execute(
            "INSERT INTO edges (id, source, target, type, metadata) VALUES (?, ?, ?, ?, ?)",
            (edge_id, source, target, edge_type, json.dumps(metadata or {}))
        )
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM edges WHERE id = ?", (edge_id,)).fetchone()
        return self._row_to_edge(row)

    def query_edges(self, node_id: str, direction: str = "both", edge_type: str | None = None) -> list[Edge]:
        conditions = []
        params: list = []

        if direction in ("outbound", "both"):
            conditions.append("source = ?")
            params.append(node_id)
        if direction in ("inbound", "both"):
            conditions.append("target = ?")
            params.append(node_id)

        where = " OR ".join(conditions)
        if edge_type:
            where = f"({where}) AND type = ?"
            params.append(edge_type)

        rows = self.conn.execute(f"SELECT * FROM edges WHERE {where}", params).fetchall()
        return [self._row_to_edge(r) for r in rows]

    def update_edge(self, edge_id: str, changes: dict) -> Edge:
        sets = []
        params: list = []
        if "type" in changes:
            sets.append("type = ?")
            params.append(changes["type"])
        if "target" in changes:
            sets.append("target = ?")
            params.append(changes["target"])
        if "metadata" in changes:
            sets.append("metadata = ?")
            params.append(json.dumps(changes["metadata"]))
        params.append(edge_id)
        self.conn.execute(f"UPDATE edges SET {', '.join(sets)} WHERE id = ?", params)
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM edges WHERE id = ?", (edge_id,)).fetchone()
        return self._row_to_edge(row)

    def close_edge(self, edge_id: str) -> None:
        self.conn.execute("DELETE FROM edges WHERE id = ?", (edge_id,))
        self.conn.commit()

    def _row_to_edge(self, row: sqlite3.Row) -> Edge:
        return Edge({
            "id": row["id"],
            "source": row["source"],
            "target": row["target"],
            "type": row["type"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
            "source_op": row["source_op"],
            "created_at": row["created_at"],
        })
```

Also add the import for `generate_id` if not already present at the top of the file.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_internal_edges.py -v`
Expected: all 6 tests PASS

**Step 5: Commit**

```bash
git add src/adapters/internal.py tests/test_internal_edges.py
git commit -m "feat(pim): edge CRUD operations on internal adapter"
```

---

## Task 8: Orchestrator (Router + Write Policy)

**Files:**
- Create: `src/orchestrator.py`
- Create: `tests/test_orchestrator.py`

**Step 1: Write the failing tests**

```python
# tests/test_orchestrator.py
import pytest
from src.db import init_db
from src.adapters.internal import InternalAdapter
from src.orchestrator import Orchestrator

@pytest.fixture
def orchestrator(tmp_data_dir):
    conn = init_db(tmp_data_dir / "pim.db")
    internal = InternalAdapter(conn, tmp_data_dir)
    return Orchestrator(conn=conn, internal_adapter=internal, data_dir=tmp_data_dir)

def test_create_node_routes_to_internal(orchestrator):
    node = orchestrator.create_node("note", {"title": "Test"}, register="scratch")
    assert node["adapter"] == "internal"
    assert node["type"] == "note"

def test_create_node_logs_decision(orchestrator):
    node = orchestrator.create_node("note", {"title": "Test"})
    log = orchestrator.get_decision_log(target=node["id"])
    assert len(log) == 1
    assert log[0]["operation"] == "create_node"
    assert log[0]["risk_tier"] == "medium"

def test_query_nodes(orchestrator):
    orchestrator.create_node("note", {"title": "A"})
    orchestrator.create_node("note", {"title": "B"})
    orchestrator.create_node("task", {"title": "T", "status": "open"})

    notes = orchestrator.query_nodes("note")
    assert len(notes) == 2

def test_update_node(orchestrator):
    node = orchestrator.create_node("task", {"title": "Old", "status": "open"})
    updated = orchestrator.update_node(node["id"], {"attributes": {"title": "New"}})
    assert updated["attributes"]["title"] == "New"

def test_close_node(orchestrator):
    node = orchestrator.create_node("task", {"title": "Doomed", "status": "open"})
    orchestrator.close_node(node["id"], "complete")
    results = orchestrator.query_nodes("task", {"register": "log"})
    assert len(results) == 1

def test_create_edge(orchestrator):
    note = orchestrator.create_node("note", {"title": "Doc"})
    topic = orchestrator.create_node("topic", {"title": "Project", "status": "active"})
    edge = orchestrator.create_edge(note["id"], topic["id"], "belongs-to")
    assert edge["type"] == "belongs-to"

def test_query_edges(orchestrator):
    note = orchestrator.create_node("note", {"title": "Doc"})
    topic = orchestrator.create_node("topic", {"title": "Project", "status": "active"})
    orchestrator.create_edge(note["id"], topic["id"], "belongs-to")

    edges = orchestrator.query_edges(source=note["id"])
    assert len(edges) == 1

def test_register_transition_logged(orchestrator):
    node = orchestrator.create_node("note", {"title": "Test"})
    orchestrator.update_node(node["id"], {"register": "working"})
    log = orchestrator.get_decision_log(target=node["id"])
    # create + update = 2 entries
    assert len(log) == 2
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: FAIL

**Step 3: Write implementation**

```python
# src/orchestrator.py
"""Orchestrator — routes operations to adapters and enforces write policy."""

import json
import sqlite3
from pathlib import Path

from src.adapter import Adapter, Node, Edge
from src.uri import parse_uri, generate_id
from src.constants import RISK_LOW, RISK_MEDIUM, RISK_HIGH


class Orchestrator:
    """
    Central orchestration layer. Routes operations to adapters via the routing table.
    Enforces write policy and logs decisions.

    For Tier 1, only the internal adapter is available. The routing table and
    external adapter support will be added in later tiers.
    """

    def __init__(self, conn: sqlite3.Connection, internal_adapter: Adapter, data_dir: Path):
        self.conn = conn
        self.internal = internal_adapter
        self.data_dir = data_dir
        # Routing table: type -> adapter_id (or dict of register -> adapter_id)
        # For Tier 1, everything routes to internal
        self.adapters: dict[str, Adapter] = {"internal": internal_adapter}
        self.routing: dict = {}  # empty = everything falls back to internal

    def register_adapter(self, adapter: Adapter) -> None:
        """Register an external adapter."""
        self.adapters[adapter.adapter_id] = adapter

    def set_routing(self, routing: dict) -> None:
        """Set the routing table."""
        self.routing = routing

    def _resolve_adapter(self, obj_type: str, register: str = "scratch") -> Adapter:
        """Resolve which adapter handles a given type + register."""
        route = self.routing.get(obj_type)
        if route is None:
            return self.internal
        if isinstance(route, str):
            return self.adapters.get(route, self.internal)
        if isinstance(route, dict):
            adapter_id = route.get(register, "internal")
            return self.adapters.get(adapter_id, self.internal)
        return self.internal

    def _log_decision(self, operation: str, target: str | None, risk_tier: str,
                      approval: str = "automatic", evidence: dict | None = None) -> str:
        log_id = f"dl-{generate_id('log')}"
        self.conn.execute(
            """INSERT INTO decision_log (id, operation, target, risk_tier, approval, evidence)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (log_id, operation, target, risk_tier, approval, json.dumps(evidence or {}))
        )
        self.conn.commit()
        return log_id

    def _classify_risk(self, operation: str, obj_type: str | None = None, changes: dict | None = None) -> str:
        """Classify operation risk per the architecture doc's write policy."""
        # Low risk: register transitions, associative relations, read/log
        if operation == "update_register":
            return RISK_LOW
        if operation == "create_edge" and changes and changes.get("type") in ("references", "related-to", "belongs-to"):
            return RISK_LOW

        # High risk: merges, deletes, content overwrites
        if operation == "close_node" and changes and changes.get("mode") == "delete":
            return RISK_HIGH
        if operation == "merge":
            return RISK_HIGH

        # Medium: everything else (create, update, most edges)
        return RISK_MEDIUM

    # --- Node operations ---

    def create_node(self, obj_type: str, attributes: dict, body: str | None = None,
                    register: str = "scratch") -> Node:
        adapter = self._resolve_adapter(obj_type, register)
        risk = self._classify_risk("create_node", obj_type)
        node = adapter.create_node(obj_type, attributes, body)

        # Set register if not scratch
        if register != "scratch":
            adapter.update_node(node["native_id"], {"register": register})
            node = adapter.resolve(node["native_id"])

        log_id = self._log_decision("create_node", node["id"], risk)
        # Update source_op on the node
        self.conn.execute("UPDATE nodes SET source_op = ? WHERE id = ?", (log_id, node["id"]))
        self.conn.commit()

        return adapter.resolve(node["native_id"])

    def query_nodes(self, obj_type: str, filters: dict | None = None) -> list[Node]:
        filters = filters or {}
        register = filters.get("register")

        if register:
            adapter = self._resolve_adapter(obj_type, register)
            return adapter.query_nodes(obj_type, filters)
        else:
            # Fan out across all adapters that might hold this type
            # For now, just internal
            return self.internal.query_nodes(obj_type, filters)

    def update_node(self, pim_uri: str, changes: dict) -> Node:
        parts = parse_uri(pim_uri)
        adapter = self.adapters.get(parts["adapter"], self.internal)
        native_id = adapter.reverse_resolve(pim_uri)

        if "register" in changes:
            risk = self._classify_risk("update_register")
        else:
            risk = self._classify_risk("update_node", parts["type"])

        self._log_decision("update_node", pim_uri, risk, evidence={"changes": changes})
        return adapter.update_node(native_id, changes)

    def close_node(self, pim_uri: str, mode: str) -> None:
        parts = parse_uri(pim_uri)
        adapter = self.adapters.get(parts["adapter"], self.internal)
        native_id = adapter.reverse_resolve(pim_uri)
        risk = self._classify_risk("close_node", changes={"mode": mode})
        self._log_decision("close_node", pim_uri, risk, evidence={"mode": mode})
        adapter.close_node(native_id, mode)

    # --- Edge operations (always internal relation index) ---

    def create_edge(self, source: str, target: str, edge_type: str, metadata: dict | None = None) -> Edge:
        risk = self._classify_risk("create_edge", changes={"type": edge_type})
        edge = self.internal.create_edge(source, target, edge_type, metadata)
        self._log_decision("create_edge", edge["id"], risk, evidence={"source": source, "target": target, "type": edge_type})
        return edge

    def query_edges(self, source: str | None = None, target: str | None = None,
                    edge_type: str | None = None, direction: str = "both") -> list[Edge]:
        node_id = source or target
        if source and not target:
            direction = "outbound"
        elif target and not source:
            direction = "inbound"
        return self.internal.query_edges(node_id, direction, edge_type)

    def update_edge(self, edge_id: str, changes: dict) -> Edge:
        self._log_decision("update_edge", edge_id, RISK_MEDIUM, evidence={"changes": changes})
        return self.internal.update_edge(edge_id, changes)

    def close_edge(self, edge_id: str) -> None:
        self._log_decision("close_edge", edge_id, RISK_LOW)
        self.internal.close_edge(edge_id)

    # --- Decision log ---

    def get_decision_log(self, target: str | None = None, operation: str | None = None,
                         limit: int = 50) -> list[dict]:
        query = "SELECT * FROM decision_log WHERE 1=1"
        params: list = []
        if target:
            query += " AND target = ?"
            params.append(target)
        if operation:
            query += " AND operation = ?"
            params.append(operation)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: all 8 tests PASS

**Step 5: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: all tests PASS

**Step 6: Commit**

```bash
git add src/orchestrator.py tests/test_orchestrator.py
git commit -m "feat(pim): orchestrator with routing, write policy, and decision logging"
```

---

## Task 9: MCP Server with All Tools

**Files:**
- Create: `src/server.py`
- Create: `tests/test_server.py`

**Step 1: Write the failing tests**

```python
# tests/test_server.py
"""Test that the MCP server exposes all ontology tools and they work end-to-end."""
import pytest
from unittest.mock import patch
from src.server import create_server

@pytest.fixture
def server(tmp_data_dir):
    with patch.dict("os.environ", {"PIM_DATA_DIR": str(tmp_data_dir)}):
        return create_server()

def test_server_has_all_tools(server):
    tool_names = {t.name for t in server._tool_manager.list_tools()}
    expected = {
        "pim_create_node", "pim_query_nodes", "pim_update_node", "pim_close_node",
        "pim_create_edge", "pim_query_edges", "pim_update_edge", "pim_close_edge",
        "pim_capture", "pim_dispatch", "pim_resolve", "pim_review", "pim_decision_log",
    }
    assert expected.issubset(tool_names), f"Missing tools: {expected - tool_names}"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_server.py -v`
Expected: FAIL

**Step 3: Write implementation**

```python
# src/server.py
"""PIM MCP server — exposes ontology tools via FastMCP."""

import json
import os
from pathlib import Path

from fastmcp import FastMCP

from src.constants import DATA_DIR, DB_PATH, OBJECT_TYPES, REGISTERS, RELATION_TYPES, CLOSE_MODES
from src.db import init_db
from src.adapters.internal import InternalAdapter
from src.orchestrator import Orchestrator


def create_server() -> FastMCP:
    data_dir = Path(os.environ.get("PIM_DATA_DIR", str(DATA_DIR))).expanduser()
    db_path = data_dir / "pim.db"
    conn = init_db(db_path)
    internal = InternalAdapter(conn, data_dir)
    orch = Orchestrator(conn=conn, internal_adapter=internal, data_dir=data_dir)

    mcp = FastMCP(
        "PIM",
        instructions=(
            "Personal Information Management system. "
            "8 object types: note, entry, task, event, message, contact, resource, topic. "
            "4 registers: scratch (inbox), working (active), reference (filed), log (historical). "
            "Directed edges connect nodes. See docs/ontology.md for the full model."
        ),
    )

    # --- Node lifecycle tools ---

    @mcp.tool()
    def pim_create_node(
        type: str,
        attributes: dict,
        body: str | None = None,
        register: str = "scratch",
    ) -> dict:
        """Create a new node in the PIM graph.

        Args:
            type: One of: note, entry, task, event, message, contact, resource, topic
            attributes: Type-specific attributes (see ontology for schemas)
            body: Content body for unstructured types (note, entry, message, resource)
            register: Initial register: scratch, working, reference, or log
        """
        node = orch.create_node(type, attributes, body, register)
        return dict(node)

    @mcp.tool()
    def pim_query_nodes(
        type: str,
        register: str | None = None,
        attributes: dict | None = None,
        text_search: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Query nodes by type, register, attributes, or full-text search.

        Args:
            type: Object type to search
            register: Filter by register (scratch, working, reference, log)
            attributes: Filter by attribute values (e.g. {"status": "open"})
            text_search: Full-text search across attributes and body
            limit: Max results (default 20)
        """
        filters = {"limit": limit}
        if register:
            filters["register"] = register
        if attributes:
            filters["attributes"] = attributes
        if text_search:
            filters["text_search"] = text_search
        nodes = orch.query_nodes(type, filters)
        return [dict(n) for n in nodes]

    @mcp.tool()
    def pim_update_node(
        id: str,
        attributes: dict | None = None,
        body: str | None = None,
        register: str | None = None,
    ) -> dict:
        """Update a node's attributes, body, or register.

        Args:
            id: PIM URI of the node (e.g. pim://note/internal/n-20260312-abc123)
            attributes: Attribute changes to merge
            body: New body content (unstructured types only)
            register: New register (scratch, working, reference, log)
        """
        changes = {}
        if attributes:
            changes["attributes"] = attributes
        if body is not None:
            changes["body"] = body
        if register:
            changes["register"] = register
        node = orch.update_node(id, changes)
        return dict(node)

    @mcp.tool()
    def pim_close_node(
        id: str,
        mode: str = "archive",
    ) -> str:
        """Close a node — complete, archive, cancel, or delete.

        Args:
            id: PIM URI of the node
            mode: One of: complete, archive, cancel, delete
        """
        orch.close_node(id, mode)
        return f"Node {id} closed with mode: {mode}"

    # --- Edge lifecycle tools ---

    @mcp.tool()
    def pim_create_edge(
        source: str,
        target: str,
        type: str,
        metadata: dict | None = None,
    ) -> dict:
        """Create a directed edge between two nodes.

        Direction: source bears on target.
        Relation families: structural (→ topic), agency (→ contact),
        temporal (diachronic → diachronic), annotation (note/entry → any),
        derivation (any → any), generic (references, related-to).

        Args:
            source: PIM URI of the source node
            target: PIM URI of the target node
            type: Relation type (belongs-to, derived-from, from, to, involves, etc.)
            metadata: Optional key-value metadata on the edge
        """
        edge = orch.create_edge(source, target, type, metadata)
        return dict(edge)

    @mcp.tool()
    def pim_query_edges(
        source: str | None = None,
        target: str | None = None,
        type: str | None = None,
        direction: str = "both",
    ) -> list[dict]:
        """Query edges by source, target, type, or direction.

        Args:
            source: PIM URI to find outbound edges from
            target: PIM URI to find inbound edges to
            type: Filter by relation type
            direction: outbound, inbound, or both
        """
        edges = orch.query_edges(source=source, target=target, edge_type=type, direction=direction)
        return [dict(e) for e in edges]

    @mcp.tool()
    def pim_update_edge(
        id: str,
        type: str | None = None,
        target: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        """Update an edge's type, target, or metadata.

        Args:
            id: Edge ID
            type: New relation type
            target: New target PIM URI (re-file)
            metadata: New metadata to set
        """
        changes = {}
        if type:
            changes["type"] = type
        if target:
            changes["target"] = target
        if metadata:
            changes["metadata"] = metadata
        edge = orch.update_edge(id, changes)
        return dict(edge)

    @mcp.tool()
    def pim_close_edge(id: str) -> str:
        """Dissolve an edge. The nodes persist; only the connection is removed.

        Args:
            id: Edge ID
        """
        orch.close_edge(id)
        return f"Edge {id} dissolved"

    # --- Boundary tools (stubs for Tier 1) ---

    @mcp.tool()
    def pim_capture(
        input: str,
        source: str | None = None,
    ) -> dict:
        """Capture raw input — decompose into typed objects and relations.

        In Tier 1 this creates a single note in scratch. Full decomposition
        will be implemented when the agent constellation is available.

        Args:
            input: Raw content to capture
            source: Optional origin hint (email, voice, clipboard, url)
        """
        node = orch.create_node("note", {"title": f"Capture: {input[:50]}"}, body=input)
        return {"nodes_created": [node["id"]], "edges_created": [], "suggestions": []}

    @mcp.tool()
    def pim_dispatch(
        target: str,
        method: str | None = None,
        params: dict | None = None,
    ) -> dict:
        """Dispatch a node outward across the sovereignty boundary.

        Stub for Tier 1 — full dispatch requires external adapters.

        Args:
            target: PIM URI of the node to dispatch
            method: Optional dispatch method
            params: Optional dispatch parameters
        """
        return {"status": "not_implemented", "message": "Dispatch requires external adapters (Tier 3+)"}

    # --- Convenience tools ---

    @mcp.tool()
    def pim_resolve(
        type: str,
        hints: dict,
    ) -> dict:
        """Identity resolution — find an existing node matching the hints.

        Tier 1: deterministic lookup only (exact attribute match).
        Semantic search added in Tier 8.

        Args:
            type: Object type to search
            hints: Attribute hints (name, email, title, etc.)
        """
        results = orch.query_nodes(type, {"attributes": hints, "limit": 5})
        if not results:
            return {"outcome": "not_found", "candidates": []}
        if len(results) == 1:
            return {"outcome": "found", "node": dict(results[0]), "confidence": 1.0}
        return {
            "outcome": "ambiguous",
            "candidates": [dict(r) for r in results],
            "confidence": 0.5,
        }

    @mcp.tool()
    def pim_review(
        register: str | None = None,
        type: str | None = None,
        topic: str | None = None,
        contact: str | None = None,
    ) -> dict:
        """Assemble a contextual review — fan out queries across the graph.

        Args:
            register: Review a specific register (e.g. "scratch" for inbox)
            type: Filter by object type
            topic: PIM URI of a topic to review
            contact: PIM URI of a contact to review
        """
        results = {}

        if register:
            for t in OBJECT_TYPES:
                nodes = orch.query_nodes(t, {"register": register, "limit": 10})
                if nodes:
                    results[t] = [dict(n) for n in nodes]

        elif type:
            nodes = orch.query_nodes(type, {"limit": 20})
            results[type] = [dict(n) for n in nodes]

        elif topic:
            edges = orch.query_edges(target=topic, edge_type="belongs-to")
            node_ids = [e["source"] for e in edges]
            for nid in node_ids[:20]:
                from src.uri import parse_uri
                parts = parse_uri(nid)
                adapter = orch.adapters.get(parts["adapter"], orch.internal)
                native_id = adapter.reverse_resolve(nid)
                if native_id:
                    node = adapter.resolve(native_id)
                    if node:
                        t = node["type"]
                        results.setdefault(t, []).append(dict(node))

        elif contact:
            edges = orch.query_edges(target=contact)
            for e in edges[:20]:
                from src.uri import parse_uri
                parts = parse_uri(e["source"])
                adapter = orch.adapters.get(parts["adapter"], orch.internal)
                native_id = adapter.reverse_resolve(e["source"])
                if native_id:
                    node = adapter.resolve(native_id)
                    if node:
                        t = node["type"]
                        results.setdefault(t, []).append(dict(node))

        return {"scope": {"register": register, "type": type, "topic": topic, "contact": contact}, "results": results}

    @mcp.tool()
    def pim_decision_log(
        target: str | None = None,
        operation: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Retrieve decision log entries for auditing and undo.

        Args:
            target: Filter by PIM URI
            operation: Filter by operation type
            limit: Max results (default 50)
        """
        return orch.get_decision_log(target=target, operation=operation, limit=limit)

    return mcp


# Entry point for MCP
mcp = create_server()

if __name__ == "__main__":
    mcp.run()
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_server.py -v`
Expected: PASS

Note: The test checks tool registration. If `fastmcp`'s internal API for listing tools differs, adjust the test to match the actual API (e.g. `server.list_tools()` or similar).

**Step 5: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: all tests PASS

**Step 6: Commit**

```bash
git add src/server.py tests/test_server.py
git commit -m "feat(pim): MCP server with all 13 ontology tools"
```

---

## Task 10: End-to-End Integration Test

**Files:**
- Create: `tests/test_e2e.py`

**Step 1: Write the integration test**

```python
# tests/test_e2e.py
"""End-to-end test: create objects, link them, query the graph."""
import pytest
from src.db import init_db
from src.adapters.internal import InternalAdapter
from src.orchestrator import Orchestrator

@pytest.fixture
def orch(tmp_data_dir):
    conn = init_db(tmp_data_dir / "pim.db")
    internal = InternalAdapter(conn, tmp_data_dir)
    return Orchestrator(conn=conn, internal_adapter=internal, data_dir=tmp_data_dir)

def test_full_workflow(orch):
    """Simulate the architecture doc's end-to-end example (simplified)."""

    # Create a contact
    sarah = orch.create_node("contact", {"name": "Sarah Chen", "email": "sarah@acme.com"})

    # Create a topic
    q3 = orch.create_node("topic", {"title": "Q3 Review", "status": "active"}, register="working")

    # Create a message
    msg = orch.create_node("message", {
        "subject": "Q3 review meeting",
        "sent_at": "2026-03-12T10:00:00",
        "channel": "email",
        "direction": "inbound",
    }, body="Hi, can we meet Thursday at 2pm? I need the revenue report by Wednesday.")

    # Create an event derived from the message
    event = orch.create_node("event", {
        "title": "Q3 Review Meeting",
        "start": "2026-03-14T14:00:00",
        "end": "2026-03-14T15:00:00",
        "status": "confirmed",
    }, register="working")

    # Create a task derived from the message
    task = orch.create_node("task", {
        "title": "Send revenue report",
        "status": "open",
        "due_date": "2026-03-13",
    }, register="working")

    # Create relations
    orch.create_edge(msg["id"], sarah["id"], "from")           # message from Sarah
    orch.create_edge(event["id"], sarah["id"], "involves")     # event involves Sarah
    orch.create_edge(event["id"], msg["id"], "derived-from")   # event derived from message
    orch.create_edge(task["id"], msg["id"], "derived-from")    # task derived from message
    orch.create_edge(msg["id"], q3["id"], "belongs-to")        # message belongs to Q3 topic
    orch.create_edge(event["id"], q3["id"], "belongs-to")      # event belongs to Q3 topic
    orch.create_edge(task["id"], q3["id"], "belongs-to")       # task belongs to Q3 topic

    # Verify: query everything under Q3 topic
    q3_edges = orch.query_edges(target=q3["id"], edge_type="belongs-to")
    assert len(q3_edges) == 3  # message, event, task

    # Verify: query Sarah's involvement
    sarah_edges = orch.query_edges(target=sarah["id"])
    assert len(sarah_edges) == 2  # from, involves

    # Verify: task is in working register
    working_tasks = orch.query_nodes("task", {"register": "working"})
    assert len(working_tasks) == 1
    assert working_tasks[0]["attributes"]["title"] == "Send revenue report"

    # Complete the task
    orch.close_node(task["id"], "complete")
    log_tasks = orch.query_nodes("task", {"register": "log"})
    assert len(log_tasks) == 1
    assert log_tasks[0]["attributes"]["status"] == "completed"

    # Verify decision log has entries
    log = orch.get_decision_log()
    assert len(log) > 0

def test_text_search_across_bodies(orch):
    """Verify FTS works across node bodies."""
    orch.create_node("note", {"title": "API Design"}, body="REST endpoints for the billing system")
    orch.create_node("note", {"title": "Meeting Notes"}, body="Discussed the new billing flow with the team")
    orch.create_node("note", {"title": "Recipe"}, body="Chocolate chip cookies need butter and sugar")

    results = orch.query_nodes("note", {"text_search": "billing"})
    assert len(results) == 2

    results = orch.query_nodes("note", {"text_search": "cookies"})
    assert len(results) == 1
```

**Step 2: Run to verify it passes**

Run: `python -m pytest tests/test_e2e.py -v`
Expected: all 2 tests PASS

**Step 3: Run full test suite one final time**

Run: `python -m pytest tests/ -v --tb=short`
Expected: all tests PASS

**Step 4: Commit**

```bash
git add tests/test_e2e.py
git commit -m "test(pim): end-to-end integration test matching architecture doc example"
```

---

## Summary

After completing all 10 tasks, Tier 1 delivers:

| Component | File | What it does |
|-----------|------|-------------|
| Plugin scaffold | `plugin.json`, `.mcp.json`, `requirements.txt` | Plugin identity and MCP config |
| Constants | `src/constants.py` | Types, registers, relations, risk tiers |
| Database | `src/db.py` | SQLite schema with nodes, edges, decision_log, FTS |
| URI system | `src/uri.py` | PIM URI generation and parsing |
| Type schemas | `src/types.py` | Axis coordinates, attribute schemas, validation |
| Adapter ABC | `src/adapter.py` | Contract that all adapters implement |
| Internal adapter | `src/adapters/internal.py` | Full CRUD for nodes + edges, FTS, body externalization |
| Orchestrator | `src/orchestrator.py` | Routing, write policy, decision logging |
| MCP server | `src/server.py` | 13 ontology tools exposed via FastMCP |
| Tests | `tests/` | Unit + integration tests for all components |

**Next tier:** Tier 2 adds write policy enforcement with risk tier gating (confirm high-risk ops before executing).
