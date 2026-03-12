---
name: filing
description: "PIM filing and register transitions. Use when the user wants to file, archive, move items between registers, or organize items into their proper place in the PIM system."
---

# Cross-System Filing

Move items between registers and create proper organizational links.

## Register Transitions

| From | To | Meaning | Example |
|------|----|---------|---------|
| scratch → working | Promoting to active | "I'm working on this now" |
| scratch → reference | Filing for lookup | "Keep this for reference" |
| scratch → log | Archiving | "Done, but keep the record" |
| working → reference | Stabilizing | "This is settled, not changing" |
| working → log | Completing | "Finished this project" |

## Process

1. **Identify the item**: Use `pim_query_nodes` to find the node
2. **Determine destination register**: Based on the user's intent
3. **Update register**: Use `pim_update_node` with `register` change
4. **Create links**: File under a topic, connect to related items
5. **Adapter routing**: If the destination register is served by a different adapter, handle the cross-adapter move

## Tips

- Filing is a good time to add missing relations (topic, contact links)
- When filing batches, group by destination to reduce context switching
- Ask about the topic/project when moving to working or reference
- Log transitions are often paired with closing (tasks completed, events past)
