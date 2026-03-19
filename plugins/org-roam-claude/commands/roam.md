---
name: roam
description: Search org-roam notes
argument-hint: "<query>"
allowed-tools:
  - mcp__org-roam__search_notes
  - mcp__org-roam__get_note
  - mcp__org-roam__get_backlinks
  - mcp__org-roam__get_links
---

Search the user's org-roam notes for the given query. Use `search_notes` with the query argument, then present the results as a concise list with titles and tags.

If the user's query is specific enough to likely match a single note, also fetch the full note with `get_note` and display its content.

If the query is a tag name (e.g. "psych", "education"), use the `tag` parameter instead of `query`.
