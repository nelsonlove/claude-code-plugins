"""Shared poll logic used by SessionStart, UserPromptSubmit, PostToolUse hooks.

Reads:
  - claude-identity sessions-meta sidecar for tags
  - claude-identity registry for handle (implicit subscription)
  - thread store for current thread files
Returns:
  - {new_matches: [{thread_id, title, opener, scope, modified}, ...]}
"""
import os
from pathlib import Path

from lib.identity_client import read_session_tags, read_session_handle
from lib.match import match
from lib.thread_store import list_threads


def poll_for_session(*, home, session_id, threads_dir, last_poll_epoch):
    tags = read_session_tags(home, session_id)
    handle = read_session_handle(home, session_id)
    if handle:
        tags = list(tags) + [handle]  # implicit handle subscription

    new_matches = []
    for th in list_threads(threads_dir=Path(threads_dir)):
        # Filter by mtime
        try:
            mtime = Path(th["path"]).stat().st_mtime
        except OSError:
            continue
        if mtime <= last_poll_epoch:
            continue
        # Filter by scope match
        if not match(tags, th["scope"]):
            continue
        new_matches.append({
            "thread_id": th["thread_id"],
            "title": th["title"],
            "opener": th["opener"],
            "scope": th["scope"],
            "modified": th["modified"],
        })
    return {"new_matches": new_matches}
