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
