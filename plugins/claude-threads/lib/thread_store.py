"""File-per-thread CRUD. Filename: <YYYY-MM-DD> <topic>.md.

Frontmatter schema (default `thread-` prefix; see config.py):
  title, created, modified, aliases, linter-yaml-title-alias  (existing JD)
  thread-id (8 hex), thread-status (open|answered|resolved), thread-opener,
  thread-scope (list of tags)

Plugin never touches the `tags:` array. modified updated on append.
"""
import os
import re
import secrets
import tempfile
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

from lib.frontmatter import parse, write as write_fm, update_keys


def _now_iso():
    """Local time, second precision, no timezone offset.

    Format: 2026-05-10T15:09:07

    Personal-plugin scope — all writes happen on one machine, no need to
    disambiguate across zones. Second precision is enough for the message-
    state dedupe tuple because COUNT distinguishes appends regardless of
    timestamp resolution; same-second edits-in-place by the same author are
    a rare edge case worth living with.
    """
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _today_iso_date():
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")


def _new_thread_id():
    return secrets.token_hex(4)  # 8 hex chars


def _msg_header(author_handle, ts, subject):
    """Format the '## ' message header (v0.2.3 layout):

        ## <subject> · <ts> · <author>

    Subject-first makes threads scannable in Obsidian's outline view. Author
    moves to the END so the matcher's regex can anchor on it reliably (last
    `· <token>` segment).

    Model segment is dropped — CC doesn't expose CLAUDE_MODEL to MCP server
    subprocesses, so v0.2.0–v0.2.2 always wrote 'unknown' there. For non-CC
    posters via bin/post, model still travels in git history via commit
    context, not the message header.
    """
    return f"## {subject} · {ts} · {author_handle}"


def _derive_subject(message, fallback="(no subject)"):
    """Return a single-line subject derived from the first non-empty line of
    the message body, truncated to 60 chars. Used when the caller doesn't
    pass an explicit subject. Falls back to '(no subject)' when the message
    is empty or whitespace-only."""
    for line in message.splitlines():
        line = line.strip()
        if not line:
            continue
        # Strip Markdown heading hashes if the user wrote `# topic` as their first line
        line = re.sub(r"^#+\s+", "", line)
        if not line:
            continue
        # Squeeze internal whitespace so headers stay one line
        line = re.sub(r"\s+", " ", line)
        return line[:60]
    return fallback


def _msg_body(author_handle, message):
    """Compose a message block body without doubling the trailing signature.

    Authors often include their own sign-off in the message text; appending
    the substrate's auto-signature on top produces visible duplicates like:

        message text
        — alice         <- author wrote this
        — alice         <- substrate added this

    Detects existing signatures with em-dash (—), en-dash (–), or ASCII
    double-hyphen (--) prefix. Only appends the auto-signature when the
    message has no matching sign-off."""
    body = message.rstrip()
    expected = f"— {author_handle}"
    last_line = body.rsplit("\n", 1)[-1].strip()
    sigs = (f"— {author_handle}", f"– {author_handle}", f"-- {author_handle}")
    if last_line in sigs:
        return body + "\n"
    return body + "\n\n" + expected + "\n"


def _slug(topic):
    """Filesystem-safe slug. Don't lowercase or strip — preserve human-readable form."""
    safe = re.sub(r"[\\/:*?\"<>|]", "_", topic)
    return safe.strip()


def _resolve_filename(threads_dir, date, slug):
    """Find a unique filename, appending (2), (3), ... if needed."""
    base = Path(threads_dir) / f"{date} {slug}.md"
    if not base.exists():
        return base
    n = 2
    while True:
        candidate = Path(threads_dir) / f"{date} {slug} ({n}).md"
        if not candidate.exists():
            return candidate
        n += 1


def _atomic_write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp, str(path))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def create_thread(*, threads_dir, opener_handle, scope, topic,
                  first_message, author_handle, prefix="thread-",
                  no_reply=False, subject=None):
    """Create a new thread file. Returns {thread_id, path}.

    If no_reply=True, sets `thread-no-reply: true` in frontmatter — append_message
    will refuse to add to it. Use for broadcast/announce threads where replies
    would mtime-storm every subscriber.

    The first message gets `subject` if provided, otherwise the thread topic
    (the topic IS the natural subject of the opener message).
    """
    thread_id = _new_thread_id()
    date = _today_iso_date()
    path = _resolve_filename(threads_dir, date, _slug(topic))

    ts = _now_iso()
    fm = OrderedDict()
    fm["title"] = topic
    fm["created"] = ts
    fm["modified"] = ts
    fm["aliases"] = [topic]
    fm["linter-yaml-title-alias"] = topic
    fm[f"{prefix}id"] = thread_id
    fm[f"{prefix}status"] = "open"
    fm[f"{prefix}opener"] = opener_handle
    fm[f"{prefix}scope"] = list(scope)
    if no_reply:
        fm[f"{prefix}no-reply"] = True

    first_subject = subject if subject else topic
    body = (
        f"\n# {topic}\n\n"
        f"{_msg_header(author_handle, ts, subject=first_subject)}\n\n"
        f"{_msg_body(author_handle, first_message)}"
    )
    _atomic_write(path, write_fm(fm, body))
    return {"thread_id": thread_id, "path": str(path)}


def _find_thread_path(threads_dir, thread_id, prefix="thread-"):
    for p in Path(threads_dir).iterdir():
        if not p.suffix == ".md":
            continue
        try:
            text = p.read_text()
        except OSError:
            continue
        fm, _ = parse(text)
        if fm.get(f"{prefix}id") == thread_id:
            return p
    return None


class ThreadIsNoReply(Exception):
    """Raised by append_message when the thread has thread-no-reply: true set."""
    def __init__(self, thread_id):
        self.thread_id = thread_id
        super().__init__(
            f"thread {thread_id} is marked no-reply (broadcast-only). "
            f"Spawn a side thread tagged 're:{thread_id}' for discussion."
        )


def append_message(*, threads_dir, thread_id, author_handle,
                   message, prefix="thread-", subject=None):
    """Append a message to a thread. If subject is None, derive from message.

    The subject becomes the first segment of the `## ` header so the thread
    reads as a scannable list of message topics in Obsidian's outline view."""
    path = _find_thread_path(threads_dir, thread_id, prefix=prefix)
    if path is None:
        raise KeyError(f"unknown thread-id: {thread_id}")
    text = path.read_text()
    fm, body = parse(text)
    if fm.get(f"{prefix}no-reply") is True:
        raise ThreadIsNoReply(thread_id)
    ts = _now_iso()
    msg_subject = subject if subject else _derive_subject(message)
    new_block = (
        f"\n{_msg_header(author_handle, ts, subject=msg_subject)}\n\n"
        f"{_msg_body(author_handle, message)}"
    )
    fm = update_keys(fm, {"modified": ts})
    _atomic_write(path, write_fm(fm, body + new_block))


def close_thread(*, threads_dir, thread_id, prefix="thread-"):
    path = _find_thread_path(threads_dir, thread_id, prefix=prefix)
    if path is None:
        raise KeyError(f"unknown thread-id: {thread_id}")
    text = path.read_text()
    fm, body = parse(text)
    fm = update_keys(fm, {f"{prefix}status": "resolved", "modified": _now_iso()})
    _atomic_write(path, write_fm(fm, body))


def list_threads(*, threads_dir, prefix="thread-"):
    out = []
    for p in Path(threads_dir).iterdir():
        if not p.suffix == ".md":
            continue
        try:
            text = p.read_text()
        except OSError:
            continue
        fm, _ = parse(text)
        if f"{prefix}id" not in fm:
            continue  # not a thread file
        out.append({
            "thread_id": fm[f"{prefix}id"],
            "status": fm.get(f"{prefix}status", "open"),
            "opener": fm.get(f"{prefix}opener", ""),
            "scope": fm.get(f"{prefix}scope", []),
            "title": fm.get("title", ""),
            "modified": fm.get("modified", ""),
            "path": str(p),
        })
    return out


# v0.2.3 message header: `## <subject> · <ISO-ts> · <author>`. Same shape and
# disambiguation strategy as lib/poll.py — see _parse_headers there for the
# full reasoning. Headers with a trailing model token are read as legacy
# (author = first segment, no subject); otherwise treated as new (author =
# last segment, subject = first).
_ISO_TS = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\S*"
_MSG_RE_NEW = re.compile(
    rf"^## (?P<subject>.+?) · (?P<when>{_ISO_TS}) · (?P<who>\S+)\s*$\n\n?(?P<body>.*?)(?=\n## |\Z)",
    re.DOTALL | re.MULTILINE,
)
_MSG_RE_LEGACY = re.compile(
    rf"^## (?P<who>\S+) · (?P<when>{_ISO_TS})(?: · \S+)?\s*$\n\n?(?P<body>.*?)(?=\n## |\Z)",
    re.DOTALL | re.MULTILINE,
)
_MODEL_TOKEN_RE = re.compile(
    r"^(unknown|external|claude-|gpt-|llama-|mistral-|gemini-|anthropic-|openai-)"
)


def read_thread(*, threads_dir, thread_id, prefix="thread-"):
    path = _find_thread_path(threads_dir, thread_id, prefix=prefix)
    if path is None:
        raise KeyError(f"unknown thread-id: {thread_id}")
    text = path.read_text()
    fm, body = parse(text)
    by_pos = {}  # line-start pos → message dict
    for m in _MSG_RE_NEW.finditer(body):
        if _MODEL_TOKEN_RE.match(m.group("who")):
            continue  # legacy interpretation wins
        by_pos[m.start()] = {
            "from": m.group("who"),
            "at": m.group("when"),
            "subject": m.group("subject"),
            "body": m.group("body").strip(),
        }
    for m in _MSG_RE_LEGACY.finditer(body):
        by_pos.setdefault(m.start(), {
            "from": m.group("who"),
            "at": m.group("when"),
            "subject": None,
            "body": m.group("body").strip(),
        })
    messages = [by_pos[k] for k in sorted(by_pos)]
    return {
        "thread_id": fm.get(f"{prefix}id"),
        "status": fm.get(f"{prefix}status"),
        "opener": fm.get(f"{prefix}opener"),
        "scope": fm.get(f"{prefix}scope", []),
        "title": fm.get("title"),
        "modified": fm.get("modified"),
        "path": str(path),
        "messages": messages,
    }
