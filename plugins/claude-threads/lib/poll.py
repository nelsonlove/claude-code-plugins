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


# v0.2.3 message header: `## <subject> · <ISO-ts> · <author>` (3 segments,
# author last). Pre-0.2.3 wrote `## <author> · <ts>` or `## <author> · <ts>
# · <model>` (no subject, author first).
#
# Both shapes have the same strict ISO-timestamp anchor in the middle, which
# blocks body-subheading false positives like `## Trust posture` (the
# v0.2.1 bug fixed in v0.2.2). The shape difference: in the new format the
# author is the LAST `· <token>` segment; in legacy with model it's the
# token after `## `; in legacy without model it's also the token after `## `.
#
# Strategy: capture the timestamp + everything after the LAST ` · ` (could be
# author OR model) AND the first token after `## ` (could be author OR
# subject). Then dedupe with a heuristic: if both first and last tokens
# differ, the new format treats last as author; if there's only one ·, the
# token after `## ` is the author (legacy 2-segment).
_ISO_TS = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\S*"
# Match: `## <text> · <ts> · <token>` (new format, 3 segments)
_HEADER_NEW = re.compile(
    rf"^## (?P<subject>.+?) · (?P<when>{_ISO_TS}) · (?P<who>\S+)\s*$",
    re.MULTILINE,
)
# Match: `## <token> · <ts>` or `## <token> · <ts> · <token>` (legacy)
_HEADER_LEGACY = re.compile(
    rf"^## (?P<who>\S+) · (?P<when>{_ISO_TS})(?: · \S+)?\s*$",
    re.MULTILINE,
)
# Matches the trailing `· <model>` segment in legacy 3-token headers.
# Used to disambiguate from new format: if the last token looks like a known
# model identifier, it's a legacy header where that's the model and the first
# token is the author. v0.2.0–v0.2.2 wrote these literal values:
#   "unknown"  (CC sessions, CLAUDE_MODEL not exposed to MCP subprocess)
#   "external" (bin/post default when no CLAUDE_MODEL in env)
#   "claude-…", "gpt-…", "llama-…", "mistral-…", "gemini-…" (rare; only if
#   bin/post --model was used or future SDK exposes the var)
_MODEL_TOKEN_RE = re.compile(
    r"^(unknown|external|claude-|gpt-|llama-|mistral-|gemini-|anthropic-|openai-)"
)


def _parse_headers(text):
    """Return ordered [(author, when), ...] for every message header in `text`.

    Disambiguation between new (subject·ts·author) and legacy (author·ts·model)
    shapes — both are 3-segment ISO-anchored — uses _MODEL_TOKEN_RE on the
    trailing token: if it matches a known model identifier, the line is a
    legacy header (author = first token); otherwise treat as new (author =
    last token). Two-segment legacy headers only match _HEADER_LEGACY.

    The strict ISO timestamp anchor in both patterns blocks body subheadings
    like `## Trust posture` from being mis-parsed as headers (the v0.2.1 bug
    fixed in v0.2.2).
    """
    found = {}  # line-start position → (author, when)
    for m in _HEADER_NEW.finditer(text):
        if _MODEL_TOKEN_RE.match(m.group("who")):
            continue  # trailing token is a model name → legacy interpretation
        found[m.start()] = (m.group("who"), m.group("when"))
    for m in _HEADER_LEGACY.finditer(text):
        found.setdefault(m.start(), (m.group("who"), m.group("when")))
    return [found[k] for k in sorted(found)]


def _message_state(path):
    """Return [count, last_author, last_at] for the thread file, or None if
    unreadable / no messages.

    This is the durable "real activity" version marker. It changes only when
    a message is appended (count goes up) or the last message is edited in
    place (author/at tuple changes). It does NOT change when:
      - iCloud sync touches mtime
      - Obsidian Linter rewrites frontmatter (incl. bumping `modified:`)
      - A status flip or scope edit happens (those are metadata, not activity)

    Use as the dedupe key. The `modified:` frontmatter field is unsafe — the
    Linter bumps it on every pass, producing notification storms.
    """
    try:
        text = Path(path).read_text()
    except OSError:
        return None
    headers = _parse_headers(text)
    if not headers:
        return None
    return [len(headers), headers[-1][0], headers[-1][1]]


def _last_message_author(path):
    """Return the handle from the file's last `## <handle> · ...` block, or None."""
    state = _message_state(path)
    return state[1] if state else None


def poll_for_session(*, home, session_id, threads_dir, last_poll_epoch,
                     seen_messages=None):
    """Poll threads_dir for new/changed threads matching session's subscriber tags.

    Filtering layers (in order, cheap → expensive):
    1. mtime > last_poll_epoch (cheap; cuts unchanged files quickly)
    2. seen_messages[thread_id] != [count, last_author, last_at] (semantic
       dedupe; suppresses Linter and iCloud touches that don't add messages)
    3. Subscriber tags match thread scope (the actual matcher)
    4. Last message author != self handle (skip self-triggered echoes)

    Args:
        seen_messages: dict mapping thread_id -> [count, last_author, last_at].
            Pass None to disable semantic dedupe (mtime-only behavior, v0.2.0
            compatible). Pass a dict to enable; updated in-place with the
            current message-state for surfaced threads.

    Returns:
        {new_matches: [...], seen_messages: <updated dict or None>}
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
        # Layer 2: semantic dedupe by message-state tuple. The tuple changes
        # only when a message is appended or the last message is edited.
        # NOTE: v0.2.1 originally tried frontmatter `modified:` here, but
        # peer testing surfaced a Linter-storm failure: Obsidian Linter bumps
        # `modified:` on every pass without changing message content, so that
        # key produced false positives whenever the Linter ran. The message-
        # state tuple is what the Linter doesn't touch.
        cur_state = _message_state(th["path"])
        if seen_messages is not None:
            tid = th["thread_id"]
            if cur_state is not None and seen_messages.get(tid) == cur_state:
                continue
        # Layer 3: scope match
        if not match(tags, th["scope"]):
            continue
        # Layer 4: skip self-author writes
        if handle and cur_state and cur_state[1] == handle:
            continue
        new_matches.append({
            "thread_id": th["thread_id"],
            "title": th["title"],
            "opener": th["opener"],
            "scope": th["scope"],
            "modified": th["modified"],
        })
        if seen_messages is not None and cur_state is not None:
            seen_messages[th["thread_id"]] = cur_state
    return {"new_matches": new_matches, "seen_messages": seen_messages}
