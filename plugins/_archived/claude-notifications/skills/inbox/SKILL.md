---
name: inbox
description: View, filter, and dismiss pending notifications from the cross-session inbox. Use when the user says "/inbox", "check inbox", "any notifications", or "clear notifications".
---

# Inbox

Show the user their pending notifications and let them act on them.

## Steps

1. Call `get_notifications` (no tag filter) to fetch all pending notifications.
2. Present them grouped by source, showing tags, date, and message.
3. Ask the user what they'd like to do:
   - Dismiss individual notifications by ID
   - Dismiss all notifications
   - Leave them for later
4. Call `dismiss_notification` for any the user wants to clear.
