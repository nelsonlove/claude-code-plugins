"""Semantic index — embedding-based similarity search for PIM nodes."""

import json
import math
import sqlite3


class SemanticIndex:
    """Manages embeddings and similarity search for PIM nodes.

    Stores embeddings in a dedicated table and supports k-NN search
    using cosine similarity. In Tier 1, embeddings are provided externally
    (e.g., from an LLM). Future tiers will auto-generate them.
    """

    def __init__(self, conn: sqlite3.Connection, embedding_dim: int = 384):
        self.conn = conn
        self.embedding_dim = embedding_dim
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Create the embeddings table if it doesn't exist."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                node_id TEXT PRIMARY KEY,
                embedding TEXT NOT NULL,
                model TEXT DEFAULT 'unknown',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (node_id) REFERENCES nodes(id)
            )
        """)
        self.conn.commit()

    def store_embedding(self, node_id: str, embedding: list[float],
                        model: str = "unknown") -> None:
        """Store or update an embedding for a node."""
        if len(embedding) != self.embedding_dim:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self.embedding_dim}, "
                f"got {len(embedding)}"
            )
        self.conn.execute(
            """INSERT INTO embeddings (node_id, embedding, model, updated_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(node_id) DO UPDATE SET
                   embedding = excluded.embedding,
                   model = excluded.model,
                   updated_at = CURRENT_TIMESTAMP""",
            (node_id, json.dumps(embedding), model)
        )
        self.conn.commit()

    def get_embedding(self, node_id: str) -> list[float] | None:
        """Retrieve the embedding for a node."""
        row = self.conn.execute(
            "SELECT embedding FROM embeddings WHERE node_id = ?",
            (node_id,)
        ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def delete_embedding(self, node_id: str) -> None:
        """Remove the embedding for a node."""
        self.conn.execute(
            "DELETE FROM embeddings WHERE node_id = ?",
            (node_id,)
        )
        self.conn.commit()

    def search(self, query_embedding: list[float], limit: int = 10,
               obj_type: str | None = None,
               min_similarity: float = 0.0) -> list[dict]:
        """Find the most similar nodes to the query embedding.

        Returns a list of {node_id, similarity} dicts ordered by similarity (descending).
        """
        if len(query_embedding) != self.embedding_dim:
            raise ValueError(
                f"Query embedding dimension mismatch: expected {self.embedding_dim}, "
                f"got {len(query_embedding)}"
            )

        # Fetch all embeddings and compute cosine similarity
        # In a production system, this would use sqlite-vec for efficient k-NN
        if obj_type:
            rows = self.conn.execute(
                """SELECT e.node_id, e.embedding
                   FROM embeddings e
                   JOIN nodes n ON e.node_id = n.id
                   WHERE n.type = ?""",
                (obj_type,)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT node_id, embedding FROM embeddings"
            ).fetchall()

        results = []
        for row in rows:
            stored_embedding = json.loads(row[1] if isinstance(row[1], str) else row["embedding"])
            similarity = self._cosine_similarity(query_embedding, stored_embedding)
            if similarity >= min_similarity:
                results.append({
                    "node_id": row[0] if isinstance(row[0], (str, int)) else row["node_id"],
                    "similarity": round(similarity, 6),
                })

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]

    def batch_store(self, embeddings: list[dict]) -> int:
        """Store multiple embeddings at once.

        Each dict should have: node_id, embedding, and optionally model.
        Returns the number of embeddings stored.
        """
        count = 0
        for item in embeddings:
            node_id = item["node_id"]
            embedding = item["embedding"]
            model = item.get("model", "unknown")
            if len(embedding) == self.embedding_dim:
                self.conn.execute(
                    """INSERT INTO embeddings (node_id, embedding, model, updated_at)
                       VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                       ON CONFLICT(node_id) DO UPDATE SET
                           embedding = excluded.embedding,
                           model = excluded.model,
                           updated_at = CURRENT_TIMESTAMP""",
                    (node_id, json.dumps(embedding), model)
                )
                count += 1
        self.conn.commit()
        return count

    def stats(self) -> dict:
        """Return statistics about the semantic index."""
        total = self.conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        models = self.conn.execute(
            "SELECT model, COUNT(*) FROM embeddings GROUP BY model"
        ).fetchall()
        return {
            "total_embeddings": total,
            "embedding_dim": self.embedding_dim,
            "models": {row[0]: row[1] for row in models},
        }

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
