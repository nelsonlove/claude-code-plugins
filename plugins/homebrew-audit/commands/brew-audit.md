---
name: brew-audit
description: Generate or regenerate the Brewfile audit org file at ~/Desktop/BREWFILE-AUDIT.org
argument-hint: "[--fresh]"
allowed-tools:
  - Bash
  - Read
  - Write
---

Generate or regenerate the Homebrew audit org file.

## Behavior

1. Check if `~/Desktop/BREWFILE-AUDIT.org` already exists.
2. If it exists (and `--fresh` was NOT passed), run the generation script with `--existing` to **preserve all prior triage decisions** (KEEP/DROP/MAYBE/DEP states and notes):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate-audit.py \
  --template-dir ${CLAUDE_PLUGIN_ROOT}/templates \
  --existing ~/Desktop/BREWFILE-AUDIT.org \
  --output ~/Desktop/BREWFILE-AUDIT.org
```

3. If `--fresh` was passed or no existing file, run without `--existing`:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate-audit.py \
  --template-dir ${CLAUDE_PLUGIN_ROOT}/templates \
  --output ~/Desktop/BREWFILE-AUDIT.org
```

4. After generation, report:
   - Total packages
   - Breakdown by state (KEEP/DROP/MAYBE/DEP)
   - Any new packages not in the previous file
   - Remind the user to open the file in Emacs: `emacs ~/Desktop/BREWFILE-AUDIT.org`
