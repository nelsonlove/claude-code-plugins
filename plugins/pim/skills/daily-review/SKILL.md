---
name: daily-review
description: "PIM daily review and briefing. Use when the user asks for a daily review, morning briefing, status update, or wants to see what's on their plate."
---

# Daily Review

Assemble a contextual briefing of the user's day.

## Briefing Structure

1. **Today's calendar**: Query events with `pim_query_nodes(type="event", text_search="<today's date>")` or `attributes={"date": "<today>"}`
2. **Active tasks**: Query `pim_query_nodes(type="task", register="working")`, especially flagged or due today
3. **Inbox count**: Use `pim_review(register="scratch")` to get inbox items across types, or `pim_stats()` for counts
4. **Recent activity**: What changed since last review (new messages, completed tasks)
5. **Upcoming**: Next 2-3 days' events and deadlines

## Presentation

Present as a concise briefing:

```
## Today (Wednesday, March 12)

### Calendar
- 10:00 Team standup (30 min)
- 14:00 Client call with Alice (1 hr)

### Tasks (3 active, 2 due today)
- [due today] Review proposal draft
- [due today] Send invoice
- [flagged] Prepare presentation

### Inbox (5 new items)
- 2 messages, 1 note, 2 tasks in scratch

### Coming Up
- Tomorrow: Dentist appointment (9:00)
- Friday: Project deadline
```

## Tips

- Keep it scannable — the user wants a quick overview, not a data dump
- Highlight what needs attention today
- Mention items that are overdue or stalled
- If the inbox is large, suggest a triage session
