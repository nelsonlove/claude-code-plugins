---
name: brew-execute
description: Execute post-triage actions — uninstall DROPs, generate clean Brewfile, autoremove orphans
allowed-tools:
  - Bash
  - Read
  - Edit
  - AskUserQuestion
---

Execute post-triage actions on `~/Desktop/BREWFILE-AUDIT.org`.

## Behavior

1. Read `~/Desktop/BREWFILE-AUDIT.org` and count states (KEEP/DROP/MAYBE/DEP).

2. **If MAYBEs remain**: Report the count and list them. Offer to go through them conversationally by category — explain each package, check dependencies and usage history, and ask the user to decide. Update the org file as decisions are made. Do NOT batch-annotate silently.

3. **When no MAYBEs remain**:
   a. Show summary table of KEEP/DROP/DEP counts.
   b. For each DROP entry, check if it is actually installed (`brew list --formula`/`--cask`, `brew tap`).
   c. For each installed DROP, check `brew uses --installed <pkg>` — if something KEEP depends on it, **warn the user and skip it** (do not uninstall).
   d. Show the list of packages that will be uninstalled and ask for confirmation.
   e. On confirmation: uninstall formulae first, then casks, then untap. Use `|| true` on each line.
   f. Run `brew autoremove` to clean orphaned deps.
   g. Generate `~/.config/Brewfile.clean` from all KEEP entries (taps, brews, casks, mas — sorted within each group).
   h. Report what was removed, space freed, and where the clean Brewfile is.
