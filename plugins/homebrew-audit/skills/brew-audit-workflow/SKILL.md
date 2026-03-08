---
name: Brew Audit Workflow
description: Use when discussing Homebrew package auditing, Brewfile management, or the BREWFILE-AUDIT.org file format. Provides knowledge about the org-mode audit workflow, TODO states, properties drawers, and babel action blocks.
version: 1.0.0
---

The Homebrew audit workflow uses an org-mode file at `~/Desktop/BREWFILE-AUDIT.org` to triage installed Homebrew packages.

## File structure

The org file has three parts:
1. **Header** — org settings, TODO keywords, column view config, usage instructions
2. **Package entries** — grouped by section, each a level-2 heading with properties drawer
3. **Actions** — static org-babel elisp blocks for summary, uninstall script, and clean Brewfile generation

## TODO states

| State | Key | Meaning |
|-------|-----|---------|
| KEEP  | k   | Install on next machine |
| MAYBE | m   | Undecided — needs more info |
| DROP  | d   | Uninstall now |
| DEP   | p   | Auto-installed dependency |

## Entry format

```org
** KEEP package-name                                     :brew:
:PROPERTIES:
:INSTALLED: 2024-01-15
:TYPE:      brew
:PACKAGE:   package-name
:END:
Package description from brew
/annotation note/
```

Tags: `:brew:`, `:cask:`, `:mas:`, `:tap:`, `:go:`, `:uv:`

## Regeneration

When regenerating, the script preserves existing TODO states and notes by reading the prior org file's PACKAGE properties and matching them to fresh brew data. New packages get heuristic annotations. The babel action blocks come from a static template — they are never regenerated.

## Commands

- `/brew-audit` — generate or regenerate the org file
- `/brew-audit --fresh` — regenerate from scratch (no preserved states)
- `/brew-info <package>` — deep-dive on a specific package

## Workflow

1. Run `/brew-audit` to generate the file
2. Open in Emacs: `emacs ~/Desktop/BREWFILE-AUDIT.org`
3. Triage packages with `S-left`/`S-right` or `C-c C-t`
4. Use `/brew-info <name>` for packages you're unsure about
5. When done, run the babel blocks under `* Actions` in Emacs (`C-c C-c` on each block)
