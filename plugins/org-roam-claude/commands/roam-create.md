---
name: roam-create
description: Create a new org-roam note
argument-hint: "<title>"
allowed-tools:
  - mcp__org-roam__create_note
  - mcp__org-roam__search_notes
  - mcp__org-roam__add_link
---

Create a new org-roam note with the given title. Ask the user what the note should contain if no body is obvious from context.

Before creating, do a quick `search_notes` to check if a note with a similar title already exists — if so, mention it and ask if they want to create a new one or edit the existing one.

The note will automatically get the `claude` filetag. If additional tags are appropriate based on the content, include them.

After creating, offer to link it to related existing notes if any are apparent.
