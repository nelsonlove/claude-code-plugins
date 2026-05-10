#!/usr/bin/env python3
"""Session manager: audit and clean up Claude Code session files.

Usage:
    sessions.py                    Show session audit
    sessions.py --stats            Show disk usage only
    sessions.py --cleanup          Remove orphan dirs and old sessions
    sessions.py --cleanup --dry-run  Show what would be removed
"""

import argparse
import json
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

PROJECTS_DIR = Path.home() / ".claude" / "projects"
TRASH = Path.home() / ".Trash"


def find_project_dirs():
    """Find all project directories under ~/.claude/projects/."""
    if not PROJECTS_DIR.exists():
        return []
    return [d for d in PROJECTS_DIR.iterdir() if d.is_dir()]


def session_info(jsonl_path: Path) -> dict | None:
    """Extract basic info from a session file."""
    first_ts = None
    last_ts = None
    message_count = 0
    try:
        with open(jsonl_path) as f:
            for line in f:
                try:
                    record = json.loads(line)
                    ts = record.get("timestamp")
                    if ts and record.get("type") in ("user", "assistant"):
                        if not first_ts:
                            first_ts = ts
                        last_ts = ts
                        message_count += 1
                except json.JSONDecodeError:
                    continue
    except (OSError, PermissionError):
        return None

    return {
        "path": jsonl_path,
        "session_id": jsonl_path.stem,
        "first_ts": first_ts,
        "last_ts": last_ts,
        "message_count": message_count,
        "size_bytes": jsonl_path.stat().st_size if jsonl_path.exists() else 0,
    }


def human_size(nbytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(nbytes) < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} TB"


def dir_size(path: Path) -> int:
    total = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    except (OSError, PermissionError):
        pass
    return total


def audit(project_dir: Path) -> dict | None:
    """Audit a single project directory for sessions."""
    try:
        jsonl_files = [f for f in project_dir.glob("*.jsonl") if f.exists()]
        session_dirs = [
            d for d in project_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
            and d.name not in ("memory", "vercel-plugin")
        ]
    except (OSError, FileNotFoundError):
        return None

    # Map session IDs
    jsonl_ids = {f.stem for f in jsonl_files}
    dir_ids = {d.name for d in session_dirs}

    orphan_dirs = [d for d in session_dirs if d.name not in jsonl_ids]
    orphan_jsonls = [f for f in jsonl_files if f.stem not in dir_ids]

    # Gather session details
    sessions = []
    for f in jsonl_files:
        info = session_info(f)
        if info:
            sessions.append(info)

    def safe_size(p: Path) -> int:
        try:
            return p.stat().st_size
        except (OSError, FileNotFoundError):
            return 0

    total_jsonl_size = sum(safe_size(f) for f in jsonl_files)
    total_dir_size = sum(dir_size(d) for d in session_dirs)

    return {
        "project_dir": project_dir,
        "sessions": sessions,
        "jsonl_count": len(jsonl_files),
        "dir_count": len(session_dirs),
        "orphan_dirs": orphan_dirs,
        "orphan_jsonls": orphan_jsonls,
        "total_jsonl_size": total_jsonl_size,
        "total_dir_size": total_dir_size,
    }


def print_audit(audits: list[dict]):
    """Print a formatted audit report."""
    total_sessions = 0
    total_size = 0
    total_orphan_dirs = 0
    total_orphan_jsonls = 0

    for a in audits:
        total_sessions += a["jsonl_count"]
        total_size += a["total_jsonl_size"] + a["total_dir_size"]
        total_orphan_dirs += len(a["orphan_dirs"])
        total_orphan_jsonls += len(a["orphan_jsonls"])

    print("# Session Audit\n")
    print(f"Total sessions: {total_sessions}")
    print(f"Total disk usage: {human_size(total_size)}")
    print(f"Orphan directories (no .jsonl): {total_orphan_dirs}")
    print(f"Orphan .jsonl files (no dir): {total_orphan_jsonls}")
    print()

    for a in sorted(audits, key=lambda x: x["total_jsonl_size"], reverse=True):
        proj_name = a["project_dir"].name
        proj_size = a["total_jsonl_size"] + a["total_dir_size"]
        print(f"## {proj_name}")
        print(f"  Sessions: {a['jsonl_count']}  |  "
              f"Disk: {human_size(proj_size)}  |  "
              f"Orphan dirs: {len(a['orphan_dirs'])}")

        if a["sessions"]:
            # Age breakdown
            now = datetime.now()
            age_buckets = defaultdict(int)
            tiny_count = 0
            for s in a["sessions"]:
                if s["message_count"] <= 2:
                    tiny_count += 1
                if s["first_ts"]:
                    try:
                        ts = s["first_ts"].rstrip("Z").split("+")[0]
                        dt = datetime.fromisoformat(ts)
                        age = (now - dt).days
                        if age <= 1:
                            age_buckets["today"] += 1
                        elif age <= 7:
                            age_buckets["this week"] += 1
                        elif age <= 30:
                            age_buckets["this month"] += 1
                        else:
                            age_buckets["older"] += 1
                    except (ValueError, TypeError):
                        age_buckets["unknown"] += 1

            parts = [f"{v} {k}" for k, v in age_buckets.items()]
            if parts:
                print(f"  Age: {', '.join(parts)}")
            if tiny_count:
                print(f"  Tiny sessions (≤2 messages): {tiny_count}")
        print()


def cleanup(audits: list[dict], older_than_days: int, dry_run: bool):
    """Remove orphan dirs and optionally old/tiny sessions."""
    items_to_remove = []

    for a in audits:
        # Orphan dirs first
        for d in a["orphan_dirs"]:
            items_to_remove.append(("orphan dir", d, dir_size(d)))

        # Old tiny sessions
        now = datetime.now()
        for s in a["sessions"]:
            if s["message_count"] <= 2 and s["first_ts"]:
                try:
                    ts = s["first_ts"].rstrip("Z").split("+")[0]
                    dt = datetime.fromisoformat(ts)
                    age = (now - dt).days
                    if age >= older_than_days:
                        items_to_remove.append(
                            ("stale session", s["path"], s["size_bytes"])
                        )
                        # Also the companion dir
                        companion = s["path"].parent / s["session_id"]
                        if companion.is_dir():
                            items_to_remove.append(
                                ("companion dir", companion, dir_size(companion))
                            )
                except (ValueError, TypeError):
                    continue

    if not items_to_remove:
        print("Nothing to clean up.")
        return

    total_size = sum(size for _, _, size in items_to_remove)
    print(f"{'[DRY RUN] ' if dry_run else ''}Cleanup plan:\n")
    for kind, path, size in items_to_remove:
        print(f"  [{kind}] {path.name} ({human_size(size)})")
    print(f"\nTotal: {len(items_to_remove)} items, {human_size(total_size)}")

    if dry_run:
        print("\nDry run — nothing removed.")
        return

    print()
    for kind, path, size in items_to_remove:
        dest = TRASH / path.name
        if dest.exists():
            # Avoid collision — append timestamp
            dest = TRASH / f"{path.name}-{int(datetime.now().timestamp())}"
        try:
            shutil.move(str(path), str(dest))
            print(f"  Trashed: {path.name}")
        except OSError as e:
            print(f"  Error: {path.name}: {e}", file=sys.stderr)

    print(f"\nDone. {len(items_to_remove)} items moved to Trash.")


def main():
    p = argparse.ArgumentParser(
        description="Audit and clean up Claude Code session files"
    )
    p.add_argument("--cleanup", action="store_true",
                   help="Remove orphan dirs and old tiny sessions")
    p.add_argument("--older-than", type=int, default=30,
                   help="With --cleanup, target sessions older than N days (default: 30)")
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would be removed without doing it")
    p.add_argument("--stats", action="store_true",
                   help="Just show disk usage summary")
    args = p.parse_args()

    project_dirs = find_project_dirs()
    if not project_dirs:
        print("No session directories found.", file=sys.stderr)
        sys.exit(1)

    audits = [a for d in project_dirs if (a := audit(d)) is not None]

    if args.stats:
        total_size = sum(
            a["total_jsonl_size"] + a["total_dir_size"] for a in audits
        )
        total_sessions = sum(a["jsonl_count"] for a in audits)
        print(f"Sessions: {total_sessions}")
        print(f"Disk usage: {human_size(total_size)}")
        return

    if args.cleanup:
        cleanup(audits, args.older_than, args.dry_run)
    else:
        print_audit(audits)


if __name__ == "__main__":
    main()
