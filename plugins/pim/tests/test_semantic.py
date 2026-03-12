"""Tests for the semantic index."""

import json
import sqlite3
import pytest

from src.semantic import SemanticIndex


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "test.db"
    c = sqlite3.connect(str(db_path))
    c.row_factory = sqlite3.Row
    # Create a minimal nodes table for join queries
    c.execute("""CREATE TABLE nodes (
        id TEXT PRIMARY KEY,
        type TEXT,
        register TEXT,
        adapter TEXT,
        native_id TEXT,
        attributes TEXT,
        body TEXT,
        body_path TEXT,
        source_op TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    # Insert test nodes
    c.execute(
        "INSERT INTO nodes (id, type, attributes) VALUES (?, ?, ?)",
        ("pim://note/internal/n-1", "note", json.dumps({"title": "First"}))
    )
    c.execute(
        "INSERT INTO nodes (id, type, attributes) VALUES (?, ?, ?)",
        ("pim://note/internal/n-2", "note", json.dumps({"title": "Second"}))
    )
    c.execute(
        "INSERT INTO nodes (id, type, attributes) VALUES (?, ?, ?)",
        ("pim://contact/internal/c-1", "contact", json.dumps({"name": "Alice"}))
    )
    c.commit()
    return c


@pytest.fixture
def index(conn):
    return SemanticIndex(conn, embedding_dim=3)


# --- Table creation ---

class TestInit:
    def test_creates_embeddings_table(self, conn):
        idx = SemanticIndex(conn, embedding_dim=3)
        # Table should exist
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='embeddings'"
        ).fetchone()
        assert row is not None

    def test_idempotent(self, conn):
        SemanticIndex(conn, embedding_dim=3)
        SemanticIndex(conn, embedding_dim=3)  # Should not raise


# --- Store and retrieve ---

class TestStoreRetrieve:
    def test_store_and_get(self, index):
        index.store_embedding("pim://note/internal/n-1", [1.0, 0.0, 0.0])
        result = index.get_embedding("pim://note/internal/n-1")
        assert result == [1.0, 0.0, 0.0]

    def test_get_nonexistent(self, index):
        result = index.get_embedding("nonexistent")
        assert result is None

    def test_store_updates_existing(self, index):
        index.store_embedding("pim://note/internal/n-1", [1.0, 0.0, 0.0])
        index.store_embedding("pim://note/internal/n-1", [0.0, 1.0, 0.0])
        result = index.get_embedding("pim://note/internal/n-1")
        assert result == [0.0, 1.0, 0.0]

    def test_store_wrong_dimension(self, index):
        with pytest.raises(ValueError, match="dimension mismatch"):
            index.store_embedding("pim://note/internal/n-1", [1.0, 0.0])

    def test_delete_embedding(self, index):
        index.store_embedding("pim://note/internal/n-1", [1.0, 0.0, 0.0])
        index.delete_embedding("pim://note/internal/n-1")
        assert index.get_embedding("pim://note/internal/n-1") is None


# --- Search ---

class TestSearch:
    def test_search_returns_sorted(self, index):
        index.store_embedding("pim://note/internal/n-1", [1.0, 0.0, 0.0])
        index.store_embedding("pim://note/internal/n-2", [0.9, 0.1, 0.0])
        index.store_embedding("pim://contact/internal/c-1", [0.0, 1.0, 0.0])

        results = index.search([1.0, 0.0, 0.0])
        assert len(results) == 3
        assert results[0]["node_id"] == "pim://note/internal/n-1"
        assert results[0]["similarity"] == 1.0

    def test_search_with_type_filter(self, index):
        index.store_embedding("pim://note/internal/n-1", [1.0, 0.0, 0.0])
        index.store_embedding("pim://contact/internal/c-1", [0.9, 0.1, 0.0])

        results = index.search([1.0, 0.0, 0.0], obj_type="note")
        assert len(results) == 1
        assert results[0]["node_id"] == "pim://note/internal/n-1"

    def test_search_with_min_similarity(self, index):
        index.store_embedding("pim://note/internal/n-1", [1.0, 0.0, 0.0])
        index.store_embedding("pim://note/internal/n-2", [0.0, 1.0, 0.0])

        results = index.search([1.0, 0.0, 0.0], min_similarity=0.5)
        assert len(results) == 1

    def test_search_with_limit(self, index):
        index.store_embedding("pim://note/internal/n-1", [1.0, 0.0, 0.0])
        index.store_embedding("pim://note/internal/n-2", [0.9, 0.1, 0.0])

        results = index.search([1.0, 0.0, 0.0], limit=1)
        assert len(results) == 1

    def test_search_wrong_dimension(self, index):
        with pytest.raises(ValueError, match="dimension mismatch"):
            index.search([1.0, 0.0])

    def test_search_empty_index(self, index):
        results = index.search([1.0, 0.0, 0.0])
        assert results == []


# --- Batch store ---

class TestBatchStore:
    def test_batch_store(self, index):
        count = index.batch_store([
            {"node_id": "pim://note/internal/n-1", "embedding": [1.0, 0.0, 0.0], "model": "test"},
            {"node_id": "pim://note/internal/n-2", "embedding": [0.0, 1.0, 0.0]},
        ])
        assert count == 2
        assert index.get_embedding("pim://note/internal/n-1") is not None
        assert index.get_embedding("pim://note/internal/n-2") is not None

    def test_batch_store_skips_wrong_dim(self, index):
        count = index.batch_store([
            {"node_id": "pim://note/internal/n-1", "embedding": [1.0, 0.0, 0.0]},
            {"node_id": "pim://note/internal/n-2", "embedding": [1.0]},  # Wrong dim
        ])
        assert count == 1


# --- Stats ---

class TestStats:
    def test_stats_empty(self, index):
        stats = index.stats()
        assert stats["total_embeddings"] == 0
        assert stats["embedding_dim"] == 3

    def test_stats_with_data(self, index):
        index.store_embedding("pim://note/internal/n-1", [1.0, 0.0, 0.0], model="test-model")
        index.store_embedding("pim://note/internal/n-2", [0.0, 1.0, 0.0], model="test-model")
        stats = index.stats()
        assert stats["total_embeddings"] == 2
        assert stats["models"]["test-model"] == 2


# --- Cosine similarity ---

class TestCosineSimilarity:
    def test_identical_vectors(self):
        assert SemanticIndex._cosine_similarity([1, 0, 0], [1, 0, 0]) == 1.0

    def test_orthogonal_vectors(self):
        assert SemanticIndex._cosine_similarity([1, 0, 0], [0, 1, 0]) == 0.0

    def test_opposite_vectors(self):
        assert SemanticIndex._cosine_similarity([1, 0], [-1, 0]) == -1.0

    def test_zero_vector(self):
        assert SemanticIndex._cosine_similarity([0, 0], [1, 0]) == 0.0

    def test_different_lengths(self):
        assert SemanticIndex._cosine_similarity([1], [1, 0]) == 0.0
