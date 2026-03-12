---
name: linking
description: "PIM relation creation and graph linking. Use when the user wants to link items, connect nodes, create relationships between PIM objects, or explore how things are connected."
---

# Relation Management

Create and query edges between PIM nodes.

## Relation Families

| Family | Relations | Use for |
|--------|-----------|---------|
| Structural | belongs-to, member-of, references | Organizational hierarchy, topic membership |
| Agency | from, to, involves, delegated-to, sent-by | People connections, message routing |
| Temporal | precedes, occurs-during | Sequencing, scheduling |
| Annotation | annotation-of | Notes attached to other items |
| Derivation | derived-from, blocks | Task dependencies, source tracking |
| Generic | related-to | Catch-all for loose associations |

## Process

1. **Identify source and target nodes**: Resolve URIs or find by search
2. **Choose relation type**: Based on the semantic meaning
3. **Check risk tier**: AUTO relations (references, related-to, belongs-to) can be created freely; VALIDATED and CONFIRMED need user approval
4. **Create edge**: Use `pim_create_edge(source, target, type)`
5. **Explore**: Use `pim_query_edges` to traverse the graph

## Common Patterns

- Task → Topic: `belongs-to` (what project is this for?)
- Task → Contact: `involves` or `delegated-to` (who's responsible?)
- Note → Topic: `belongs-to` (what's this about?)
- Message → Contact: `from` / `to` / `sent-by`
- Event → Contact: `involves` (who's attending?)
- Note → Note: `references` or `related-to`

## Tips

- Use `pim_discover` to get automated suggestions for a node
- The enrichment policy prevents auto-creation of high-risk relations
- When linking contacts, check for identity matches first with `pim_resolve`
