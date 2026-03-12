---
name: daily-review
description: "PIM daily review and briefing. Use when the user asks for a daily review, morning briefing, status update, or wants to see what's on their plate."
---

# Daily Review

Assemble a contextual briefing of the user's day.

## Briefing Structure

1. **Today's calendar**: Query events for today using `pim_query_nodes(type="event")` with date filters
2. **Active tasks**: Query working-register tasks, especially flagged or due today
3. **Inbox count**: Count scratch-register items across types
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
