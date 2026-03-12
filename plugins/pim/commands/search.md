---
description: Cross-system PIM search
argument-hint: "<query>"
allowed-tools: mcp__pim__pim_query_nodes, mcp__pim__pim_query_edges, mcp__pim__pim_resolve
---

Search across all PIM types (notes, tasks, events, contacts, messages, resources, topics) for the given query.

## Context

Use the `pim_query_nodes` tool with `text_search` filter to search across types. Follow edges with `pim_query_edges` to provide context.

## Your task

Search for: $ARGUMENTS

1. Search across all relevant types using `pim_query_nodes` with text_search
2. Group results by type
3. For the top results, follow edges to show connections
4. Present results concisely with URIs for reference
