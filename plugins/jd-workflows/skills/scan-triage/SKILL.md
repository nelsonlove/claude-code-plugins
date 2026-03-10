---
name: scan-triage
description: Use when processing scanned documents — OCR, segment multi-page PDFs into individual documents, classify each, file to JD locations, and create OmniFocus tasks for actionable items. Trigger when the user says "scan triage", "process scans", "OCR this", or drops a PDF for filing.
---

# Scan → OCR → Segment → File → Task

Process scanned multi-page PDFs into individual documents, file them into the JD tree, and create tasks for actionable items.

## Tools

- **OCR**: `swift ~/repos/jd-scan/tools/ocr.swift <pdf> [--pages X-Y] [--images]`
- **PDF split**: `~/repos/jd-scan/tools/split-pdf.sh <input.pdf> <output.pdf> <page-spec>`
- **Filing**: `jd mv`, `jd which`, `jd search`, `jd new`
- **Tasks**: `jd_omnifocus_create_task` or omnifocus-mcp tools

## Workflow

### 1. Identify the PDF

If no path is given, check `01.04 Scans` for unprocessed PDFs. If multiple are present, list them and ask which to process.

### 2. OCR all pages

```sh
swift ~/repos/jd-scan/tools/ocr.swift <pdf> --images
```

This outputs JSON with per-page text and confidence, plus page images in a temp directory.

Read the JSON output. If any page has confidence below 0.5, warn the user — the scan may need preprocessing (deskew, contrast adjustment via ImageMagick).

### 3. Read page images

Use the Read tool to visually examine each page image from the `--images` output. This is critical for:
- Detecting document boundaries (letterheads, form headers, date changes)
- Understanding documents that OCR poorly (handwriting, tables, photos)
- Verifying OCR accuracy

### 4. Segment into documents

Analyze the OCR text AND page images together to identify document boundaries. Look for:
- New letterhead or header
- Different sender/recipient
- Date discontinuities
- Form type changes
- Blank separator pages
- Visual layout changes (letter vs form vs receipt)

Group consecutive pages into documents. For each document, determine:
- **Description**: What is this document?
- **Date**: When was it created/received?
- **JD destination**: Which ID should it be filed to?
- **Actionable?**: Does it require a task in OmniFocus?
- **Proposed filename**: `YYYY-MM-DD description.pdf`

### 5. Present classification

Show the user a table:

| Pages | Document | Date | Destination | Action needed? |
|-------|----------|------|-------------|----------------|
| 1-3 | Letter from BKT re: discovery | 2026-02-28 | `26.21 Court documents` | Review deadlines |
| 4-5 | Capital One statement Feb 2026 | 2026-02-01 | `26.27 Rule 410 production` | None (filing only) |
| 6 | Star Market receipt | 2026-01-15 | `45.02 Receipts archive` | None |

**Wait for user approval before proceeding.** Ask about any uncertain classifications.

### 6. Split and file

For each approved document:

1. **Split**: `~/repos/jd-scan/tools/split-pdf.sh input.pdf "YYYY-MM-DD description.pdf" <page-spec>`
2. **File**: `jd mv "YYYY-MM-DD description.pdf" <jd-id>`
3. **Create task** (if actionable): Use `jd_omnifocus_create_task` with the appropriate JD target

### 7. Clean up

- Delete or archive the original multi-page PDF (ask user which)
- Remove temp image directory
- Report summary: what was filed where, what tasks were created

## Rules

- **Always get approval** before splitting, filing, or creating tasks
- **Use `--images`** — visual inspection catches what OCR misses
- **Date-prefix filenames** — `YYYY-MM-DD description.pdf` for chronological sorting
- **When uncertain about destination, propose `xx.01`** (category unsorted) rather than guessing
- **Flag low-confidence OCR** — don't silently file documents you can't read
- **Never delete the original** without explicit user approval
- **One document = one file** — don't combine unrelated pages
- **Preserve page order** within each document

## Filename conventions

Match existing patterns in the destination directory when possible. Default format:

```
YYYY-MM-DD description.pdf
```

Examples:
- `2026-02-28 BKT discovery deadline letter.pdf`
- `2026-02-01 Capital One statement.pdf`
- `2026-01-15 Star Market receipt.pdf`

## Preprocessing (if needed)

If scan quality is poor, suggest preprocessing before OCR:

```sh
# Deskew
convert input.pdf -deskew 40% deskewed.pdf

# Increase contrast
convert input.pdf -contrast-stretch 1%x1% enhanced.pdf

# Both
convert input.pdf -deskew 40% -contrast-stretch 1%x1% cleaned.pdf
```

Then re-run OCR on the preprocessed version.
