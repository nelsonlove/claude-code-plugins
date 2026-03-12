## Adapter System

### Adapter Registry

The registry tracks which adapters are active and what they handle. It is the routing table consulted for every operation.

```json
{
  "adapters": {
    "internal": {
      "types": {
        "note":     { "operations": ["create","query","update","close"], "registers": ["scratch","reference","working","log"] },
        "entry":    { "operations": ["create","query","update","close"], "registers": ["scratch","reference","working","log"] },
        "task":     { "operations": ["create","query","update","close"], "registers": ["scratch","reference","working","log"] },
        "event":    { "operations": ["create","query","update","close"], "registers": ["scratch","reference","working","log"] },
        "message":  { "operations": ["create","query","update","close"], "registers": ["scratch","reference","working","log"] },
        "contact":  { "operations": ["create","query","update","close"], "registers": ["scratch","reference","working","log"] },
        "resource": { "operations": ["create","query","update","close"], "registers": ["scratch","reference","working","log"] },
        "topic":    { "operations": ["create","query","update","close"], "registers": ["scratch","reference","working","log"] }
      },
      "priority": 0
    }
  },
  "routing": {
    "note": "internal", "entry": "internal", "task": "internal", "event": "internal",
    "message": "internal", "contact": "internal", "resource": "internal", "topic": "internal"
  }
}
```

### Routing Rules

1. Every type has a default adapter (the one in the routing table)
2. Routing can be **register-aware** — different registers of the same type can route to different adapters
3. The internal adapter covers everything by default (priority 0)
4. When an external adapter registers, it takes over its declared types and registers at higher priority
5. Operations on a type go to the adapter that covers that type + register combination; the relation index always lives in the internal store
6. Query operations that span registers fan out across all adapters covering that type and merge results

### Register-Aware Routing: Obsidian + Apple Notes

A user has Obsidian for deep, linked, evolving notes (working register) and Apple Notes for stable reference facts — Wi-Fi passwords, account numbers, quick lookups (reference register). Both handle the Note type, but they serve different registers.

The adapter declarations:

```json
{
  "adapter_id": "obsidian",
  "types": {
    "note": { "operations": ["create","query","update","close"],
              "registers": ["scratch","working"],
              "extended_capabilities": ["backlinks","wikilinks","frontmatter","folders"] }
  },
  "priority": 10
}
```

```json
{
  "adapter_id": "apple-notes",
  "types": {
    "note": { "operations": ["create","query","update","close"],
              "registers": ["reference"],
              "extended_capabilities": ["folders","checklists","sketches"] }
  },
  "priority": 10
}
```

The routing table becomes register-aware for the note type:

```json
{
  "routing": {
    "note": {
      "scratch": "obsidian",
      "working": "obsidian",
      "reference": "apple-notes",
      "log": "internal"
    },
    "entry": "internal",
    "task": "omnifocus",
    "event": "apple-calendar",
    "message": "himalaya",
    "contact": "apple-contacts",
    "resource": "internal",
    "topic": "omnifocus"
  }
}
```

When the user says "save that the Wi-Fi password is XYZ," the agent creates a note in the reference register → routes to Apple Notes. When the user says "start a new note about API design," the agent creates a note in the working register → routes to Obsidian. When the user says "find all my notes about the quarterly review," the agent queries both adapters and merges results.

Types that route to a single adapter use a simple string value. Types that split across registers use an object mapping registers to adapters. Any register not explicitly mapped falls back to internal.

### What Lives Where

The internal adapter is not just a fallback for types without external adapters. It is the permanent home for three categories of data:

**Types with no external tool.** If the user has no note-taking app with an adapter, notes live internally. If they have no journal app, entries live internally. The internal adapter is a complete PIM on its own — it covers all eight types and all four registers.

**Cross-cutting topics.** A topic like "Q3 Review" may span tasks in OmniFocus, notes in Obsidian, messages in email, and events on the calendar. No single external adapter owns it. Even when OmniFocus claims the topic type via routing, the orchestrator may need to maintain internal topics for cross-tool organization. In practice, the system supports dual topic provenance: adapter-native topics (an OmniFocus project) and internal-only topics (a cross-tool area of concern). The routing table determines where *new* topics are created; existing topics live wherever they were created.

**The relation index.** All edges live in the internal store, regardless of which adapters hold the endpoint nodes. This is always true — the internal store is the graph's connective tissue.

In a typical setup, the type distribution looks like:

| Type | Typical Adapter | Why |
|---|---|---|
| Note | internal, or Obsidian/Org-Roam | Often authored through the agent directly |
| Entry | internal, or Day One | Journals are personal; many users create them through the agent |
| Task | OmniFocus, Things, Reminders | Users almost always have a task manager already |
| Event | Apple Calendar, Google Calendar | Calendar apps are deeply OS-integrated |
| Message | Himalaya, Gmail adapter | Email and messaging have their own data stores |
| Contact | Apple Contacts, Google Contacts | Contact management is OS-integrated |
| Resource | internal, or filesystem/bookmark adapter | Varies — some users manage bookmarks externally, others don't |
| Topic | hybrid (see above) | Cross-cutting by nature; often spans multiple adapters |

### Registering an External Adapter

Adapter registration follows the pattern shown above. The OmniFocus adapter declares coverage of task and topic:

```json
{
  "adapter_id": "omnifocus",
  "types": {
    "task":  { "operations": ["create","query","update","close"], "registers": ["scratch","working","log"],
               "extended_capabilities": ["defer_date","flagged","tags","dependencies"] },
    "topic": { "operations": ["create","query","update","close"], "registers": ["scratch","working","log"],
               "extended_capabilities": ["sequential_project","review_interval","folders"] }
  },
  "native_relations": ["belongs-to", "blocks"],
  "priority": 10
}
```

Note: `native_relations` lists canonical directions only. OmniFocus natively represents "contains" and "blocked-by," but the adapter translates to canonical directions: "contains" → inbound `belongs-to`, "blocked-by" → inbound `blocks`.

This updates routing: task → omnifocus, topic → omnifocus. Cross-adapter edges (task → message, topic → contact) live in the relation index.

### Edge Synchronization

The relation index must stay in sync with adapters that natively store relations. The sync mechanism works as follows:

**Adapter → index (inbound sync).** When the orchestrator calls `sync(since)` on a capture-capable adapter, the adapter returns changed nodes *and* changed edges. For each edge the adapter reports, the orchestrator upserts it into the relation index, translating to canonical direction. Edges the adapter reports as deleted are removed from the index. Sync is poll-based — the orchestrator calls `sync` periodically or on demand.

**Index → adapter (outbound sync).** When the orchestrator creates an edge in the relation index between two nodes that share a primary adapter, and that adapter natively supports the relation type, the orchestrator calls `create_edge` on the adapter to push the relation into the native tool. If the adapter does not support the relation type natively, the edge lives only in the index.

**Conflict resolution.** The adapter is authoritative for its native relations. If the adapter reports a state that conflicts with the index (e.g., the user moved a task to a different project directly in OmniFocus), the adapter's state wins and the index is updated. For cross-adapter edges (which live only in the index), the index is authoritative.

**Sync frequency.** On plugin startup, full sync. During a session, incremental sync before any operation that reads from an adapter. Between sessions, no sync occurs — the graph is stale until the next startup.

### Adapter Contract

Every adapter implements:

```
resolve(native_id) → Node
reverse_resolve(pim_uri) → native_id
enumerate(type, filters, pagination) → [Node]
create_node(type, attributes) → Node
query_nodes(type, filters) → [Node]
update_node(native_id, changes) → Node
close_node(native_id, mode) → void
create_edge(source, target, type) → Edge       // if supported
query_edges(node_id, direction, type) → [Edge]  // if supported
update_edge(edge_id, changes) → Edge            // if supported
close_edge(edge_id) → void                      // if supported
sync(since: datetime) → SyncResult              // index entries (metadata + excerpt) for changed objects
fetch_body(native_id) → Content                 // full content body, fetched on demand
dispatch(node_id, method, params) → Result      // for dispatch-capable adapters
```

The `sync` operation returns **index entries** — metadata and content excerpts sufficient for search and embedding — not full copies of external objects. The `fetch_body` operation retrieves the full content from the native tool when the agent needs it for reading, extraction, or detailed analysis. This keeps the PIM lightweight while maintaining the ability to access full content on demand.

Edge operations use canonical directions only. An adapter that natively stores "contains" translates it to an inbound `belongs-to` edge when reporting via `query_edges` or `sync`. The orchestrator never sees inverse labels from adapters.

Each adapter also provides a capability declaration (see the companion adapter contracts for Himalaya and OmniFocus) specifying which types, operations, registers, relations, and extended capabilities it supports. Additionally, each adapter declares an **ingestion policy hint** — which objects should be ingested during sync (e.g., "all unread messages," "messages from the last 30 days," "all contacts") versus which should be seen but not ingested until explicitly requested. The orchestrator uses capability declarations to route operations and degrade gracefully when a capability is unavailable.

### Adapter Loading

Adapters load in three tiers:

**Tier 1: Internal adapter.** Always present. Covers all eight types, all four registers, all operations. The baseline.

**Tier 2: Native PIM adapters.** Declared in `~/.pim/adapters.json`. These are adapters built specifically for the PIM plugin — they speak the adapter contract natively (PIM URIs, typed attributes, register-aware operations). The Himalaya and OmniFocus adapter contracts are examples.

```json
{"adapter_id": "omnifocus", "type": "mcp", "server": "omnifocus-mcp-server",
 "config": {"database_path": "~/Library/Group Containers/com.omnigroup.OmniFocus3/..."}}
```

```json
{"adapter_id": "dayone", "type": "script", "command": "~/.pim/adapters/dayone/adapter.sh",
 "config": {"journal": "Journal"}}
```

**Tier 3: MCP bridge adapters.** External MCP servers installed as separate Claude Code plugins, wrapped into the PIM adapter contract via a translation layer.

A user might have an Apple Reminders MCP, a Google Calendar MCP, or a Notion MCP installed independently of the PIM plugin. These servers expose tool schemas (`create_reminder`, `list_events`, `query_database`) that don't speak the PIM adapter protocol. An MCP bridge adapter wraps an external MCP server to make it usable as a PIM adapter.

The bridge handles translation:

- `pim_create_node(type: "task", attributes: {title: "Buy milk", due_date: "2026-03-15"})` → `create_reminder(title: "Buy milk", dueDate: "2026-03-15", list: "Inbox")`
- `pim_query_nodes(type: "task", register: "scratch")` → `list_reminders(list: "Inbox", completed: false)`
- `pim_close_node(mode: "complete")` → `complete_reminder(id: "...")`
- Register mapping: Reminders lists map to PIM registers (Inbox → scratch, custom lists → working, completed → log)

The bridge also generates a capability declaration that honestly reports what the external MCP supports. Reminders has no `defer_date`, no `blocks` relations, no `sequential_project`. The orchestrator sees these gaps in the capability declaration and degrades gracefully — edges that can't be stored natively live only in the relation index.

**Bridge generation.** Bridges can be:

- **Pre-built** — shipped with the PIM plugin for common MCP servers (Apple Reminders, Google Calendar, Apple Contacts, etc.)
- **Agent-generated** — the config agent examines an external MCP server's tool schema, determines which PIM types and operations it can cover, generates the translation layer, tests it, and registers it. The user says "use my Reminders MCP for simple tasks" and the config agent handles the rest.

Agent-generated bridges are stored in `~/.pim/adapters/bridges/` and can be reviewed and edited by the user.

**Ownership.** When the PIM wraps an external MCP as a bridge adapter, the external tool remains authoritative. The PIM ingests as index entries, not copies. If the user also interacts with the tool directly (creating reminders via Siri, adding calendar events in the app), those changes appear at the next sync. The PIM does not claim exclusive access to the underlying tool.

### Operating Without a Bridge

In some cases, the interpreter may interact with an external MCP server that has no bridge adapter — either because the bridge hasn't been generated yet, or because the user is using a plugin that the PIM doesn't formally recognize as an adapter.

The index model still applies. Even when the interpreter is calling raw MCP tools (e.g., an OmniFocus plugin's `list_tasks` or `create_task`) rather than PIM adapter operations, the same principles hold:

- **The external tool is the source of truth.** The PIM indexes into it. Objects read from the MCP become index entries in the internal store.
- **All objects enter the graph.** The interpreter does not ask the user whether to import "some" or "all" objects. If the tool is connected and the user asked to work with its contents, the contents enter the graph.
- **The interpreter does not ask implementation questions.** "Should I create one node per project or one per task?" is never appropriate. One index entry per object in the external tool. The interpreter maps external objects to PIM types using the ontology (OmniFocus tasks → Task type, OmniFocus projects → Topic type) and creates nodes accordingly.
- **Batch confirmation still applies.** Bulk ingestion from a raw MCP uses `pim_batch_propose` just as it would through a formal adapter. The user sees "I found 75 tasks across 7 projects in OmniFocus — here's a summary" and confirms before the executor commits.

When the interpreter encounters an MCP server it hasn't worked with before, it should delegate to the config agent to examine the MCP's tool schema and either generate a bridge adapter or record the tool mapping in the profile for future sessions. Operating without a bridge is a temporary state, not a permanent mode.

Loading sequence:

1. Plugin starts, loads internal adapter (always present)
2. Reads `~/.pim/adapters.json` for native PIM adapter declarations
3. Scans available MCP servers for potential bridge candidates
4. For each adapter (native or bridge): load, verify contract, register in routing table
5. If an adapter fails to load, its types fall back to internal
6. Log which adapters are active and what they handle

### Migration

When an adapter is swapped, existing nodes of that type need to migrate:

```
pim_migrate(from_adapter: string, to_adapter: string, types: [string]) → MigrationResult
```

Enumerates nodes from the source adapter, creates them in the target, updates PIM URIs in the relation index, and optionally archives source copies.

