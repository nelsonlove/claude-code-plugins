---
name: triage
description: "PIM inbox triage and scratch register sweep. Use when the user asks to triage, process their inbox, review new items, or sort unsorted items across their tools."
---

# Multi-Inbox Triage

Process the scratch register across all adapters — the unified inbox sweep.

## Process

1. **Gather**: Use `pim_review` or query each type with `register=scratch` to see all inbox items
2. **Present**: Show items grouped by type with source adapter
3. **For each item**, help the user decide:
   - **Promote to working**: Active project, current task, upcoming event
   - **File to reference**: Stable info, contacts, bookmarks
   - **Move to log**: Completed, historical, journal entries
   - **Delete/close**: No longer needed
   - **Link**: Connect to existing topics, contacts, or related items
4. **Execute**: Use `pim_update_node` to change registers, `pim_create_edge` for new links
5. **Discover**: After promoting items, call `pim_discover(node_id=<uri>)` on each to surface connections that may have been missed. Auto-link high-confidence suggestions.

## Triage Order

Process in this order (most actionable first):
1. **Tasks** — need decisions about priority and project assignment
2. **Messages** — may spawn new tasks or events
3. **Events** — check for missing prep or follow-up
4. **Notes** — file or link to topics
5. **Resources** — bookmarks and saved items

## Tips

- Ask about batches, not individual items ("These 5 notes all seem related to Project X — file them all?")
- Suggest relations as you go ("This task mentions Alice — link to her contact?")
- Track what was processed so the user can stop and resume
