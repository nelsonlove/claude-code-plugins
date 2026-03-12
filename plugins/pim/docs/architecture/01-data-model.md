## Data Model

The ontology defines types, registers, and relations as abstract concepts. The data model implements them as concrete structures in a graph stored in SQLite.

### Primitives

**Node.** A discrete, identifiable object in the system. Every note, entry, task, event, message, contact, resource, and topic is a node.

Every node has:

- **id** — a PIM URI (see Addressing below), globally unique
- **type** — one of the eight object types (note, entry, task, event, message, contact, resource, topic)
- **attributes** — typed key-value pairs determined by the node's type schema
- **register** — the node's current register (scratch, working, reference, log)
- **adapter** — which adapter holds this node
- **native_id** — the identifier assigned by the external tool, if any
- **source_op** — the decision log entry that created this node
- **created_at** — timestamp of creation
- **modified_at** — timestamp of last modification

**Edge.** A typed, directed connection between two nodes. The ontology establishes that the system has one relational primitive — the directed edge — and that relation semantics derive from endpoint types. The data model stores one edge per relation in the canonical direction; inverse traversal is a query-time operation, not a stored duplicate.

Every edge has:

- **id** — a globally unique identifier
- **source** — PIM URI of the source node (the node that bears on the target)
- **target** — PIM URI of the target node
- **type** — the convenience label for this relation (belongs-to, derived-from, from, etc.)
- **metadata** — optional key-value pairs (weight, note, context)
- **source_op** — the decision log entry that created this edge
- **created_at** — timestamp of creation

**Content body.** The text of a note, the body of a message, the binary data behind a resource. Unstructured types (note, entry, message, resource) carry content bodies. Structured types (task, event, contact, topic) consist entirely of attributes and edges.

Storage rules:

- Bodies under 100KB: stored inline in the node record
- Bodies over 100KB: externalized to `~/.pim/blobs/{node_id}`
- Binary content (images, PDFs): always externalized

### Addressing

Every node has a PIM URI that uniquely identifies it across all adapters.

Format: `pim://{type}/{adapter}/{native_id}`

Examples:

- `pim://note/internal/n-20260312-001`
- `pim://task/omnifocus/hLarPeCbbib`
- `pim://message/himalaya/acct1-inbox-4527`
- `pim://contact/internal/cn-012`
- `pim://resource/internal/r-quarterly-report`
- `pim://topic/omnifocus/nR4oJnW2Mxf`

For objects that exist only in the orchestration layer (topics that span multiple tools, relations no single adapter holds), the adapter portion identifies the internal store:

- `pim://topic/internal/top-901`

Every adapter must support four addressing operations:

1. **Resolve** — given a native ID, return the node with attributes
2. **Reverse-resolve** — given a PIM URI, return the native ID
3. **Enumerate** — list all nodes of supported types, with pagination
4. **Stability guarantee** — native IDs must be stable, or the adapter must signal when they change

### Internal Store

SQLite database at `~/.pim/pim.db`.

```sql
CREATE TABLE nodes (
    id              TEXT PRIMARY KEY,  -- PIM URI
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

CREATE TABLE edges (
    id          TEXT PRIMARY KEY,
    source      TEXT NOT NULL REFERENCES nodes(id),
    target      TEXT NOT NULL REFERENCES nodes(id),
    type        TEXT NOT NULL,
    metadata    JSON DEFAULT '{}',
    source_op   TEXT,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE decision_log (
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

-- Indexes
CREATE INDEX idx_nodes_type ON nodes(type);
CREATE INDEX idx_nodes_register ON nodes(register);
CREATE INDEX idx_nodes_adapter ON nodes(adapter);
CREATE INDEX idx_nodes_modified ON nodes(modified_at);
CREATE INDEX idx_edges_source ON edges(source);
CREATE INDEX idx_edges_target ON edges(target);
CREATE INDEX idx_edges_type ON edges(type);
CREATE INDEX idx_edges_source_type ON edges(source, type);
CREATE INDEX idx_edges_target_type ON edges(target, type);
CREATE INDEX idx_decision_log_target ON decision_log(target);
CREATE INDEX idx_decision_log_operation ON decision_log(operation);

-- Full-text search
CREATE VIRTUAL TABLE nodes_fts USING fts5(
    id, type, attributes, body,
    content='nodes', content_rowid='rowid'
);
```

### Relation Index

The `edges` table is the relation index. It holds three categories of edges:

- **Internal-only edges** — relations between nodes in the internal adapter (the only copy)
- **Mirrored edges** — relations that also exist natively in an external adapter, kept in sync for unified querying
- **Cross-adapter edges** — relations between nodes in different adapters (the only copy; no single adapter natively holds these)

The relation index is the component that makes the system more than the sum of its adapters. Without it, each tool is an island. With it, the entire PIM is a connected graph.

### Native Data and the Index Model

The PIM does not replace the data stores of external tools. When an external adapter is active for a type, the native tool is the **storage authority** — the system that holds the authoritative data. The PIM *indexes into* that tool, holding enough information to search, relate, and reason about objects, while the authoritative content remains in the native tool.

This applies to any type managed by an external adapter, not just referential types. An OmniFocus task is sovereign (the user is the authority on its truth), but when the OmniFocus adapter is active, OmniFocus is the storage authority for that task. The PIM holds an index entry. Changes to the task go through the adapter to OmniFocus, and the PIM's index entry is updated to reflect the result. The same applies to topics in OmniFocus, events in Apple Calendar, entries in Day One. Sovereignty is an ontological property (who determines truth). Storage authority is an implementation property (which system holds the data). They are independent.

The rule is simple: **if an external adapter holds a type, the PIM is an index. If the internal adapter holds a type, the PIM is the authoritative store.**

For any type managed by an external adapter, nodes in the PIM are **index entries**. An index entry contains:

- Full metadata (sender, date, subject, status, title, due date — enough to query and display)
- A content excerpt or summary (enough for embedding and semantic search)
- A pointer back to the native tool (the adapter + native_id, resolvable to the full object)

The full content — the complete email body, the task's extended notes, the calendar event's attachments — stays in the native tool and is fetched on demand through the adapter's `fetch_body` operation when the agent needs it.

For types managed by the internal adapter (the default when no external adapter is configured), nodes in the PIM are the authoritative store. There is no native tool to delegate to.

**Three stages of awareness.** The PIM tracks its relationship to each externally-managed object through three states:

**Seen.** The adapter has reported this object during sync. The PIM knows it exists. Tracked by a sync cursor per adapter — a timestamp or sequence number marking the last successful sync.

**Ingested.** The PIM has created an index entry for this object with metadata and content excerpt. Not every seen object is ingested — the adapter may report thousands of archived emails or completed tasks from years past, and the PIM may choose to ingest only recent, active, or relevant objects. The ingestion policy is configurable per adapter.

**Processed.** The agent has triaged the ingested node — extracted objects, created relations, and moved the node out of the scratch register. "Processed" is not a separate flag; it is implied by `register != scratch`.

This three-stage model means the PIM can handle large external data stores without mirroring them entirely. The sync cursor advances through the full store. The ingestion policy selects what enters the graph. The register system tracks what has been attended to.

