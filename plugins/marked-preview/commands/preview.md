---
name: preview
description: Generate markdown and open in Marked 2 for rich preview. Pass a topic to generate, or a file path to preview an existing file.
argument-hint: "<topic or file path>"
---

Preview markdown in Marked 2.

<$ARGUMENTS>

## Instructions

Parse the argument to determine mode:

### File path mode
If the argument looks like a file path (starts with `/`, `~/`, `./`, or ends in `.md`/`.markdown`/`.txt`):

1. Resolve the path (expand `~`)
2. Verify the file exists
3. Open it directly:

```bash
open -a "Marked 2" "<resolved-path>"
```

Report: "Opened <filename> in Marked 2."

### Generate mode
If the argument is a topic or prompt (default):

1. Generate well-structured markdown about the topic. Use headings, lists, tables, code blocks — whatever suits the content. Make it substantive and useful, not a stub.
2. Write to a temp file with a descriptive slug:

```bash
SLUG=$(echo "<topic>" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | head -c 50)
FILE="/tmp/claude-preview-${SLUG}.md"
```

3. Write the markdown content to `$FILE` using the Write tool.
4. Open in Marked:

```bash
open -a "Marked 2" "$FILE"
```

Report: "Generated and opened in Marked 2." Include the temp file path so the user can find it.

### No argument
If no argument is given, ask the user what they'd like to preview.
