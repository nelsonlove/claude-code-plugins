"""Identity resolution — deduplication and entity matching pipeline."""

import json
import sqlite3
from typing import Any


class IdentityResolver:
    """Pipeline for resolving duplicate or ambiguous entities.

    Supports deterministic matching (exact attribute match) and
    semantic matching (embedding similarity). Maintains a merge log
    for tracking resolved identities.
    """

    def __init__(self, conn: sqlite3.Connection, semantic_index=None):
        self.conn = conn
        self.semantic = semantic_index
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Create identity resolution tables."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS identity_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                match_type TEXT NOT NULL,
                confidence REAL NOT NULL,
                evidence TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS identity_merges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                canonical_id TEXT NOT NULL,
                merged_id TEXT NOT NULL,
                match_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (match_id) REFERENCES identity_matches(id)
            )
        """)
        self.conn.commit()

    def find_matches(self, node_id: str, obj_type: str | None = None,
                     min_confidence: float = 0.8) -> list[dict]:
        """Find potential matches for a node using all available methods.

        Returns candidates ordered by confidence (descending).
        """
        candidates = []

        # 1. Deterministic matching (exact attribute match)
        det_matches = self._deterministic_match(node_id, obj_type)
        candidates.extend(det_matches)

        # 2. Semantic matching (embedding similarity)
        if self.semantic:
            sem_matches = self._semantic_match(node_id, obj_type)
            candidates.extend(sem_matches)

        # Deduplicate and sort
        seen = set()
        unique = []
        for c in candidates:
            if c["candidate_id"] not in seen:
                seen.add(c["candidate_id"])
                unique.append(c)
        unique.sort(key=lambda x: x["confidence"], reverse=True)

        return [c for c in unique if c["confidence"] >= min_confidence]

    def _deterministic_match(self, node_id: str, obj_type: str | None = None) -> list[dict]:
        """Find matches based on exact attribute comparison."""
        row = self.conn.execute(
            "SELECT * FROM nodes WHERE id = ?", (node_id,)
        ).fetchone()
        if row is None:
            return []

        node_attrs = json.loads(row["attributes"])
        node_type = row["type"]

        # Build query based on type-specific key fields
        key_fields = self._key_fields_for_type(node_type)
        if not key_fields:
            return []

        # Find other nodes of the same type with matching key fields
        candidates = []
        query = "SELECT * FROM nodes WHERE type = ? AND id != ?"
        params: list[Any] = [node_type, node_id]

        if obj_type:
            query += " AND type = ?"
            params.append(obj_type)

        other_nodes = self.conn.execute(query, params).fetchall()

        for other in other_nodes:
            other_attrs = json.loads(other["attributes"])
            confidence = self._compute_attribute_similarity(
                node_attrs, other_attrs, key_fields
            )
            if confidence > 0:
                candidates.append({
                    "candidate_id": other["id"],
                    "confidence": confidence,
                    "match_type": "deterministic",
                    "evidence": {
                        "matching_fields": [
                            f for f in key_fields
                            if node_attrs.get(f) and node_attrs.get(f) == other_attrs.get(f)
                        ]
                    },
                })

        return candidates

    def _semantic_match(self, node_id: str, obj_type: str | None = None) -> list[dict]:
        """Find matches using embedding similarity."""
        if not self.semantic:
            return []

        embedding = self.semantic.get_embedding(node_id)
        if embedding is None:
            return []

        results = self.semantic.search(
            embedding, limit=5, obj_type=obj_type, min_similarity=0.7
        )

        return [
            {
                "candidate_id": r["node_id"],
                "confidence": r["similarity"],
                "match_type": "semantic",
                "evidence": {"similarity": r["similarity"]},
            }
            for r in results
            if r["node_id"] != node_id
        ]

    def record_match(self, source_id: str, target_id: str,
                     match_type: str, confidence: float,
                     evidence: dict | None = None) -> int:
        """Record a potential identity match for review."""
        cursor = self.conn.execute(
            """INSERT INTO identity_matches
               (source_id, target_id, match_type, confidence, evidence)
               VALUES (?, ?, ?, ?, ?)""",
            (source_id, target_id, match_type, confidence,
             json.dumps(evidence or {}))
        )
        self.conn.commit()
        return cursor.lastrowid

    def resolve_match(self, match_id: int, accept: bool) -> dict:
        """Accept or reject a pending match."""
        row = self.conn.execute(
            "SELECT * FROM identity_matches WHERE id = ?",
            (match_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Match not found: {match_id}")

        status = "accepted" if accept else "rejected"
        self.conn.execute(
            """UPDATE identity_matches
               SET status = ?, resolved_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (status, match_id)
        )

        result = {
            "match_id": match_id,
            "status": status,
            "source_id": row["source_id"],
            "target_id": row["target_id"],
        }

        if accept:
            # Record the merge
            self.conn.execute(
                """INSERT INTO identity_merges (canonical_id, merged_id, match_id)
                   VALUES (?, ?, ?)""",
                (row["source_id"], row["target_id"], match_id)
            )

        self.conn.commit()
        return result

    def get_canonical(self, node_id: str) -> str:
        """Get the canonical ID for a node (follows merge chain)."""
        # Check if this node was merged into another
        row = self.conn.execute(
            "SELECT canonical_id FROM identity_merges WHERE merged_id = ?",
            (node_id,)
        ).fetchone()
        if row is None:
            return node_id
        # Follow the chain
        return self.get_canonical(row["canonical_id"])

    def get_merged_ids(self, canonical_id: str) -> list[str]:
        """Get all IDs that were merged into this canonical ID."""
        rows = self.conn.execute(
            "SELECT merged_id FROM identity_merges WHERE canonical_id = ?",
            (canonical_id,)
        ).fetchall()
        return [row["merged_id"] for row in rows]

    def get_pending_matches(self, limit: int = 50) -> list[dict]:
        """Get pending identity matches for review."""
        rows = self.conn.execute(
            """SELECT * FROM identity_matches
               WHERE status = 'pending'
               ORDER BY confidence DESC
               LIMIT ?""",
            (limit,)
        ).fetchall()
        return [
            {
                "id": row["id"],
                "source_id": row["source_id"],
                "target_id": row["target_id"],
                "match_type": row["match_type"],
                "confidence": row["confidence"],
                "evidence": json.loads(row["evidence"]) if row["evidence"] else {},
            }
            for row in rows
        ]

    def stats(self) -> dict:
        """Return identity resolution statistics."""
        total_matches = self.conn.execute(
            "SELECT COUNT(*) FROM identity_matches"
        ).fetchone()[0]
        pending = self.conn.execute(
            "SELECT COUNT(*) FROM identity_matches WHERE status = 'pending'"
        ).fetchone()[0]
        accepted = self.conn.execute(
            "SELECT COUNT(*) FROM identity_matches WHERE status = 'accepted'"
        ).fetchone()[0]
        total_merges = self.conn.execute(
            "SELECT COUNT(*) FROM identity_merges"
        ).fetchone()[0]
        return {
            "total_matches": total_matches,
            "pending": pending,
            "accepted": accepted,
            "total_merges": total_merges,
        }

    @staticmethod
    def _key_fields_for_type(obj_type: str) -> list[str]:
        """Return the key fields used for deterministic matching per type."""
        return {
            "contact": ["name", "email", "phone"],
            "topic": ["title", "taxonomy_id"],
            "resource": ["uri"],
            "note": ["title"],
            "entry": ["title", "timestamp"],
            "task": ["title"],
            "event": ["title", "start"],
            "message": ["subject", "sent_at"],
        }.get(obj_type, [])

    @staticmethod
    def _compute_attribute_similarity(attrs_a: dict, attrs_b: dict,
                                       key_fields: list[str]) -> float:
        """Compute similarity between two attribute dicts based on key fields."""
        if not key_fields:
            return 0.0

        matches = 0
        comparisons = 0

        for field in key_fields:
            val_a = attrs_a.get(field)
            val_b = attrs_b.get(field)
            if val_a is not None and val_b is not None:
                comparisons += 1
                if isinstance(val_a, str) and isinstance(val_b, str):
                    if val_a.lower() == val_b.lower():
                        matches += 1
                elif val_a == val_b:
                    matches += 1

        if comparisons == 0:
            return 0.0
        return matches / comparisons
