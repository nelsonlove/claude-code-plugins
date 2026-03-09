---
name: marked-preview
description: "Generate and preview markdown in Marked 2. Use when the user asks to preview something, wants formatted output, asks for a report/summary/comparison to be displayed nicely, or mentions Marked."
---

# Marked Preview

Marked 2 is a macOS markdown previewer at `/Applications/Marked 2.app`. Use it when the user wants rich formatted output outside the terminal.

## When to use

- User asks to "preview", "show in Marked", or "open in Marked"
- User wants a report, comparison, summary, or any document that benefits from formatted rendering
- User asks to preview an existing markdown file
- User says "make this pretty" or wants output they can print/share

## Opening files

```bash
open -a "Marked 2" "/path/to/file.md"
```

Marked 2 live-reloads — if you update the file, the preview updates automatically.

## Generating previews

1. Write markdown to `/tmp/claude-preview-<slug>.md`
2. Open with `open -a "Marked 2"`
3. Tell the user the file path

Use descriptive slugs derived from the topic. Overwriting the same slug is fine — Marked will reload.

## Tips

- Marked 2 renders GitHub-flavored markdown, including tables, task lists, and fenced code blocks
- For iterative work, reuse the same temp file — Marked live-reloads on save
- The user can use Marked's export features (PDF, HTML, etc.) from the rendered preview
- Or use the `/preview` command directly
