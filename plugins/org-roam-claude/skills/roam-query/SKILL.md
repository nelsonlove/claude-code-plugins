---
name: roam-query
description: >
  Use when the user asks about their notes, wants to look something up in their
  knowledge base, references org-roam, asks "what do I have on...", "find my
  notes about...", or wants to explore connections between topics. Also use when
  the user mentions a topic that might have existing notes worth referencing.
---

# Querying Org-Roam Notes

The user has ~2,400 org-roam notes covering education, psychology, psychoanalysis,
software engineering, literature, and architecture patterns (Alexander's Pattern
Language). Notes are interconnected with `[[id:...][Title]]` links.

## Search Strategy

1. **Start broad**: Use `search_notes` with the topic as query. Check both title
   matches and content matches.
2. **Narrow by tag**: If relevant, filter with `tag` parameter. Common tags:
   `education`, `psych`, `person`, `dev`, `esp`, `api`, `course_notes`,
   `methodology`, `quotes`, `poem`.
3. **Read the note**: Use `get_note` to fetch full content. The response includes
   backlinks and forward links automatically.
4. **Follow links**: Use backlinks and forward links to explore related notes.
   `explore_neighborhood` gives a broader view of a topic cluster.

## Presenting Results

- Lead with the most relevant note's content
- Mention related notes by title with a brief note on how they connect
- If the user seems interested in a cluster, use `explore_neighborhood`
- Don't dump raw JSON — synthesize and summarize

## Writing Notes

When the user wants to capture something:
- `create_note` for new topics
- `update_note` to append to existing notes
- `add_link` to connect notes together
- Always include the `claude` filetag on new notes
- Use org-mode formatting in note bodies (headings, lists, links)
