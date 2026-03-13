---
name: capture
description: "Quick PIM capture. Use when the user wants to quickly capture a thought, task, note, event, or any piece of information into the PIM system."
---

# Quick Capture

Decompose unstructured input into typed PIM objects and create them.

## Process

1. **Interpret**: Identify what the user is capturing — note, task, event, contact, etc.
2. **Extract attributes**: Title, status, dates, people mentioned
3. **Route**: Determine the right adapter based on the routing table
4. **Create**: Use `pim_create_node` to create the object in the scratch register
5. **Discover relations**: Call `pim_discover(node_id=<created_uri>)` on the new node to find connections to existing contacts, topics, and related items
6. **Auto-link**: If discovery returns high-confidence suggestions (≥ 0.7), call `pim_discover(node_id=<created_uri>, auto_create=True)` to wire them automatically. Present any remaining suggestions to the user.

## Type Detection Heuristics

| Signal | Type | Register |
|--------|------|----------|
| "todo", "need to", "should", "action" | task | scratch |
| "meeting", "appointment", date+time | event | working |
| "remember", "note:", thought/idea | note | scratch |
| Person name, email, phone | contact | reference |
| URL, article, bookmark | resource | reference |
| Project name, area, category | topic | reference |

## Tips

- Default to `note` if unclear — it's the safest catch-all
- Always place captures in scratch unless the user specifies otherwise
- Extract and suggest relations: "Call Alice about Project X" → task + involves(Alice) + belongs-to(Project X)
- For multi-part captures ("buy groceries and call dentist"), create separate nodes
