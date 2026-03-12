## Error Handling and Failure Modes

### Adapter Failures

**Adapter unreachable.** If an adapter cannot be contacted during an operation, the orchestrator does not silently fall back to the internal adapter — that would create duplicate nodes. Instead:

- Read operations (query, resolve, review) return partial results with a warning indicating which adapter was unavailable.
- Write operations (create, update, close) fail with an error. The agent informs the user and can offer to retry or to create the node in the internal adapter as a temporary measure, with a migration pending when the adapter recovers.
- On plugin startup, if an adapter fails health check, its types are marked degraded (not rerouted). The interpreter's prompt includes the degraded status so it knows which operations may fail.

**Adapter returns unexpected data.** If an adapter returns nodes that don't conform to the expected type schema (missing required attributes, unrecognized type), the orchestrator logs the malformed response, skips the node, and continues. Malformed data is never silently ingested into the graph.

### Identity Resolution Failures

**Contradictory evidence.** Stage 3 (relation-aware validation) may surface candidates that match on some dimensions but conflict on others — same name but different email, or same email but linked to a different organization. The resolution outcome is "ambiguous" and the operation is escalated to high-risk (user confirmation required). The decision log records both candidates and the conflicting evidence.

**Resolution timeout.** If the semantic index is slow or unavailable, Stage 2 is skipped and resolution proceeds with deterministic lookup only (Stage 1). This degrades gracefully — it won't find fuzzy matches, but it won't block operations.

### Capture Decomposition Failures

**Ambiguous decomposition.** When Claude is not confident about how to decompose raw input (is this a task or a note? is this one event or two?), the agent should propose its best decomposition and ask for confirmation before creating. The `pim_capture` tool returns a `suggestions` field for this purpose — proposed objects and relations that the agent can present for approval rather than executing immediately.

**Partial decomposition.** If some objects are extractable but others are ambiguous, the interpreter directs the executor to create the clear objects (low/medium risk) and surfaces the ambiguous ones as suggestions to the user. This avoids blocking the entire capture on one unclear element.

### Graph Integrity

**Orphaned edges.** If a node is deleted but edges pointing to it remain, the orchestrator cleans up inbound and outbound edges as part of the close operation. Edge deletion is logged in the decision log with the parent node's close operation as the cause.

**Duplicate edges.** Before creating an edge, the orchestrator checks for an existing edge with the same source, target, and type. If one exists, the create is a no-op (idempotent). If one exists with a different type between the same endpoints, both are kept — a note can both belong-to a topic and be annotation-of that topic.

