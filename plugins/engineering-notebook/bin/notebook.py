#!/usr/bin/env python3
"""Engineering notebook: generate journal entries from Claude Code sessions.

Usage:
    notebook.py [--date YYYY-MM-DD] [--project FRAGMENT] [--workers N]
    notebook.py --list-dates
    notebook.py --list-projects

Indexes sessions by date/project, resumes each via `claude -p --resume`
to get a summary, then assembles a journal entry.  Summaries are cached
in ~/.local/share/engineering-notebook/ so re-runs are instant.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

DAY_START_HOUR = 5

CACHE_DIR = Path.home() / ".local" / "share" / "engineering-notebook"

SUMMARY_PROMPT = (
    "Summarize this session for an engineering journal entry. "
    "Write in first person. Focus on: what was the goal, what was accomplished, "
    "key decisions made, problems encountered, and anything left unresolved. "
    "If nothing substantive happened (just a greeting, quick lookup, or tool test), "
    "reply with only the word SKIP. Otherwise keep it to 2-5 sentences."
)

# Patterns that indicate the model tried to continue the session instead of summarizing
_NOT_A_SUMMARY = re.compile(
    r"(?i)^("
    r"what (should|would|can) (I|we)|"
    r"what'?s (next|the next)|"
    r"ready to (continue|help|assist|proceed)|"
    r"(hi|hello|hey)\b|"
    r"how can I (help|assist)|"
    r"I('d| would) (be happy|love) to|"
    r"I('m| am) ready to|"
    r"let me know|"
    r"is there anything|"
    r"back\.\s|"
    r"I can see|"
    r"I'll (help|write|prepare|summarize)|"
    r"not logged in"
    r")"
)


def is_real_summary(text: str) -> bool:
    """Return True if text looks like an actual summary, not a confused continuation."""
    if not text or text.upper().strip() == "SKIP":
        return False
    if _NOT_A_SUMMARY.match(text.strip()):
        return False
    return len(text.strip()) > 30


# ── Cache ──────────────────────────────────────────────────────────


def _cache_path() -> Path:
    return CACHE_DIR / "summaries.json"


def load_cache() -> dict:
    path = _cache_path()
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_cache(cache: dict):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path().write_text(json.dumps(cache, indent=2))


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
        "project_dir": str(path.parent),
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


def _cwd_from_project_dir(project_dir: str) -> str | None:
    """Derive the original working directory from a project dir path.

    Project dirs are named like -Users-nelson-Documents, which maps to
    /Users/nelson/Documents.  We resolve using the same hyphen-ambiguity
    logic as project_name_from_path.
    """
    dirname = Path(project_dir).name.lstrip("-")
    # Convert to filesystem path: replace hyphens with /
    candidate = "/" + dirname.replace("-", "/")
    if Path(candidate).is_dir():
        return candidate
    # Try the smart resolver
    home_user = Path.home().name
    prefix = f"Users/{home_user}/"
    if candidate.startswith(f"/Users/{home_user}"):
        raw = dirname[len(f"Users-{home_user}"):].lstrip("-")
        if not raw:
            return str(Path.home())
        resolved = _resolve_hyphenated_path(Path.home(), raw)
        real_path = resolved.replace("~/", str(Path.home()) + "/")
        if Path(real_path).is_dir():
            return real_path
    return None


def summarize_session(session_id: str, project_dir: str | None = None) -> str:
    """Resume a session and ask Claude to summarize it."""
    try:
        result = subprocess.run(
            [
                "claude",
                "-p", SUMMARY_PROMPT,
                "--resume", session_id,
                "--no-session-persistence",
                "--dangerously-skip-permissions",
                "--disable-slash-commands",
                "--output-format", "text",
                "--model", "claude-haiku-4-5-20251001",
                "--max-turns", "1",
            ],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=_cwd_from_project_dir(project_dir) if project_dir else None,
        )
        output = result.stdout.strip()
        if not output or output.upper().startswith("SKIP"):
            return ""
        if not is_real_summary(output):
            return ""
        return output
    except subprocess.TimeoutExpired:
        return f"[Session {session_id[:8]}… timed out]"
    except FileNotFoundError:
        print("Error: 'claude' CLI not found in PATH.", file=sys.stderr)
        sys.exit(1)


def summarize_all(sessions_by_project: dict, workers: int = 4,
                  use_cache: bool = True) -> dict:
    """Summarize all sessions in parallel, grouped by project."""
    cache = load_cache() if use_cache else {}

    # Flatten to (project, session) pairs
    tasks = []
    cached_results = defaultdict(list)
    for project, sessions in sessions_by_project.items():
        for s in sessions:
            sid = s["session_id"]
            if use_cache and sid in cache:
                # Cache hit — empty string means SKIP
                if cache[sid]:
                    cached_results[project].append(cache[sid])
            else:
                tasks.append((project, sid, s.get("project_dir")))

    if cached_results or (use_cache and cache):
        cached_count = sum(len(v) for v in cached_results.values())
        skip_count = sum(
            1 for proj_sessions in sessions_by_project.values()
            for s in proj_sessions
            if s["session_id"] in cache and not cache[s["session_id"]]
        )
        print(f"  Cache: {cached_count} summaries, {skip_count} skips",
              file=sys.stderr)

    results = dict(cached_results)
    total = len(tasks)

    if total == 0:
        print("  All sessions cached — nothing to summarize.", file=sys.stderr)
        return results

    print(f"  Summarizing {total} uncached sessions…", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(summarize_session, sid, pdir): (proj, sid)
            for proj, sid, pdir in tasks
        }
        done = 0
        for future in as_completed(futures):
            proj, sid = futures[future]
            done += 1
            summary = future.result()
            print(f"  [{done}/{total}] {sid[:12]}… "
                  f"{'SKIP' if not summary else 'ok'}", file=sys.stderr)
            # Cache both summaries and skips
            cache[sid] = summary
            if summary:
                results.setdefault(proj, []).append(summary)

    if use_cache:
        save_cache(cache)

    # Clean up orphan dirs left by --no-session-persistence
    _cleanup_orphan_dirs()

    return results


def _cleanup_orphan_dirs():
    """Remove session dirs that have no matching .jsonl file."""
    projects_dir = Path.home() / ".claude" / "projects"
    if not projects_dir.exists():
        return
    skip_names = {"memory", "vercel-plugin", "subagents"}
    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
        try:
            jsonl_ids = {f.stem for f in project_dir.glob("*.jsonl")}
            for d in project_dir.iterdir():
                if (d.is_dir() and d.name not in skip_names
                        and not d.name.startswith(".")
                        and d.name not in jsonl_ids):
                    shutil.rmtree(d, ignore_errors=True)
        except OSError:
            continue


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
    p.add_argument("--index-only", action="store_true", help="Show session index with cache status")
    p.add_argument("--no-cache", action="store_true", help="Force re-summarize all sessions")
    p.add_argument("--cache-stats", action="store_true", help="Show cache statistics")
    args = p.parse_args()

    if args.cache_stats:
        cache = load_cache()
        summaries = sum(1 for v in cache.values() if v)
        skips = sum(1 for v in cache.values() if not v)
        print(f"Cache: {len(cache)} entries ({summaries} summaries, {skips} skips)")
        print(f"Location: {_cache_path()}")
        return

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
        cache = load_cache()
        for proj, sessions in sorted(projects.items()):
            print(f"## {proj} ({len(sessions)} sessions)")
            for s in sessions:
                sid = s["session_id"]
                status = ""
                if sid in cache:
                    status = " [cached: summary]" if cache[sid] else " [cached: skip]"
                print(f"  {sid}  {s['started_at']}{status}")
            print()
        return

    print(f"Summarizing {total} sessions for {date}…", file=sys.stderr)
    summaries = summarize_all(projects, workers=args.workers,
                              use_cache=not args.no_cache)
    print(assemble_journal(date, summaries))


if __name__ == "__main__":
    main()
