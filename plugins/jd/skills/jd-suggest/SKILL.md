---
name: jd-suggest
description: Analyze a directory tree and suggest a Johnny Decimal taxonomy. Use when the user wants to organize a new set of files, create a JD structure from scratch, says "suggest a structure", "organize this", "create a taxonomy", or "jd init --suggest".
---

# Suggest a Johnny Decimal Taxonomy

Analyze a directory tree and propose a JD structure (areas, categories, IDs) that fits the contents.

## Inputs

The user provides a directory path (or defaults to the capture inbox / unsorted folder).

## Process

### 1. Scan the directory

Use `find` to get a representative sample of paths:

```bash
find <path> -maxdepth 5 -not -path '*/.git/*' -not -path '*/node_modules/*' -not -path '*/.venv/*' -not -path '*/__pycache__/*' -not -path '*/site-packages/*' | shuf | head -200
```

If the directory is inside an existing JD tree, also run `jd triage` and `jd ls` for context.

### 2. Analyze and categorize

From the sampled paths, infer the user's activities, projects, and content types. Key principles:

- **Think broadly about areas.** Areas should be very broad life domains (Home, Work, Hobbies, Learning), not specific projects. Max 10.
- **Categories are where work happens.** Each category should represent a type of activity or content. Max 10 per area.
- **IDs are specific things.** Each ID is a single topic, project, or item. Start numbering at .11 (standard zeros .00-.10 are reserved).
- **Underfitting is better than overfitting.** Prefer fewer, broader categories over many narrow ones. You can always split later.
- **Sampling bias is real.** A Python venv or node_modules will dominate the sample. Weight by uniqueness of path structure, not raw count.
- **Infer purpose from context.** A file inside `receipts/2024/` is financial; a file inside `photos/vacation/` is personal media. Use directory names to infer meaning.
- **Disregard cruft.** Ignore iCloud container paths, `.Trash`, `Library`, default system directories. Focus on user-created content.
- **Consider the broader picture.** The taxonomy should cover ALL aspects of the user's life represented in the files, not just the dominant categories in the sample.

### 3. Propose the taxonomy

Present the taxonomy as a tree:

```
10-19 [Area Name]
  11 [Category]
    11.11 [ID]
    11.12 [ID]
  12 [Category]
    12.11 [ID]

20-29 [Area Name]
  21 [Category]
  22 [Category]
```

For each area and category, include a one-line description of what it covers.

### 4. Refine with the user

Ask the user:
- Does this match how you think about your stuff?
- Any areas or categories that should be split, merged, or renamed?
- Anything missing that you know you have but wasn't in the sample?

Iterate until the user is satisfied.

### 5. Generate output

Once approved, offer to:

**Option A — Create a system template:**
```bash
jd template create <name> --from <existing-id>  # if based on existing structure
```
Or write a YAML template file directly to `00.03 Templates/`.

**Option B — Scaffold the tree:**
For each area/category/ID, run:
```bash
jd new category <area> "<name>"
jd new id <category> "<name>"
```

**Option C — Export as markdown:**
Write the taxonomy to a file for further editing before implementation.

## Rules

- **Always get approval** before creating anything on the filesystem.
- **Use `jd` CLI commands** for all filesystem operations.
- **Standard zeros are automatic** — `jd init` creates .00 and .01. Don't include them in the taxonomy.
- **Start IDs at .11** — .00-.10 are reserved for standard zeros.
- **Respect existing structure** — if inside a JD tree, propose additions/reorganization, not a full replacement.
- **Don't over-specify IDs** — propose 3-5 IDs per category as examples. The user will create more as needed.
