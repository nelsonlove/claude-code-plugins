# PIM Plugin — Design Document

Date: 2026-03-12

## Status

Design approved. Ready for implementation planning.

## Canonical Sources

- **Ontology**: `docs/ontology.md` — the formal model (types, registers, relations, operations, transforms)
- **Architecture**: `docs/architecture.md` — the implementation spec (data model, adapters, agents, write policy, semantic index)

This document records implementation decisions made during the design session that supplement those canonical sources.

## What This Is

A Claude Code plugin called `pim` that implements the PIM Matrix architecture. It consolidates and replaces several existing separate plugins (apple-notes, omnifocus, dayone, mail) into one unified personal information management system. The old plugins remain functional during development.

## Implementation Decisions

### Plugin Location

- Plugin source: `~/repos/claude-code-plugins/plugins/pim/`
- Runtime data: `~/.local/share/pim/` (XDG-compliant, not `~/.pim/` as in the architecture doc)
  - `pim.db` — SQLite database
  - `embeddings/` — vector index files
  - `blobs/` — externalized content bodies
  - `profile.json` — user profile
  - `adapters.json` — adapter declarations
  - `adapters/` — adapter scripts and bridge configs
  - `agents/` — subagent memory directories
  - `backups/` — periodic SQLite backups

### Adapter Inventory

Implementing full fidelity to the architecture doc's adapter system. Each adapter implements the contract from the architecture doc (resolve, reverse_resolve, enumerate, create_node, query_nodes, update_node, close_node, sync, fetch_body, dispatch + optional edge operations).

| Adapter | Types Covered | Access Method | Tier |
|---------|--------------|---------------|------|
| internal | all 8 types (fallback) | SQLite direct | 1 (always present) |
| omnifocus | task, topic | JXA via `osascript -l JavaScript` | 2 (native) |
| dayone | entry | `dayone2` CLI | 2 (native) |
| himalaya | message | `himalaya` CLI | 2 (native) |
| apple-calendar | event | `icalbuddy` CLI | 2 (native) |
| apple-notes | note (reference register) | SQLite on NoteStore.sqlite | 2 (native) |
| apple-contacts | contact | `pyobjc` Contacts framework | 2 (native) |
| apple-messages | message (read-only supplement) | SQLite on chat.db | 2 (native, read-only) |
| safari | resource | `plistlib` on Bookmarks.plist | 2 (native) |
| jd | topic (JD areas/categories/IDs) | `jd` CLI | 2 (native) |
| org-roam | note (working register) | `emacsclient --eval` | Deferred (separate plugin in progress) |

Notes:
- `apple-messages` is read-only — no send capability. Himalaya handles outbound message dispatch.
- `jd` adapter validates `jd://` URIs by shelling out to `jd which`. JD areas, categories, and IDs are represented as Topic nodes with `taxonomy_id` set to the JD number.
- `apple-notes` targets the reference register by default (quick lookups, passwords, account numbers). When org-roam is ready, it takes working/scratch registers for notes.
- org-roam is explicitly deferred — a separate plugin is being developed in another session.

### Routing Table (Initial)

```json
{
  "note": {
    "scratch": "internal",
    "working": "internal",
    "reference": "apple-notes",
    "log": "internal"
  },
  "entry": "dayone",
  "task": "omnifocus",
  "event": "apple-calendar",
  "message": "himalaya",
  "contact": "apple-contacts",
  "resource": {
    "scratch": "internal",
    "working": "internal",
    "reference": "safari",
    "log": "internal"
  },
  "topic": {
    "scratch": "omnifocus",
    "working": "omnifocus",
    "reference": "jd",
    "log": "internal"
  }
}
```

### Agent Constellation

Full implementation of the six-agent constellation from the architecture doc:

| Agent | Model | Role |
|-------|-------|------|
| Interpreter | Opus | User-facing. Intent interpretation, ambiguity resolution, delegation. |
| Executor | Sonnet | Write-only graph access. Executes operation plans. |
| Briefing | Sonnet | Session startup. Assembles compressed briefing. |
| Research | Sonnet | Deep retrieval. Four-stage pipeline. |
| Discovery | Sonnet | Relation discovery and enrichment proposals. |
| Config | Sonnet (Opus for onboarding) | System admin, adapter config, profile updates. |

### Semantic Index

Using `sqlite-vec` for vector storage (keeps everything in one SQLite file). Embedding model TBD — likely `text-embedding-3-small` via API or `nomic-embed-text` locally. Per-type partitions + cross-type unified index as specified in the architecture doc.

### MCP Server Architecture

One central MCP server (`server.py`) exposes the ontology tools:
- Boundary: `pim_capture`, `pim_dispatch`
- Node lifecycle: `pim_create_node`, `pim_query_nodes`, `pim_update_node`, `pim_close_node`
- Edge lifecycle: `pim_create_edge`, `pim_query_edges`, `pim_update_edge`, `pim_close_edge`
- Convenience: `pim_resolve`, `pim_review`, `pim_discover`, `pim_transform`, `pim_decision_log`

The MCP server loads adapters, manages the routing table, and enforces the write policy. Adapters are Python modules loaded by the server, not separate MCP servers.

### Skills

Skills teach the interpreter agent workflow patterns. They reference the ontology's vocabulary.

| Skill | Purpose |
|-------|---------|
| search | Cross-system search — how to decompose queries into type-appropriate searches |
| triage | Multi-inbox sweep — how to process scratch register across adapters |
| capture | Quick create — how to decompose input into typed objects |
| daily-review | Session briefing + today's calendar/tasks/flagged items |
| filing | Cross-system filing — register transitions, axis-crossing transforms |
| linking | Explicit link creation/querying, relation family selection |
| contact-lookup | Contact hub traversal — interaction history across messages, events, tasks |

### Commands

| Command | Purpose |
|---------|---------|
| `/pim:search <query>` | Cross-system search |
| `/pim:triage` | Start triage sweep |
| `/pim:capture` | Quick capture |
| `/pim:review` | Daily review |
| `/pim:onboard` | Run onboarding interview (config agent) |
| `/pim:status` | Adapter health + graph stats |

### Build Order

| Tier | Components | Deliverable |
|------|-----------|-------------|
| 1 | Plugin scaffold, data model (SQLite schema), internal adapter, MCP server with node/edge lifecycle tools | Functional graph with internal storage only |
| 2 | Write policy + decision log, risk tier enforcement | Auditable mutations |
| 3 | OmniFocus adapter, Himalaya adapter | Tasks + email integrated |
| 4 | Apple Calendar adapter (icalbuddy), Day One adapter | Events + journal integrated |
| 5 | Apple Notes adapter, Safari adapter | Notes + bookmarks integrated |
| 6 | Apple Contacts adapter (pyobjc), Apple Messages adapter (chat.db) | Contacts + message history |
| 7 | JD adapter (jd CLI) | JD topology as Topics |
| 8 | Semantic index (sqlite-vec, embeddings), identity resolution pipeline | Fuzzy matching, cross-type search |
| 9 | Agent constellation (interpreter, executor, briefing, research, discovery, config) | Full multi-agent architecture |
| 10 | Relation discovery, enrichment policy | Opportunistic link suggestions |
| 11 | Onboarding flow, profile system | Self-configuring system |
| 12 | Skills + commands | User-facing workflows |
| 13 | org-roam adapter | When that plugin is ready |

### Relationship to Existing Plugins

These existing plugins are replaced by pim once the relevant adapter is functional:

| Existing Plugin | Replaced by Adapter | Keep Until |
|----------------|-------------------|------------|
| apple-notes | apple-notes adapter (Tier 5) | Tier 5 complete |
| omnifocus | omnifocus adapter (Tier 3) | Tier 3 complete |
| dayone | dayone adapter (Tier 4) | Tier 4 complete |
| mail | himalaya adapter (Tier 3) | Tier 3 complete |
| jd-workflows | jd adapter (Tier 7) + skills (Tier 12) | Tier 12 complete |

The old plugins stay installed and functional throughout. No breaking changes.

### Open Questions

1. **Embedding model**: API-based (text-embedding-3-small, costs per call) vs. local (nomic-embed-text, free but needs setup). Decision deferred to Tier 8.
2. **Sync frequency**: Architecture says "incremental sync before any operation that reads from an adapter." For adapters that shell out to CLIs (icalbuddy, himalaya), this may be slow. May need caching with TTL.
3. **Apple Messages write capability**: Currently read-only. Sending iMessages programmatically requires Shortcuts or AppleScript — may add later if needed.
4. **org-roam adapter handoff**: When the separate org-roam plugin is ready, it needs to conform to the PIM adapter contract. Coordinate with that session.

## Non-Goals

- This is not a standalone app. It is a Claude Code plugin — Claude is the UI.
- No web interface, no mobile sync, no multi-device.
- No real-time event streaming from adapters. Poll-based sync only.
- No custom embedding model training. Off-the-shelf models only.
