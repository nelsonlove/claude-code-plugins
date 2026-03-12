## Agent Architecture

The PIM is not operated by a single agent. It is a constellation of specialized agents, each with its own context window, tool access, and authority boundary. The user-facing agent interprets intent and manages conversation. Subagents handle execution, retrieval, discovery, briefing, and system configuration.

This design solves the statelessness problem: instead of cramming the entire graph state into one context window, the interpreter agent starts lean (profile + briefing summary) and delegates to subagents that load their own context as needed. Each subagent's intermediate work — reading dozens of nodes, searching embeddings, traversing graph neighborhoods — stays in its own context window. Only the compressed result returns to the interpreter.

### The Constellation

**Interpreter** (user-facing)

The agent the user talks to. Its job is understanding what the user means and deciding what to do about it. It holds the profile, the session briefing, and the conversation history. It resolves ambiguity by asking the user directly. It resolves identity ("is this the same Sarah?") using the same conversational skill it uses for intent disambiguation ("which project do you mean?").

The interpreter does not write to the graph. It composes structured operation plans and delegates execution to the executor subagent. This separation ensures that intent interpretation and graph mutation are never conflated — the interpreter decides, the executor acts.

- Context: profile, briefing summary, conversation history, ontology reference
- Tools: `pim_query_nodes`, `pim_query_edges` (read-only, for quick lookups during conversation), `pim_resolve` (for identity resolution), Agent tool (for delegating to subagents)
- Model: Opus (complex reasoning, nuanced intent interpretation)

**Executor** (subagent)

Carries out structured operation plans composed by the interpreter. Receives a plan specifying exactly which nodes to create, which edges to add, which registers to update. Does not interpret user intent — it executes instructions.

The executor is the only agent with write access to the graph. Every mutation passes through it, which means the write policy and decision log are enforced in one place. If the interpreter's plan includes a high-risk operation (merging contacts, deleting nodes), the executor flags it and the interpreter relays the confirmation request to the user. For bulk operations (more than 5 nodes), the executor uses the batch proposal workflow — it proposes the batch and returns the proposal to the interpreter for user confirmation before committing.

- Context: the operation plan from the interpreter, plus whatever nodes it needs to read to execute (e.g., checking for duplicate edges before creating)
- Tools: `pim_create_node`, `pim_update_node`, `pim_close_node`, `pim_create_edge`, `pim_update_edge`, `pim_close_edge`, `pim_capture`, `pim_dispatch`, `pim_batch_propose`, `pim_batch_commit`, `pim_batch_discard`
- Model: Sonnet (execution is well-scoped, doesn't need Opus-level reasoning)
- Returns: a structured report of what was created, updated, or closed, with PIM URIs — or a batch proposal for the interpreter to present to the user

**Briefing** (subagent)

Assembles a session briefing at session start. Reads graph state across all adapters: scratch register counts by type, working register highlights (active topics and their status), upcoming diachronic objects (tasks due soon, events tomorrow), recent activity since last session.

The briefing agent has a persistent memory directory where it maintains a running graph summary. On each invocation, it updates the summary incrementally (what changed since last time) rather than recomputing from scratch. This makes session startup fast even as the graph grows.

- Context: full graph access via query tools, its own memory directory
- Tools: `pim_query_nodes`, `pim_query_edges`, `pim_review` (read-only)
- Memory: `~/.pim/agents/briefing/` — running graph summary, last-session timestamp, register snapshots
- Model: Sonnet
- Returns: compressed markdown briefing (target: under 1K tokens) injected into the interpreter's context
- Invocation: automatically at session start, before the user's first message

**Research** (subagent)

Handles deep retrieval queries that would bloat the interpreter's context. When the user asks "what did I discuss with Sarah last month?" or "show me everything about the Q3 review," the interpreter delegates to the research agent, which runs the full four-stage retrieval pipeline (structured → graph expansion → semantic → prune), reads content bodies from adapters as needed, and composes a narrative summary.

- Context: the research query from the interpreter, plus whatever graph data it reads
- Tools: `pim_query_nodes`, `pim_query_edges`, `pim_review`, adapter `fetch_body` (read-only)
- Model: Sonnet
- Returns: narrative summary with PIM URIs for key objects (so the interpreter can reference them in follow-up operations)

**Discovery** (subagent)

Runs relation discovery and enrichment. Given seed nodes (from a capture, a review, or a scheduled pass), searches the cross-type embedding index for implicit connections, filters by relational plausibility, scores candidates, and returns proposed edges and enrichment metadata.

- Context: seed nodes, cross-type search results, plausibility rules
- Tools: `pim_query_nodes`, `pim_query_edges`, `pim_discover` (read-only; returns proposals, does not commit)
- Memory: `~/.pim/agents/discovery/` — enrichment patterns learned from user feedback (which proposals were accepted vs. rejected)
- Model: Sonnet
- Returns: list of proposed edges with confidence scores, plus proposed enrichment annotations
- Invocation: by the interpreter after capture, during review, or on a scheduled basis

**Integrity** (subagent)

Audits the graph for inconsistencies, staleness, and drift. The discovery agent asks "what connections are missing?" The integrity agent asks "what's wrong with what we already have?"

Specific checks:

- **Staleness:** query adapters for current state, compare with index entries, flag mismatches (deleted externally, attributes changed, moved to different folder/list)
- **Duplicates:** run identity resolution against the existing graph, looking for nodes that probably refer to the same entity but were created separately (two contacts for the same person from different adapters, two topics with overlapping scope)
- **Register hygiene:** find objects stuck in scratch beyond a threshold (configurable, default 2 weeks), objects in working that haven't been modified recently, objects in reference that are no longer being retrieved
- **Orphans:** edges pointing to nodes that no longer exist in their adapter, nodes with no relations that structurally should have some (a task that belongs to no topic, a message with no sender)
- **Profile coherence:** verify the profile's tool mappings match actual adapter state and routing table

The integrity agent is read-only. It returns a structured report of issues found, each with a proposed fix (merge these contacts, archive this stale task, delete this orphaned edge, update this stale attribute). The interpreter presents the report to the user. Approved fixes go to the executor.

- Context: full graph access, adapter sync state, profile
- Tools: `pim_query_nodes`, `pim_query_edges`, `pim_resolve`, `pim_review`, adapter `sync` and `fetch_body` (read-only)
- Memory: `~/.pim/agents/integrity/` — issue history (what was flagged, what was accepted/rejected, recurring problems)
- Model: Sonnet
- Returns: structured issue report with proposed fixes, severity ratings, and affected PIM URIs
- Invocation: by the interpreter during review, on a weekly schedule, or when the user says something like "something seems off" or "clean things up"

**Config** (subagent)

Handles system administration: onboarding interviews, adapter configuration, profile updates, routing changes, migration. This is the only agent that can modify the system configuration files (`profile.json`, `adapters.json`, routing table).

When the user says "I switched to Things for tasks" or "add Raindrop as my bookmark manager," the interpreter recognizes this as a configuration change and delegates to the config agent. The config agent conducts any necessary conversation (via questions returned to the interpreter, which relays them to the user), updates the configuration, tests adapter connections, and runs migration if needed.

- Context: current profile, adapter registry, the configuration change request
- Tools: `pim_profile_read`, `pim_profile_update`, `pim_adapter_list`, `pim_adapter_configure`, `pim_adapter_test`, `pim_routing_update`, `pim_migrate`
- Memory: `~/.pim/agents/config/` — configuration change history, migration log, user preferences about proactivity
- Model: Sonnet (or Opus for initial onboarding, which requires more nuanced conversation)
- Returns: updated configuration summary, migration results if applicable

### Authority Boundaries

The constellation enforces clean separation of concerns:

| Authority | Agent |
|---|---|
| Interpreting user intent | Interpreter only |
| Asking the user questions | Interpreter only (subagents return questions to interpreter for relay) |
| Writing to the graph (nodes, edges) | Executor only |
| Writing to system config | Config only |
| Reading the graph | All agents (via query tools) |
| Proposing new connections | Discovery |
| Proposing fixes to existing state | Integrity |
| Committing any change | Executor (on interpreter's instruction, based on proposals from discovery or integrity) |

No agent crosses another's authority boundary. The interpreter never writes nodes. The executor never interprets intent. The config agent never modifies the graph. Discovery and integrity propose but never commit. This makes the system auditable — every graph mutation traces to an executor action, which traces to an interpreter decision, which traces to user intent or agent policy.

### Session Lifecycle

1. **Startup.** The plugin invokes the briefing agent, which reads graph state and returns a compressed summary. The interpreter's context is assembled: system prompt + profile + adapter registry + briefing summary.

2. **Conversation.** The user interacts with the interpreter. For simple queries, the interpreter responds directly (using its read-only graph access for quick lookups). For complex retrieval, it delegates to the research agent. For mutations, it composes an operation plan and delegates to the executor. For configuration changes, it delegates to the config agent.

3. **Capture.** When the user provides raw input to process, the interpreter analyzes it, runs identity resolution (possibly delegating ambiguous cases to the user as questions), composes an operation plan, and delegates to the executor. After execution, it invokes the discovery agent on the newly created nodes to surface connections.

4. **Review.** The interpreter invokes the research agent with a review scope. The research agent returns a compressed view. The interpreter presents it to the user. Triage decisions (promote to working, file as reference, discard) are composed as operation plans and sent to the executor.

5. **Shutdown.** No explicit shutdown step. The briefing agent's memory is updated during its next invocation (next session start). The discovery agent's memory is updated when its proposals are accepted or rejected.

### Cost and Model Selection

Subagents run on Sonnet by default for cost efficiency. The interpreter runs on Opus because intent interpretation, ambiguity resolution, and conversation management require stronger reasoning. The config agent may use Opus during initial onboarding (which is a complex, nuanced conversation) and Sonnet for routine configuration changes.

The interpreter should prefer direct graph queries over subagent delegation for simple operations. "What's the due date on that task?" doesn't need a research subagent — a single `pim_query_nodes` call in the interpreter's context is faster and cheaper. Subagent delegation is for operations where the intermediate context would be large: multi-hop traversals, cross-type searches, batch operations.

