# Johnny Decimal — Claude Code Integration

If `jd` is not on PATH, use the launcher: `${CLAUDE_PLUGIN_ROOT}/bin/run jd <args>`

## What is Johnny Decimal?

A filing system with three levels: areas (XX-XX), categories (XX), and IDs (XX.YY). Everything has a unique numeric ID.

## How to use the `jd` CLI

All JD operations go through the `jd` command. Never hardcode filesystem paths.

**Finding things:**
- `jd which 26.05` — resolve ID to path
- `jd search sourdough` — search by name
- `jd jdex list 26` — list all indexed IDs in a category
- `jd jdex show 26.05` — show JDex entry details
- `jd ls 26` — tree listing of a category

**Creating things:**
- `jd new id 26 "Name"` — create new ID (auto-numbered)
- `jd new sub 11.24 JEM "Jemima"` — create SUB-ID
- `jd new sub 22.00 "Post title" --sequential` — create sequential SUB

**Moving things:**
- `jd mv 26.01 22.01` — renumber
- `jd mv 26.01 22` — refile to category
- `jd mv 26.01 "New name"` — rename
- `jd mv -a 26.05` — archive
- `jd mv -s 26.05` — move to someday
- `jd restore 26.05` — restore from archive

**System health:**
- `jd validate` — check for issues
- `jd triage` — show busiest unsorted dirs
- `jd jdex adopt` — create JDex entries for unindexed filesystem IDs

## Key principles

- **JDex is source of truth** — IDs exist when they're in the index. Filesystem is downstream.
- **Files go in IDs, not categories** — never save files directly in area or category folders.
- **Standard zeros are reserved** — .00 is JDex/meta, .01 is inbox/unsorted, .02-.09 have defined purposes.
- **Use `jd mv`, never raw `mv`** — the CLI updates the JDex and handles all bookkeeping.
- **Ask before creating** — don't create new IDs without user approval.
- **When unsure, file to unsorted** — `xx.01` (category unsorted) or `01.01` (capture unsorted).
