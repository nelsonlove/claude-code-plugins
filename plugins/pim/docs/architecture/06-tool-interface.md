## Tool Interface

The PIM exposes tools that map to the ten operations defined in the ontology. Tools are type-agnostic — the caller specifies the object type as a parameter, and the plugin routes to the correct adapter. In the multi-agent constellation, different agents have access to different tool subsets (see Agent Architecture).

### Boundary Tools

```
pim_capture(input: string, source?: string) → CaptureResult
```

Accepts raw input. The plugin (with Claude's help) decomposes it into typed objects and relations. Returns a summary of what was created.

- `input`: raw content — pasted text, transcribed voice memo, email body, URL, etc.
- `source`: optional origin hint — "email", "voice", "clipboard", "url"
- Returns: `{ nodes_created: [PIM URI], edges_created: [Edge ID], suggestions: [...] }`

In practice, capture is a multi-step process: the interpreter analyzes the input and identifies extractable objects, then delegates to the executor to create nodes and edges. The capture tool wraps this workflow.

```
pim_dispatch(target: PIM URI, method?: string, params?: object) → DispatchResult
```

Pushes an object or topic aggregate outward across the sovereignty boundary. The adapter determines what "outward" means:

- Dispatching a message → send email via adapter
- Dispatching a resource → open URL
- Dispatching a topic → aggregate and export/publish

### Lifecycle Tools: Objects

```
pim_create_node(type: string, attributes: object, register?: string) → Node
```

Create a new node. Type must be one of the eight types. Register defaults to scratch.

```
pim_query_nodes(filters: object) → [Node]
```

Find nodes by type, attributes, register, or full-text search.

```json
{
  "type": "task",
  "register": "working",
  "attributes": { "status": "open", "due_before": "2026-03-15" },
  "text_search": "quarterly report",
  "limit": 20
}
```

```
pim_update_node(id: PIM URI, changes: object) → Node
```

Update attributes, content, or register.

```
pim_close_node(id: PIM URI, mode: string) → void
```

Close a node. Mode: "complete", "archive", "cancel", "delete".

### Lifecycle Tools: Relations

```
pim_create_edge(source: PIM URI, target: PIM URI, type: string, metadata?: object) → Edge
```

Create a typed relation. The type is a convenience label (belongs-to, derived-from, etc.); the system validates that the relation is plausible for the endpoint types using the ontology's derived relation families.

```
pim_query_edges(filters: object) → [Edge]
```

Traverse the graph. Filter by source, target, type, direction, or any combination.

```json
{
  "source": "pim://topic/internal/project-acme",
  "type": "belongs-to",
  "direction": "inbound"
}
```

`direction`: "outbound" (from source), "inbound" (to target), "both".

```
pim_update_edge(id: Edge ID, changes: object) → Edge
```

Change type or target (re-file, re-assign).

```
pim_close_edge(id: Edge ID) → void
```

Dissolve a relation.

### Convenience Tools

```
pim_resolve(type: string, hints: object) → ResolveResult
```

Perform identity resolution. Executes the three-stage pipeline and returns one of three outcomes. Does not create or modify anything.

- Returns: `{ outcome: "found" | "ambiguous" | "not_found", node?: Node, candidates?: [Node], confidence: float, evidence: object }`

```
pim_review(scope: object) → ReviewResult
```

Run a contextual review. Fans out queries across adapters and assembles a unified view using the retrieval pipeline.

```json
{"register": "scratch"}
{"type": "task", "attributes": {"due_before": "today"}}
{"topic": "pim://topic/internal/project-acme"}
{"contact": "pim://contact/internal/sarah"}
{"date_range": {"start": "2026-03-03", "end": "2026-03-10"}}
```

```
pim_discover(seed: PIM URI | [PIM URI], threshold?: float) → [ProposedEdge]
```

Run relation discovery against the seed nodes. Returns proposed edges above the confidence threshold, scored and typed. The agent can then create edges (medium risk) or surface them as suggestions to the user.

```
pim_transform(source: PIM URI | [PIM URI], transform: string, target_type?: string) → [Node]
```

Execute a named transform on one or more source nodes.

- `transform`: "extract", "narrate", "distill", "capture", "dispatch"
- `target_type`: optional hint for what to produce

Note: "schedule" is not a transform — the ontology establishes that the diachrony axis is asymmetric. To anchor a synchronic object in time, create a new diachronic object and link it via derivation.

```
pim_decision_log(filters?: object) → [LogEntry]
```

Retrieve decision log entries for auditing, debugging, and undo.

### Configuration Tools

These tools are used by the config agent to manage the system configuration. They are not available to other agents.

```
pim_profile_read() → Profile
```

Read the current user profile. Returns the full `profile.json` contents.

```
pim_profile_update(changes: object) → Profile
```

Update the profile. Accepts a partial object that is merged into the existing profile. Returns the updated profile. Changes are logged.

```
pim_adapter_list() → [AdapterStatus]
```

List all configured adapters with their status (active, degraded, failed), type coverage, and register mappings.

```
pim_adapter_configure(adapter_id: string, config: object) → AdapterStatus
```

Configure a new adapter or update an existing one's configuration. For MCP bridge adapters, this includes the translation layer. Runs a health check before committing.

```
pim_adapter_test(adapter_id: string) → TestResult
```

Test an adapter's contract without registering it. Calls enumerate, verifies response format, reports which types/operations/registers it supports.

```
pim_routing_update(changes: object) → RoutingTable
```

Update the routing table. Accepts partial changes (e.g., `{"task": "omnifocus"}` or `{"note": {"working": "obsidian", "reference": "apple-notes"}}`). Returns the updated routing table.

### Batch Operations

For operations that create or modify many nodes at once — initial import, bulk capture, batch enrichment — the system supports both a confirmation workflow and bulk throughput tools.

#### Bulk Throughput

Individual MCP tool calls for each node and edge are not viable at ingestion scale. Creating 366 message nodes and 1,796 edges one at a time is too slow. The system provides array-based bulk endpoints:

```
pim_create_nodes(nodes: [NodeSpec]) → [Node]
```

Create multiple nodes in a single call. Each `NodeSpec` contains type, attributes, and register. Returns all created nodes with PIM URIs.

```
pim_create_edges(edges: [EdgeSpec]) → [Edge]
```

Create multiple edges in a single call. Each `EdgeSpec` contains source, target, type, and optional metadata. Returns all created edges with IDs.

These are throughput tools, not confirmation tools. They execute immediately. They are used *within* the batch confirmation workflow (the executor calls them to commit an approved batch) and *by subagents* doing bulk ingestion work.

#### Batch Confirmation

For operations requiring user approval — initial import, high-risk bulk changes — the system wraps bulk operations in a propose/confirm workflow.

```
pim_batch_propose(operations: [Operation]) → BatchProposal
```

Accepts a list of proposed operations (create, update, close on nodes and edges). Does NOT execute them. Returns a proposal with a summary and a batch ID:

```json
{
  "batch_id": "batch-20260312-001",
  "summary": {
    "nodes_to_create": 12,
    "edges_to_create": 28,
    "by_type": {"task": 4, "event": 2, "contact": 3, "topic": 1, "message": 2},
    "high_risk": ["contact merge: Sarah Chen (2 candidates)", "new topic: Q3 Review"]
  },
  "operations": [...]
}
```

The interpreter presents the summary to the user. The user can approve all, approve with exclusions, or reject.

```
pim_batch_commit(batch_id: string, exclusions?: [int]) → BatchResult
```

Execute a previously proposed batch. Optional exclusions list indexes of operations to skip. Internally uses `pim_create_nodes` and `pim_create_edges` for throughput. Returns the result of all committed operations.

```
pim_batch_discard(batch_id: string) → void
```

Discard a proposed batch without executing.

The batch confirmation workflow is required (not optional) during initial import and for any operation that would create more than 5 nodes in a single action. The interpreter must present the proposal to the user before the executor commits it.

### Ingestion at Scale

Testing revealed several patterns for bulk ingestion that subagents should follow:

**Pre-partition large workloads.** When a subagent's workload exceeds its context window (e.g., 366 emails with ~5 edges each), the interpreter or executor should pre-partition the data into chunks and dispatch parallel subagents with structured data (JSON arrays of node/edge specs), not free-form instructions. A subagent that receives "index these 366 emails" will hit the context wall. A subagent that receives a JSON array of 70 pre-extracted node specs will succeed.

**One index entry per discrete object.** Every individual task, message, event, contact, and note becomes its own node. Do not create "summary nodes" for groups of objects (e.g., one node representing an entire OmniFocus project's tasks). Summary nodes break queryability — "what involves Sarah?" only works if each task she's involved in is its own node with its own edges.

**Aggregation is appropriate only for undifferentiated collections.** A directory of 70 photos that the user treats as a single unit (not individually queryable) can be represented as a small number of aggregate resource nodes. But tasks, messages, contacts, and events are always individual nodes — they have distinct attributes, distinct relations, and distinct query paths.

### Body-Level Extraction

The content body of an unstructured object (message, note, entry, resource) is the richest source of relational signal in the graph. It must be used for extraction, not just summarization.

**The forwarded-email problem.** In any context where communication is mediated — legal, enterprise, healthcare — messages arrive as forwards. The envelope headers (From/To/CC) identify who forwarded the message to you. The body contains the actual participants: the opposing counsel whose letter was forwarded, the doctor whose report was attached, the colleague whose message was quoted. Header-only extraction misses these entirely. A forwarded email from your attorney containing opposing counsel's letter should produce edges to both your attorney (from the headers) and opposing counsel (from the body).

**The principle: extract from the body, not just the headers.** When ingesting any unstructured object, scan the content body for:

- **Known contacts.** Match names and email addresses from the existing contact graph against the body text. Wire `involves` edges for any contact mentioned, discussed, or quoted — not just envelope participants.
- **Topics and projects.** Match existing topic names, JD numbers, or project keywords against the body. Wire `belongs-to` edges when the content substantively relates to a topic.
- **Embedded actions.** Identify requests, commitments, deadlines, and decisions in the body. These may generate new task or event nodes via extraction.
- **Referenced documents.** Identify mentions of specific documents, filings, reports. Wire `references` edges to existing resource nodes, or create new resource nodes for documents not yet in the graph.
- **Quoted participants.** In forwarded or replied messages, parse quoted headers (`From:`, `To:`, `Sent:`) embedded in the body to identify participants in the original exchange.

This applies to all unstructured types, not just messages. A note that mentions Sarah and references the Q3 report should have edges to both. A journal entry that discusses a meeting with the GAL should have an `involves` edge to the GAL contact. The body is where the information lives — the attributes are just the envelope.

**Implementation.** Body-level extraction runs as part of ingestion, not as a separate pass. When a subagent creates a node for an unstructured object, it reads the body (or excerpt), scans against the known contact list and topic list, and includes the resulting edges in the same batch as the node creation. If the subagent's context is too constrained for body scanning (e.g., bulk ingestion of hundreds of messages), a follow-up extraction pass should be scheduled immediately — not deferred indefinitely.

