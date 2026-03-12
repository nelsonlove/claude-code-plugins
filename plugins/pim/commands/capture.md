---
description: Quick PIM capture
argument-hint: "<text to capture>"
allowed-tools: mcp__pim__pim_create_node, mcp__pim__pim_create_edge, mcp__pim__pim_query_nodes
---

Quickly capture a thought, task, note, or any piece of information.

## Your task

Capture: $ARGUMENTS

1. Interpret the input — identify the type (note, task, event, contact, etc.)
2. Extract attributes (title, status, dates, people)
3. Create the node using `pim_create_node` in the scratch register
4. If the input mentions known contacts or topics, suggest linking them
5. Confirm what was created
