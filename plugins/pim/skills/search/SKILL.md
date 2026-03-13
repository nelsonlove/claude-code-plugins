---
name: search
description: "Cross-system PIM search. Use when the user asks to find, search, or look up information across their notes, tasks, events, contacts, messages, or bookmarks. Decomposes queries into type-appropriate searches using PIM MCP tools."
---

# Cross-System Search

Search across the unified PIM graph using `pim_query_nodes` and `pim_query_edges`.

## Strategy

1. **Determine scope**: Does the user want a specific type (tasks, contacts) or a broad search?
2. **Text search**: Use `pim_query_nodes` with `text_search` filter across relevant types
3. **Type-specific queries**: For structured queries (e.g., "overdue tasks"), use type + attribute filters
4. **Graph traversal**: Use `pim_query_edges` to follow connections from found nodes
5. **Present results**: Group by type, show most relevant first

## Query Decomposition

| User intent | PIM operation |
|-------------|--------------|
| "find notes about X" | `pim_query_nodes(type="note", text_search="X")` |
| "who did I meet with last week" | `pim_query_nodes(type="event", text_search="...")` then follow `involves` edges to contacts |
| "tasks related to project Y" | `pim_query_edges(target=<topic_uri>, type="belongs-to")` |
| "everything about Alice" | `pim_query_nodes(type="contact", text_search="Alice")` then `pim_query_edges(target=<contact_uri>)` |

## Tips

- Start broad, narrow based on results
- Always check multiple types unless the user specifies one
- Follow edges to provide context (a task's topic, an event's attendees)
- Use `pim_resolve` for identity disambiguation when multiple contacts match
