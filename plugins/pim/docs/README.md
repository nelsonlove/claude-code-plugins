# PIM Matrix Plugin Architecture

This document is split into numbered sections for readability. Read them in order.

| Section | File | Contents |
|---|---|---|
| 00 | [Overview](00-overview.md) | What the plugin is, the Transparency Principle, component list |
| 01 | [Data Model](01-data-model.md) | Primitives, addressing, SQLite schema, relation index, native data / index model |
| 02 | [Semantic Index](02-semantic-index.md) | Embeddings, per-type and cross-type search, similarity ranking, query interface |
| 03 | [Resolution, Retrieval, Discovery](03-resolution-retrieval-discovery.md) | Identity resolution pipeline, retrieval pipeline, relation discovery with plausibility table |
| 04 | [Write Policy](04-write-policy.md) | Risk tiers, axis-modulated risk, decision logs, type policy matrix, enrichment policy, initial import policy |
| 05 | [Error Handling](05-error-handling.md) | Adapter failures, resolution failures, capture ambiguity, graph integrity |
| 06 | [Tool Interface](06-tool-interface.md) | Boundary tools, lifecycle tools, convenience tools, configuration tools, batch operations |
| 07 | [Adapter System](07-adapter-system.md) | Registry, routing (register-aware), bridges, edge sync, contract, loading, migration, operating without a bridge |
| 08 | [Onboarding](08-onboarding.md) | Conversational interview (with dialogue examples), profile structure, initial import, profile evolution |
| 09 | [Agent Architecture](09-agent-architecture.md) | Constellation (interpreter, executor, briefing, research, discovery, integrity, config), authority boundaries, session lifecycle, cost |
| 10 | [System Prompts](10-system-prompts.md) | Per-agent prompts, example end-to-end workflow, directory structure |

## Companion Documents

- **[PIM Matrix Ontology](../pim-matrix-ontology.md)** — the pure model (axes, types, registers, relations, operations, transforms). The architecture references this as the source of truth.
- **[The PIM Matrix](../the-pim-matrix.md)** — the essay (philosophy and motivation). Needs terminology update.
- **Adapter Contracts** — per-adapter implementation details (Himalaya, OmniFocus). Need terminology update.
