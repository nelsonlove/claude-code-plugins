#!/usr/bin/env python3
"""Engineering notebook: generate journal entries from Claude Code sessions.

Usage:
    notebook.py [--date YYYY-MM-DD] [--project FRAGMENT] [--workers N]
    notebook.py --list-dates
    notebook.py --list-projects

Indexes sessions by date/project, resumes each via `claude -p --resume`
to get a summary, then assembles a journal entry.
"""

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

DAY_START_HOUR = 5

SUMMARY_PROMPT = (
    "Summarize this session for an engineering journal entry. "
    "Write in first person. Focus on: what was the goal, what was accomplished, "
    "key decisions made, problems encountered, and anything left unresolved. "
    "If nothing substantive happened (just a greeting, quick lookup, or tool test), "
    "reply with only the word SKIP. Otherwise keep it to 2-5 sentences."
)


# ── Session indexing ────────────────────────────────────────────────


def find_session_files():
    projects_dir = Path.home() / ".claude" / "projects"
    if not projects_dir.exists():
        return []
    return [f for f in projects_dir.rglob("*.jsonl") if "subagents" not in str(f)]


def project_name_from_path(path: Path) -> str:
    raw = path.parent.name.lstrip("-")
    home_user = Path.home().name
    prefix = f"Users-{home_user}-"

    if raw.startswith(prefix):
        return _resolve_hyphenated_path(Path.home(), raw[len(prefix):])
    elif raw.startswith(f"Users-{home_user}"):
        return "~"
    return raw


def _resolve_hyphenated_path(base: Path, encoded: str) -> str:
    parts = encoded.split("-")
    resolved = []
    current = base
    i = 0

    while i < len(parts):
        best = None
        best_j = i + 1
        for j in range(len(parts), i, -1):
            seg = parts[i:j]
            candidates = {"-".join(seg), " ".join(seg)}
            if len(seg) > 2:
                for k in range(1, len(seg)):
                    candidates.add("-".join(seg[:k]) + " " + " ".join(seg[k:]))
            if len(seg) >= 2:
                candidates.add(seg[0] + "." + "-".join(seg[1:]))
                candidates.add(seg[0] + "." + " ".join(seg[1:]))
            for c in candidates:
                if (current / c).exists():
                    best, best_j = c, j
                    break
            if best:
                break
        if best:
            resolved.append(best)
            current = current / best
        else:
            resolved.append(parts[i])
            current = current / parts[i]
        i = best_j

    return "~/" + "/".join(resolved)


def logical_date(timestamp_str: str) -> str:
    try:
        ts = timestamp_str.rstrip("Z").split("+")[0]
        dt = datetime.fromisoformat(ts)
        if dt.hour < DAY_START_HOUR:
            dt -= timedelta(days=1)
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return "unknown"


def index_session(path: Path) -> dict | None:
    first_ts = None
    try:
        with open(path) as f:
            for line in f:
                try:
                    record = json.loads(line)
                    ts = record.get("timestamp")
                    if ts and record.get("type") in ("user", "assistant"):
                        first_ts = ts
                        break
                except json.JSONDecodeError:
                    continue
    except (OSError, PermissionError):
        return None

    if not first_ts:
        return None

    return {
        "session_id": path.stem,
        "project": project_name_from_path(path),
        "date": logical_date(first_ts),
        "started_at": first_ts,
    }


def get_sessions(date: str | None = None, project: str | None = None) -> dict:
    files = find_session_files()
    if not files:
        return {}

    sessions = [s for f in files if (s := index_session(f)) is not None]

    target = date or datetime.now().strftime("%Y-%m-%d")
    if not date and datetime.now().hour < DAY_START_HOUR:
        target = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    filtered = [s for s in sessions if s["date"] == target]
    if project:
        filtered = [s for s in filtered if project.lower() in s["project"].lower()]

    by_project = defaultdict(list)
    for s in filtered:
        by_project[s["project"]].append(s)
    for ps in by_project.values():
        ps.sort(key=lambda x: x["started_at"] or "")

    return {"date": target, "projects": dict(by_project)}


def list_dates() -> list[tuple[str, int]]:
    files = find_session_files()
    sessions = [s for f in files if (s := index_session(f)) is not None]
    counts = defaultdict(int)
    for s in sessions:
        counts[s["date"]] += 1
    return sorted(counts.items())


def list_projects() -> list[tuple[str, int]]:
    files = find_session_files()
    sessions = [s for f in files if (s := index_session(f)) is not None]
    counts = defaultdict(int)
    for s in sessions:
        counts[s["project"]] += 1
    return sorted(counts.items())


# ── Session summarization ───────────────────────────────────────────


def summarize_session(session_id: str) -> str:
    """Resume a session and ask Claude to summarize it."""
    try:
        result = subprocess.run(
            [
                "claude",
                "-p", SUMMARY_PROMPT,
                "--resume", session_id,
                "--no-session-persistence",
                "--dangerously-skip-permissions",
                "--output-format", "text",
                "--model", "claude-haiku-4-5-20251001",
                "--max-turns", "1",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = result.stdout.strip()
        if not output or output.upper().startswith("SKIP"):
            return ""
        return output
    except subprocess.TimeoutExpired:
        return f"[Session {session_id[:8]}… timed out]"
    except FileNotFoundError:
        print("Error: 'claude' CLI not found in PATH.", file=sys.stderr)
        sys.exit(1)


def summarize_all(sessions_by_project: dict, workers: int = 4) -> dict:
    """Summarize all sessions in parallel, grouped by project."""
    # Flatten to (project, session) pairs
    tasks = []
    for project, sessions in sessions_by_project.items():
        for s in sessions:
            tasks.append((project, s["session_id"]))

    results = defaultdict(list)
    total = len(tasks)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(summarize_session, sid): (proj, sid)
            for proj, sid in tasks
        }
        done = 0
        for future in as_completed(futures):
            proj, sid = futures[future]
            done += 1
            print(f"  [{done}/{total}] {sid[:12]}…", file=sys.stderr)
            summary = future.result()
            if summary:
                results[proj].append(summary)

    return dict(results)


# ── Journal assembly ────────────────────────────────────────────────


def assemble_journal(date: str, summaries_by_project: dict) -> str:
    """Combine per-session summaries into a journal entry."""
    if not summaries_by_project:
        return f"# {date}\n\nNo substantive sessions to report.\n"

    lines = []

    if len(summaries_by_project) == 1:
        # Single project — flat entry
        project = next(iter(summaries_by_project))
        summaries = summaries_by_project[project]
        lines.append(f"# {date}\n")
        lines.append(f"*Project: {project}*\n")
        for s in summaries:
            lines.append(s)
            lines.append("")
    else:
        # Multiple projects
        lines.append(f"# {date}\n")
        for project in sorted(summaries_by_project):
            summaries = summaries_by_project[project]
            lines.append(f"## {project}\n")
            for s in summaries:
                lines.append(s)
                lines.append("")

    return "\n".join(lines)


# ── CLI ─────────────────────────────────────────────────────────────


def main():
    p = argparse.ArgumentParser(
        description="Generate engineering journal entries from Claude Code sessions"
    )
    p.add_argument("--date", help="Date (YYYY-MM-DD). Default: today")
    p.add_argument("--project", help="Filter to projects matching this substring")
    p.add_argument("--workers", type=int, default=4, help="Parallel summarizers (default: 4)")
    p.add_argument("--list-dates", action="store_true", help="List available dates")
    p.add_argument("--list-projects", action="store_true", help="List projects")
    p.add_argument("--index-only", action="store_true", help="Show session index, don't summarize")
    args = p.parse_args()

    if args.list_dates:
        for d, count in list_dates():
            print(f"{d} ({count} sessions)")
        return

    if args.list_projects:
        for proj, count in list_projects():
            print(f"{proj} ({count} sessions)")
        return

    data = get_sessions(args.date, args.project)
    if not data.get("projects"):
        recent = [d for d, _ in list_dates()][-5:]
        print(f"No sessions found for {data.get('date', 'today')}.", file=sys.stderr)
        if recent:
            print(f"Recent dates: {', '.join(recent)}", file=sys.stderr)
        sys.exit(1)

    date = data["date"]
    projects = data["projects"]
    total = sum(len(ss) for ss in projects.values())

    if args.index_only:
        for proj, sessions in sorted(projects.items()):
            print(f"## {proj} ({len(sessions)} sessions)")
            for s in sessions:
                print(f"  {s['session_id']}  {s['started_at']}")
            print()
        return

    print(f"Summarizing {total} sessions for {date}…", file=sys.stderr)
    summaries = summarize_all(projects, workers=args.workers)
    print(assemble_journal(date, summaries))


if __name__ == "__main__":
    main()
