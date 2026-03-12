## Identity Resolution

Identity resolution is the process of determining whether a new piece of information refers to an existing node or requires creating a new one. It is the most consequential operation the system performs, because errors propagate through every relation attached to the misidentified node.

### Three-Stage Pipeline

**Stage 1: Deterministic Lookup.** Check exact identifiers and known aliases. For each type, the deterministic fields are:

- Contact: email address, phone number, exact normalized name, known aliases
- Resource: URI (exact match)
- Message: message-id header, thread-id
- Event: start time + title (exact match within a window)
- Task: title + topic (exact match within same topic)
- Topic: title (exact normalized match), taxonomy_id
- Note: ID only (content changes too much for deterministic match)
- Entry: ID only (timestamp + source is usually sufficient)

If there is a deterministic hit, resolution is complete.

**Stage 2: Typed Semantic Search.** Use per-type vector search to surface candidates. Search within the relevant type or a small type family — not the entire graph. Retrieve a modest candidate set (5–10 candidates).

**Stage 3: Relation-Aware Validation.** Compare candidates not only by semantic similarity but by relational consistency. Does this "John" work at the company mentioned in the message? Has this email domain appeared in the contact graph before? Is this candidate already linked to the same topic cluster?

The acceptance threshold is a function of type compatibility, field agreement, and relational coherence — not a single number.

### Resolution Outcomes

Resolution produces one of three outcomes:

- **Found** — strong deterministic or converging evidence. Link to existing node.
- **Ambiguous** — plausible candidates but insufficient evidence. Record as alias candidate, present to user, or hold for future evidence.
- **Not found** — no match after exhausting the search policy. Create new node. This is a bounded claim (searched within scope), not a metaphysical assertion.

### Merge Risk by Type

The ontology's type axes predict how risky identity errors are:

- **Contacts** have the highest merge risk. A false merge collapses two real entities into one, corrupting every relation that points to them. The system should prefer false negatives (creating a duplicate) over false merges.
- **Topics** have high merge risk due to fuzzy boundaries. Auto-deduplication should be conservative.
- **Notes** are highly mutable; their identity drifts as content evolves. Content-based deduplication is unreliable.
- **Entries** and **messages** are append-only and immutable. They are cheap to create and almost never need deduplication.
- **Resources** resolve deterministically by URI. Low merge risk.

---

## Retrieval Pipeline

When the agent needs context for an operation, it should not dump arbitrary similar content into the prompt. Retrieval follows a disciplined four-stage pipeline.

### Stage 1: Structured Retrieval

Start with the known. Retrieve the target node and its direct attributes. If the operation references specific nodes by ID, topic, or contact, fetch those first.

### Stage 2: Graph Expansion

Expand one or two hops in the relation graph. From a task, follow belongs-to to its topic, derived-from to its source message, delegated-to to its assignee. From a contact, follow inbound agency relations to recent messages, events, and tasks.

This is high-signal retrieval — the graph encodes known, validated structure. The ontology's relation families predict which hops are most valuable: structural (via topic), agency (via contact), derivation (via provenance), temporal (via sequence), annotation (via commentary).

### Stage 3: Semantic Retrieval

Only now use vector search to surface additional context. Search within the relevant type family using per-type search, not cross-type. If working on a task about "follow up with John about the roadmap meeting," semantic search might surface related notes or resources that are not explicitly linked yet.

### Stage 4: Pruning

Trim to the smallest context that supports the operation. Prefer structured and graph-derived context over semantic matches when they conflict. Drop semantic results that do not add information beyond what the graph already provided.

This pipeline — structured first, then graph, then semantic, then prune — is more reliable than embedding-only retrieval because it uses known structure before fuzzy similarity.

---

## Relation Discovery

Relation discovery is the process of surfacing implicit connections that should become explicit edges in the graph. It is distinct from retrieval (which assembles context for an immediate operation) and from identity resolution (which determines whether a node already exists).

### When Discovery Runs

Discovery runs in three contexts:

**After capture.** When new nodes enter the system, discovery searches for existing nodes they should be linked to. A newly captured message might relate to an existing topic. A newly created contact might match names mentioned in existing notes.

**During review.** When the user reviews a register or a topic, discovery can surface nodes that are semantically close to the reviewed set but not yet linked. "You have a note about API design and a task about refactoring the endpoint layer — these seem related but aren't connected."

**On schedule.** A background pass over the graph can identify clusters of semantically similar nodes that lack explicit relations. This is a hygiene operation — tidying the graph by proposing edges where the user forgot to create them.

### How Discovery Works

1. Select a seed node or set of nodes (the capture, the review scope, or the background batch).
2. Run cross-type semantic search against the seed. Unlike per-type retrieval search, this spans the full embedding space.
3. Filter results by relational plausibility (see table below).
4. Score surviving candidates by semantic similarity, graph distance (are they near each other already via other paths?), and temporal proximity (were they created or modified around the same time?).
5. Propose edges above a confidence threshold. High-confidence proposals become medium-risk write operations (see Write Policy). Lower-confidence proposals are surfaced to the user as suggestions.

### Relational Plausibility

The ontology derives five relation families from endpoint types. This constrains which edges are plausible between any two node types. The discovery system uses this table to reject implausible connections before scoring:

| Source Type | Target Type | Plausible Families | Typical Labels |
|---|---|---|---|
| any | Topic | structural | belongs-to |
| any | Contact | agency | from, to, involves, delegated-to, sent-by |
| diachronic | diachronic | temporal | precedes, occurs-during |
| Note, Entry | any | annotation | annotation-of |
| any | any | derivation | derived-from |
| any | any | generic (fallback) | references, related-to |

Rules for filtering:

- If the target is a Topic, prefer structural relations. Do not propose agency or temporal relations to a Topic.
- If the target is a Contact, prefer agency relations. Do not propose structural relations to a Contact (contacts don't "contain" things).
- If both nodes are diachronic and temporally proximate, temporal relations are plausible.
- If the source is sovereign + unstructured (Note, Entry), annotation is plausible toward any target.
- Derivation is plausible between any types but requires evidence of a creation chain — semantic similarity alone is insufficient. Discovery should flag potential derivation links for user confirmation rather than creating them autonomously.
- The generic fallback (references, related-to) is always plausible but low-priority. If a more specific family fits, prefer it.

### The Semantic Index's Three Roles

To summarize the semantic index's use across subsystems:

| Subsystem | Search Mode | Purpose |
|---|---|---|
| Identity resolution | per-type | "Does this node already exist?" |
| Retrieval | per-type | "What context do I need for this operation?" |
| Relation discovery | cross-type | "What connections exist that aren't yet edges?" |

