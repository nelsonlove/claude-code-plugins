---
name: contact-lookup
description: "PIM contact hub lookup and interaction history. Use when the user asks about a person, wants to see all interactions with a contact, or needs a contact dossier."
---

# Contact Hub Lookup

Traverse the graph from a contact node to compile a complete interaction history.

## Process

1. **Find the contact**: Use `pim_query_nodes(type="contact", filters={"text_search": "name"})`
2. **Resolve identity**: If multiple matches, use `pim_resolve` to check for merged identities
3. **Gather connections**: Use `pim_query_edges(target=<contact_uri>)` to find all related items
4. **Group by type**: Organize results into messages, tasks, events, notes
5. **Present dossier**: Show contact details + interaction timeline

## Dossier Format

```
## Alice Smith
- Email: alice@example.com
- Phone: 555-0123

### Recent Messages (3)
- [Mar 10] Re: Project proposal
- [Mar 8] Meeting follow-up
- [Mar 5] Initial introduction

### Tasks (2)
- [open] Review Alice's draft
- [completed] Send onboarding docs

### Events (1)
- [Mar 12, 2pm] Project kickoff meeting

### Notes (1)
- Alice prefers Slack over email
```

## Tips

- Always check for identity merges — the same person may appear from multiple adapters
- Sort interactions chronologically, most recent first
- Highlight open/active items (pending tasks, upcoming events)
- If the contact has many interactions, summarize and offer to drill down
