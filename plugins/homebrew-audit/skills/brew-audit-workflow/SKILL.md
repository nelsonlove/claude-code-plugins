---
name: Brew Audit Workflow
description: Use when discussing Homebrew package auditing, Brewfile management, or the BREWFILE-AUDIT.org file format. Provides knowledge about the org-mode audit workflow, TODO states, properties drawers, and babel action blocks.
version: 1.1.0
---

The Homebrew audit workflow uses an org-mode file at `~/Desktop/BREWFILE-AUDIT.org` to triage installed Homebrew packages.

## Workflow

1. `/brew-audit` — generate or regenerate the org file from live brew state
2. User triages in Emacs — flip TODO states with `S-left`/`S-right`
3. `/brew-execute` — handles everything after triage:
   - If MAYBEs remain: walk through them conversationally, explain each, update org file
   - If no MAYBEs: uninstall DROPs (with dep checking), autoremove, generate clean Brewfile
4. `/brew-info <pkg>` — deep-dive on any specific package at any time

## Key design principles

- **Conversational triage beats batch annotation.** Go category by category, explain packages in context, check deps and history. Don't pre-annotate everything silently.
- **Always check actual install state.** Cross-reference `brew list` before discussing or uninstalling. Packages may already be gone.
- **Check dependencies before uninstalling.** Run `brew uses --installed <pkg>` — never remove something a KEEP package depends on.
- **Reconcile org state with reality.** On regeneration, auto-mark packages that were triaged but are no longer installed as DROP.

## File structure

The org file has three parts:
1. **Header** — org settings, TODO keywords, column view config, usage instructions
2. **Package entries** — grouped by section, each a level-2 heading with properties drawer
3. **Actions** — static org-babel elisp blocks (from `templates/actions-block.org`)

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

When regenerating, the script preserves existing TODO states and notes by reading the prior org file's PACKAGE properties and matching them to fresh brew data. Packages that were previously triaged but are no longer installed get auto-marked DROP. New packages get heuristic annotations. The babel action blocks come from a static template — they are never regenerated.

## Commands

- `/brew-audit` — generate or regenerate the org file
- `/brew-audit --fresh` — regenerate from scratch (no preserved states)
- `/brew-execute` — post-triage: uninstall DROPs, generate clean Brewfile
- `/brew-info <package>` — deep-dive on a specific package
