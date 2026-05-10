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


def poll_for_session(*, home, session_id, threads_dir, last_poll_epoch,
                     seen_modified=None):
    """Poll threads_dir for new/changed threads matching session's subscriber tags.

    Filtering layers (in order, cheap → expensive):
    1. mtime > last_poll_epoch (cheap; cuts unchanged files quickly)
    2. seen_modified[thread_id] != current modified field (semantic dedupe;
       suppresses iCloud sync events that touch mtime but not content)
    3. Subscriber tags match thread scope (the actual matcher)
    4. Last message author != self handle (skip self-triggered echoes)

    Args:
        seen_modified: dict mapping thread_id -> last-surfaced `modified:` value.
            Pass None to disable semantic dedupe (mtime-only behavior, v0.2.0
            compatible). Pass a dict to enable; the dict is updated in-place
            with the current modified values for surfaced threads.

    Returns:
        {new_matches: [...], seen_modified: <updated dict or None>}
    """
    tags = read_session_tags(home, session_id)
    handle = read_session_handle(home, session_id)
    if handle:
        tags = list(tags) + [handle]  # implicit handle subscription

    new_matches = []
    for th in list_threads(threads_dir=Path(threads_dir)):
        # Layer 1: mtime watermark (cheap; iCloud-noisy but useful first cut)
        try:
            mtime = Path(th["path"]).stat().st_mtime
        except OSError:
            continue
        if mtime <= last_poll_epoch:
            continue
        # Layer 2: semantic dedupe by frontmatter `modified:` field. iCloud sync
        # bumps mtime without changing content, so the frontmatter `modified`
        # value (set by our own _now_iso() on real writes) is the durable
        # version marker. Skip if we've already surfaced this exact version.
        if seen_modified is not None:
            tid = th["thread_id"]
            if seen_modified.get(tid) == th["modified"]:
                continue
        # Layer 3: scope match
        if not match(tags, th["scope"]):
            continue
        # Layer 4: skip self-author writes
        if handle and _last_message_author(th["path"]) == handle:
            continue
        new_matches.append({
            "thread_id": th["thread_id"],
            "title": th["title"],
            "opener": th["opener"],
            "scope": th["scope"],
            "modified": th["modified"],
        })
        if seen_modified is not None:
            seen_modified[th["thread_id"]] = th["modified"]
    return {"new_matches": new_matches, "seen_modified": seen_modified}
