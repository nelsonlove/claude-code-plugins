#!/usr/bin/env python3
"""Detect agent-notebook weekly-rollup gaps.

Scans the JD vault's `03.13 Agent notebook/` for per-session notes, buckets them
by ISO week, and reports which COMPLETED weeks have session notes but no weekly
rollup yet — i.e. the weeks `/notebook-rollup` should generate.

The current in-progress ISO week is never targeted by default: it is not finished,
so its rollup would be partial. Pass --include-current to override.

This is the *narrative* weekly rollup (`rollups/Agent rollup for YYYY-WNN.md`),
distinct from the planned `agent-log-rollup` auditor (a separate someday-spec).

Usage:
    rollup_gaps.py                  JSON: completed weeks with notes but no rollup
    rollup_gaps.py --summary        also print a human summary to stderr
    rollup_gaps.py --week 2026-W26  JSON: just that week's session files (for regen)
    rollup_gaps.py --include-current  also include the current in-progress week

stdout is always JSON. With --week, target_weeks holds (at most) that one week and
flags whether it is already rolled / is the current week. Otherwise target_weeks
lists every completed, unrolled week in ascending order (process them in that order
so each week's "Carrying forward" link points at an already-written prior rollup).
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

NOTEBOOK_DIR = (
    Path.home()
    / "obsidian"
    / "00-09 System"
    / "03 LLMs & agents"
    / "03.13 Agent notebook"
)
ROLLUPS_DIR = NOTEBOOK_DIR / "rollups"

SESSION_RE = re.compile(r"Agent session (\d{4})-(\d{2})-(\d{2})")
ROLLUP_RE = re.compile(r"^Agent rollup for (\d{4})-W(\d{2})\.md$")
WEEK_RE = re.compile(r"^(\d{4})-W(\d{1,2})$")


def week_key(iso_year: int, iso_week: int) -> str:
    return f"{iso_year}-W{iso_week:02d}"


def parse_week(s: str) -> tuple[int, int]:
    m = WEEK_RE.match(s)
    if not m:
        raise ValueError(f"bad week {s!r} (expected YYYY-Www, e.g. 2026-W26)")
    return int(m.group(1)), int(m.group(2))


def collect_sessions() -> dict[str, list[str]]:
    """Map week_key -> sorted session file paths (relative to NOTEBOOK_DIR)."""
    weeks: dict[str, list[str]] = {}
    for path in NOTEBOOK_DIR.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9]/Agent session *.md"):
        m = SESSION_RE.search(path.name)
        if not m:
            continue
        y, mo, d = (int(g) for g in m.groups())
        iso_year, iso_week, _ = date(y, mo, d).isocalendar()
        weeks.setdefault(week_key(iso_year, iso_week), []).append(
            str(path.relative_to(NOTEBOOK_DIR))
        )
    for key in weeks:
        weeks[key].sort()
    return weeks


def existing_rollups() -> set[str]:
    if not ROLLUPS_DIR.is_dir():
        return set()
    out: set[str] = set()
    for path in ROLLUPS_DIR.glob("Agent rollup for *.md"):
        m = ROLLUP_RE.match(path.name)
        if m:
            out.add(week_key(int(m.group(1)), int(m.group(2))))
    return out


def week_record(key: str, files: list[str]) -> dict:
    iso_year, iso_week = parse_week(key)
    monday = date.fromisocalendar(iso_year, iso_week, 1).isoformat()
    sunday = date.fromisocalendar(iso_year, iso_week, 7).isoformat()
    return {
        "week": key,
        "iso_year": iso_year,
        "iso_week": iso_week,
        "monday": monday,
        "sunday": sunday,
        "session_count": len(files),
        "files": files,
        "rollup_path": f"rollups/Agent rollup for {key}.md",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Detect agent-notebook weekly-rollup gaps.")
    ap.add_argument("--week", help="Target a single ISO week (YYYY-Www), even if already rolled.")
    ap.add_argument("--include-current", action="store_true",
                    help="Also include the current in-progress week (normally excluded).")
    ap.add_argument("--summary", action="store_true", help="Print a human-readable summary to stderr.")
    args = ap.parse_args()

    if not NOTEBOOK_DIR.is_dir():
        print(json.dumps({"error": f"notebook dir not found: {NOTEBOOK_DIR}"}))
        return 2

    sessions = collect_sessions()
    rolled = existing_rollups()
    cy, cw, _ = date.today().isocalendar()
    current = week_key(cy, cw)

    if args.week:
        key = week_key(*parse_week(args.week))
        files = sessions.get(key, [])
        rec = week_record(key, files)
        rec["already_rolled"] = key in rolled
        rec["is_current"] = key == current
        result = {
            "current_week": current,
            "target_weeks": [rec] if files else [],
            "note": None if files else f"no session notes found for {key}",
        }
        print(json.dumps(result, indent=2))
        if args.summary:
            if files:
                flags = ""
                if rec["already_rolled"]:
                    flags += " (already rolled — regen)"
                if rec["is_current"]:
                    flags += " (CURRENT in-progress week)"
                print(f"{key}: {len(files)} sessions{flags}", file=sys.stderr)
            else:
                print(f"{key}: no session notes found", file=sys.stderr)
        return 0

    targets: list[dict] = []
    skipped_current: list[str] = []
    for key in sorted(sessions):
        if key in rolled:
            continue
        if parse_week(key) > (cy, cw):
            continue  # future week (clock skew / bad filename) — never target
        if key == current and not args.include_current:
            skipped_current.append(key)
            continue
        targets.append(week_record(key, sessions[key]))

    result = {
        "current_week": current,
        "target_weeks": targets,
        "already_rolled": sorted(rolled),
        "skipped_current": skipped_current,
    }
    print(json.dumps(result, indent=2))

    if args.summary:
        if targets:
            print(f"{len(targets)} week(s) to roll up:", file=sys.stderr)
            for t in targets:
                print(f"  {t['week']}  {t['monday']}–{t['sunday']}  {t['session_count']} sessions",
                      file=sys.stderr)
        else:
            print("Nothing to roll up — all completed weeks already have rollups.", file=sys.stderr)
        if skipped_current:
            print(f"Skipped current in-progress week: {', '.join(skipped_current)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
