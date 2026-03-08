---
name: brew-info
description: Deep-dive on a Homebrew package — what it is, why it might be installed, disk usage
argument-hint: "<package-name>"
allowed-tools:
  - Bash
  - Read
---

Provide a detailed analysis of a specific Homebrew package.

## Behavior

1. Run `brew info --json=v2 <package-name>` to get package metadata.
2. Check disk usage: `du -sh /opt/homebrew/Cellar/<package-name> 2>/dev/null || du -sh /opt/homebrew/Caskroom/<package-name> 2>/dev/null`
3. Check what depends on it: `brew uses --installed <package-name>`
4. Check if it was installed on request: `brew list --installed-on-request | grep -w <package-name>`

## Output

Provide a concise but informative summary:

- **What it is**: One-line description + expanded context about what the tool does and who uses it
- **Why it might be here**: Based on the user's system (developer, macOS power user), explain likely reasons this was installed
- **Disk usage**: How much space it takes
- **Dependencies**: What depends on it (if anything — removing it could break dependents)
- **Installed on request**: Yes/no — if no, it's a dependency and removing it may be handled by `brew autoremove`
- **Verdict suggestion**: KEEP / MAYBE / DROP with reasoning

If the package is currently marked MAYBE in `~/Desktop/BREWFILE-AUDIT.org`, read that file to find the entry and provide context-aware advice.
