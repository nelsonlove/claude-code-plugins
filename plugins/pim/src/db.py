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
