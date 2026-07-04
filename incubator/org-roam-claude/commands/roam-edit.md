---
name: roam-edit
description: Edit an existing org-roam note
argument-hint: "<title or search>"
allowed-tools:
  - mcp__org-roam__search_notes
  - mcp__org-roam__get_note
  - mcp__org-roam__update_note
  - mcp__org-roam__add_link
---

Edit an existing org-roam note. First search for the note by the argument, then fetch its content with `get_note`.

Show the user the current content and ask what changes they want. Use `update_note` with mode "append" to add new content, or mode "replace" to rewrite the body.

If the user wants to add links to other notes, use `add_link`.
