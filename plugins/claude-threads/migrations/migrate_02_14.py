"""One-shot migration for pre-existing 02.14 threads.

For each .md file in a directory:
  - Add `thread-id` if absent (8 hex chars)
  - Rename `status:` → `thread-status:` (preserve value)
  - Rename `opener:` → `thread-opener:` (preserve value)
  - Drop `participants:`
  - Add `thread-scope: <given>` (typically the dir's JD ID, e.g. ['02.14'])
  - Preserve everything else (especially `tags:` — never touched)

Idempotent: detects already-migrated by presence of `thread-id` in frontmatter.
"""
import secrets
import sys
from pathlib import Path

# Reach plugin lib/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.frontmatter import parse, write as write_fm
from collections import OrderedDict


def is_already_migrated(path: Path, prefix="thread-") -> bool:
    try:
        fm, _ = parse(path.read_text())
    except OSError:
        return False
    return f"{prefix}id" in fm


def migrate_thread_file(path: Path, *, scope, prefix="thread-"):
    if is_already_migrated(path, prefix=prefix):
        return
    text = path.read_text()
    fm, body = parse(text)

    new_fm = OrderedDict()
    for k, v in fm.items():
        if k == "status":
            new_fm[f"{prefix}status"] = v
        elif k == "opener":
            new_fm[f"{prefix}opener"] = v
        elif k == "participants":
            continue  # drop
        else:
            new_fm[k] = v

    if f"{prefix}id" not in new_fm:
        new_fm[f"{prefix}id"] = secrets.token_hex(4)
    if f"{prefix}scope" not in new_fm:
        new_fm[f"{prefix}scope"] = list(scope)

    path.write_text(write_fm(new_fm, body))


def migrate_directory(threads_dir: Path, *, scope, prefix="thread-"):
    """Run migration on every .md file in the directory. Returns count migrated."""
    n = 0
    for p in threads_dir.iterdir():
        if not p.suffix == ".md":
            continue
        if is_already_migrated(p, prefix=prefix):
            continue
        migrate_thread_file(p, scope=scope, prefix=prefix)
        n += 1
    return n


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("threads_dir")
    parser.add_argument("--scope", required=True, help="CSV of scope tags to add")
    parser.add_argument("--prefix", default="thread-")
    args = parser.parse_args()
    scope = [s.strip() for s in args.scope.split(",") if s.strip()]
    n = migrate_directory(Path(args.threads_dir), scope=scope, prefix=args.prefix)
    print(f"Migrated {n} thread(s).")
