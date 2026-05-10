"""Shared poll logic used by SessionStart, UserPromptSubmit, PostToolUse hooks.

Reads:
  - claude-identity sessions-meta sidecar for tags
  - claude-identity registry for handle (implicit subscription)
  - thread store for current thread files
Returns:
  - {new_matches: [{thread_id, title, opener, scope, modified}, ...]}
"""
import os
import re
from pathlib import Path

from lib.identity_client import read_session_tags, read_session_handle
from lib.match import match
from lib.thread_store import list_threads


_LAST_AUTHOR_RE = re.compile(r"^## (\S+) ·", re.MULTILINE)


def _last_message_author(path):
    """Return the handle from the file's last `## <handle> · ...` block, or None."""
    try:
        text = Path(path).read_text()
    except OSError:
        return None
    matches = _LAST_AUTHOR_RE.findall(text)
    return matches[-1] if matches else None


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
        # Skip if the most recent message in the thread is from us — avoids
        # the self-trigger loop where our own write fires PostToolUse, which
        # then surfaces our own thread back to us.
        if handle and _last_message_author(th["path"]) == handle:
            continue
        new_matches.append({
            "thread_id": th["thread_id"],
            "title": th["title"],
            "opener": th["opener"],
            "scope": th["scope"],
            "modified": th["modified"],
        })
    return {"new_matches": new_matches}
