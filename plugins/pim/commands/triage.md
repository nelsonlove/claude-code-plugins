---
description: Start PIM triage sweep
allowed-tools: mcp__pim__pim_query_nodes, mcp__pim__pim_update_node, mcp__pim__pim_create_edge, mcp__pim__pim_review, AskUserQuestion
---

Process the scratch register (inbox) across all PIM types.

## Your task

1. Use `pim_review` or query each type with `register=scratch` to gather all inbox items
2. Present items grouped by type with counts
3. For each batch, ask the user what to do:
   - Promote to working (active)
   - File to reference
   - Move to log (archive)
   - Link to topics or contacts
4. Execute the user's decisions using `pim_update_node` and `pim_create_edge`
5. Continue until inbox is empty or user stops
