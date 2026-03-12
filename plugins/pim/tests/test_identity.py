"""Tests for the identity resolution pipeline."""

import json
import sqlite3
import pytest

from src.identity import IdentityResolver
from src.semantic import SemanticIndex


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "test.db"
    c = sqlite3.connect(str(db_path))
    c.row_factory = sqlite3.Row
    # Create nodes table
    c.execute("""CREATE TABLE nodes (
        id TEXT PRIMARY KEY,
        type TEXT,
        register TEXT DEFAULT 'scratch',
        adapter TEXT DEFAULT 'internal',
        native_id TEXT,
        attributes TEXT,
        body TEXT,
        body_path TEXT,
        source_op TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    # Insert test contacts
    c.execute(
        "INSERT INTO nodes (id, type, attributes) VALUES (?, ?, ?)",
        ("pim://contact/internal/c-1", "contact",
         json.dumps({"name": "John Doe", "email": "john@example.com"}))
    )
    c.execute(
        "INSERT INTO nodes (id, type, attributes) VALUES (?, ?, ?)",
        ("pim://contact/internal/c-2", "contact",
         json.dumps({"name": "John Doe", "email": "john.doe@work.com"}))
    )
    c.execute(
        "INSERT INTO nodes (id, type, attributes) VALUES (?, ?, ?)",
        ("pim://contact/internal/c-3", "contact",
         json.dumps({"name": "Jane Smith", "email": "jane@example.com"}))
    )
    # Insert test notes
    c.execute(
        "INSERT INTO nodes (id, type, attributes) VALUES (?, ?, ?)",
        ("pim://note/internal/n-1", "note",
         json.dumps({"title": "Meeting Notes"}))
    )
    c.execute(
        "INSERT INTO nodes (id, type, attributes) VALUES (?, ?, ?)",
        ("pim://note/internal/n-2", "note",
         json.dumps({"title": "Meeting Notes"}))
    )
    c.commit()
    return c


@pytest.fixture
def resolver(conn):
    return IdentityResolver(conn)


@pytest.fixture
def resolver_with_semantic(conn):
    semantic = SemanticIndex(conn, embedding_dim=3)
    return IdentityResolver(conn, semantic_index=semantic)


# --- Table creation ---

class TestInit:
    def test_creates_tables(self, conn):
        IdentityResolver(conn)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'identity_%'"
        ).fetchall()
        names = {r["name"] for r in tables}
        assert "identity_matches" in names
        assert "identity_merges" in names

    def test_idempotent(self, conn):
        IdentityResolver(conn)
        IdentityResolver(conn)


# --- Deterministic matching ---

class TestDeterministicMatch:
    def test_finds_name_match(self, resolver):
        matches = resolver.find_matches("pim://contact/internal/c-1", min_confidence=0.3)
        # c-2 has same name "John Doe"
        match_ids = [m["candidate_id"] for m in matches]
        assert "pim://contact/internal/c-2" in match_ids

    def test_no_match_for_different(self, resolver):
        matches = resolver.find_matches("pim://contact/internal/c-3", min_confidence=0.8)
        # Jane Smith doesn't match John Doe
        assert len(matches) == 0

    def test_note_title_match(self, resolver):
        matches = resolver.find_matches("pim://note/internal/n-1", min_confidence=0.5)
        match_ids = [m["candidate_id"] for m in matches]
        assert "pim://note/internal/n-2" in match_ids

    def test_nonexistent_node(self, resolver):
        matches = resolver.find_matches("nonexistent")
        assert matches == []


# --- Semantic matching ---

class TestSemanticMatch:
    def test_finds_semantic_match(self, resolver_with_semantic):
        sem = resolver_with_semantic.semantic
        sem.store_embedding("pim://contact/internal/c-1", [1.0, 0.0, 0.0])
        sem.store_embedding("pim://contact/internal/c-2", [0.95, 0.05, 0.0])
        sem.store_embedding("pim://contact/internal/c-3", [0.0, 1.0, 0.0])

        matches = resolver_with_semantic.find_matches(
            "pim://contact/internal/c-1", min_confidence=0.5
        )
        # Should find c-2 (similar embedding + same name)
        match_ids = [m["candidate_id"] for m in matches]
        assert "pim://contact/internal/c-2" in match_ids

    def test_no_semantic_without_embedding(self, resolver_with_semantic):
        # Node has no embedding stored
        matches = resolver_with_semantic._semantic_match(
            "pim://contact/internal/c-1"
        )
        assert matches == []


# --- Record and resolve matches ---

class TestRecordResolve:
    def test_record_match(self, resolver):
        match_id = resolver.record_match(
            "pim://contact/internal/c-1",
            "pim://contact/internal/c-2",
            "deterministic",
            0.9,
            evidence={"matching_fields": ["name"]},
        )
        assert match_id is not None
        assert match_id > 0

    def test_resolve_accept(self, resolver):
        match_id = resolver.record_match(
            "pim://contact/internal/c-1",
            "pim://contact/internal/c-2",
            "deterministic", 0.9
        )
        result = resolver.resolve_match(match_id, accept=True)
        assert result["status"] == "accepted"

        # Should create a merge record
        merges = resolver.get_merged_ids("pim://contact/internal/c-1")
        assert "pim://contact/internal/c-2" in merges

    def test_resolve_reject(self, resolver):
        match_id = resolver.record_match(
            "pim://contact/internal/c-1",
            "pim://contact/internal/c-2",
            "deterministic", 0.9
        )
        result = resolver.resolve_match(match_id, accept=False)
        assert result["status"] == "rejected"

        # Should not create a merge
        merges = resolver.get_merged_ids("pim://contact/internal/c-1")
        assert len(merges) == 0

    def test_resolve_nonexistent(self, resolver):
        with pytest.raises(ValueError, match="Match not found"):
            resolver.resolve_match(999, accept=True)


# --- Canonical ID ---

class TestCanonical:
    def test_get_canonical_no_merge(self, resolver):
        canonical = resolver.get_canonical("pim://contact/internal/c-1")
        assert canonical == "pim://contact/internal/c-1"

    def test_get_canonical_after_merge(self, resolver):
        match_id = resolver.record_match(
            "pim://contact/internal/c-1",
            "pim://contact/internal/c-2",
            "deterministic", 0.9
        )
        resolver.resolve_match(match_id, accept=True)

        canonical = resolver.get_canonical("pim://contact/internal/c-2")
        assert canonical == "pim://contact/internal/c-1"

    def test_get_merged_ids(self, resolver):
        match_id = resolver.record_match(
            "pim://contact/internal/c-1",
            "pim://contact/internal/c-2",
            "deterministic", 0.9
        )
        resolver.resolve_match(match_id, accept=True)

        merged = resolver.get_merged_ids("pim://contact/internal/c-1")
        assert "pim://contact/internal/c-2" in merged


# --- Pending matches ---

class TestPendingMatches:
    def test_get_pending(self, resolver):
        resolver.record_match("c-1", "c-2", "det", 0.9)
        resolver.record_match("c-1", "c-3", "det", 0.5)

        pending = resolver.get_pending_matches()
        assert len(pending) == 2
        # Sorted by confidence DESC
        assert pending[0]["confidence"] >= pending[1]["confidence"]

    def test_pending_after_resolve(self, resolver):
        mid = resolver.record_match("c-1", "c-2", "det", 0.9)
        resolver.resolve_match(mid, accept=True)

        pending = resolver.get_pending_matches()
        assert len(pending) == 0


# --- Stats ---

class TestStats:
    def test_stats_empty(self, resolver):
        stats = resolver.stats()
        assert stats["total_matches"] == 0
        assert stats["pending"] == 0
        assert stats["total_merges"] == 0

    def test_stats_with_data(self, resolver):
        mid = resolver.record_match("c-1", "c-2", "det", 0.9)
        resolver.resolve_match(mid, accept=True)
        resolver.record_match("c-1", "c-3", "det", 0.5)

        stats = resolver.stats()
        assert stats["total_matches"] == 2
        assert stats["pending"] == 1
        assert stats["accepted"] == 1
        assert stats["total_merges"] == 1


# --- Key fields ---

class TestKeyFields:
    def test_contact_fields(self):
        fields = IdentityResolver._key_fields_for_type("contact")
        assert "name" in fields
        assert "email" in fields

    def test_unknown_type(self):
        fields = IdentityResolver._key_fields_for_type("unknown")
        assert fields == []


# --- Attribute similarity ---

class TestAttributeSimilarity:
    def test_exact_match(self):
        sim = IdentityResolver._compute_attribute_similarity(
            {"name": "John", "email": "j@x.com"},
            {"name": "John", "email": "j@x.com"},
            ["name", "email"]
        )
        assert sim == 1.0

    def test_partial_match(self):
        sim = IdentityResolver._compute_attribute_similarity(
            {"name": "John", "email": "j@x.com"},
            {"name": "John", "email": "other@x.com"},
            ["name", "email"]
        )
        assert sim == 0.5

    def test_no_match(self):
        sim = IdentityResolver._compute_attribute_similarity(
            {"name": "John"}, {"name": "Jane"}, ["name"]
        )
        assert sim == 0.0

    def test_case_insensitive(self):
        sim = IdentityResolver._compute_attribute_similarity(
            {"name": "JOHN"}, {"name": "john"}, ["name"]
        )
        assert sim == 1.0

    def test_no_comparable_fields(self):
        sim = IdentityResolver._compute_attribute_similarity(
            {"name": "John"}, {"email": "j@x.com"}, ["name"]
        )
        assert sim == 0.0
