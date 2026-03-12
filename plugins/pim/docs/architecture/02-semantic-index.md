## Semantic Index

The semantic index is an embedding layer that supports three subsystems: identity resolution, retrieval, and relation discovery. All three use vector similarity search, but they use it for different purposes and with different constraints.

### What Gets Embedded

Each type embeds different fields, following the principle that not all content should be embedded indiscriminately. The embedding captures what is most useful for finding the node when you don't have its exact identifier.

| Type | Embedded Fields |
|---|---|
| Note | title, body, linked topic names |
| Entry | body, local temporal context |
| Task | title, description, linked topic names, recent activity |
| Event | title, location, participant names |
| Message | subject, body excerpt, sender/recipient names |
| Contact | name, aliases, organization, role, notes |
| Resource | title, description, URI domain |
| Topic | title, description, contained subtopics |

Embeddings are computed at index time (node creation and update). For a single-user PIM, the corpus is small enough that re-embedding on schema changes is practical.

### Per-Type vs. Cross-Type Search

The index supports two modes:

**Per-type search** is the default. When resolving a contact, search contacts. When finding related tasks, search tasks. Per-type search is faster, produces fewer false positives, and is appropriate when the target type is known.

**Cross-type search** is used for relation discovery. When asking "what is this note about, and does anything else in the system relate to it?", the search must span types. Cross-type search uses a unified embedding space where all types are indexed together, but results are weighted by relational plausibility — a note is more likely to relate to a topic or a message than to another note it has never been linked to.

### Implementation

**Embedding model.** The system uses a single general-purpose text embedding model for all types. A model like `text-embedding-3-small` (1536 dimensions) or a local alternative like `nomic-embed-text` (768 dimensions) is appropriate — the corpus is small enough that dimensionality is not a bottleneck. The critical requirement is that the model produces embeddings in a *single shared vector space* regardless of input content, so that a note about "Q3 revenue projections" and a message with subject "Q3 financials" land near each other even though they are different types with different embedded fields.

**Embedding construction.** Each type's embedded fields (see table above) are concatenated into a single text string with type-specific formatting before embedding. For example, a contact embedding might be constructed as `"Contact: Sarah Chen | Org: Acme Corp | Role: VP Finance"` while a message embedding might be `"Message: Q3 review | From: Sarah Chen | Body excerpt: revenue numbers look strong..."`. The type prefix and field labels provide lightweight structure that helps the model distinguish types without breaking cross-type comparability.

**Index structure.** Two index modes share the same embedding space:

- **Per-type index partitions**: separate `sqlite-vec` virtual tables per type, enabling fast scoped search. `vec_notes`, `vec_tasks`, `vec_contacts`, etc.
- **Cross-type index**: a single `vec_all` table containing every node's embedding, with a type column for post-hoc filtering. Used for relation discovery.

Both use the same embeddings — nodes are inserted into their per-type partition and into the cross-type table simultaneously.

**Reindexing.** For a single-user PIM (typically under 100K nodes), full reindexing takes seconds to minutes. The system reindexes on embedding model change, schema change, or on demand. Incremental indexing handles the common case of node creation and update.

The semantic index is a *retrieval substrate*, not a truth layer. It surfaces candidates; the relation graph and deterministic lookups provide authoritative answers.

### Similarity Ranking and Query Interface

The semantic index returns ranked results with similarity scores. Different subsystems interpret these scores differently.

**Score interpretation.** Cosine similarity scores range from 0 (unrelated) to 1 (identical). In practice, with general-purpose embedding models:

- **> 0.85**: strong match. Near-certain semantic overlap. Used as the threshold for automatic identity resolution hits in Stage 2.
- **0.70 – 0.85**: moderate match. Plausible connection, worth surfacing. Used for retrieval candidates and relation discovery proposals.
- **0.55 – 0.70**: weak match. May be relevant in context but high false positive rate. Used only when stronger results are absent.
- **< 0.55**: noise. Discard.

These thresholds are starting points. The system adjusts them over time based on the discovery agent's acceptance/rejection history stored in its memory directory.

**Query interface.** All semantic searches go through a single internal function:

```
semantic_search(query_embedding: vector, scope: SearchScope, limit: int, min_score: float) → [ScoredNode]
```

Where `SearchScope` is:

- `{type: "contact"}` — search the per-type partition for contacts only
- `{type: ["note", "entry"]}` — search multiple per-type partitions
- `{cross_type: true}` — search the unified cross-type index
- `{cross_type: true, exclude_types: ["entry"]}` — cross-type with type filtering

And `ScoredNode` returns:

```json
{
  "node_id": "pim://contact/internal/cn-012",
  "score": 0.82,
  "type": "contact",
  "excerpt": "Sarah Chen | Acme Corp | VP Finance",
  "graph_distance": 2
}
```

The `graph_distance` field is computed post-hoc: how many hops separate this result from the query's origin node in the relation graph. A semantically similar node that is also 1-2 hops away in the graph is much more likely to be genuinely relevant than one that is semantically similar but graph-distant. The retrieval pipeline uses this to prioritize graph-proximate semantic matches over graph-distant ones during the pruning stage.

**Composite scoring.** For relation discovery, results are ranked by a composite score that combines:

- Semantic similarity (cosine score from the embedding index)
- Graph proximity (inverse of hop distance; directly connected = 1.0, 2 hops = 0.5, etc.)
- Temporal proximity (for diachronic types: how close in time were they created or modified)
- Relational plausibility (from the plausibility table: is this type pair expected to relate?)

The composite score determines whether a proposed edge is above the confidence threshold for automatic creation (medium risk) or should be surfaced as a suggestion (presented to user during review).

