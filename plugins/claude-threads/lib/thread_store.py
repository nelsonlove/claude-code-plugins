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


def _msg_header(author_handle, ts, author_model):
    """Format the '## ' message header. Omits the model segment when unknown
    (CC doesn't expose CLAUDE_MODEL to MCP server subprocesses, so a literal
    'unknown' clutters every line; rather show fewer fields than wrong ones)."""
    if author_model and author_model.lower() not in ("unknown", "external", ""):
        return f"## {author_handle} · {ts} · {author_model}"
    return f"## {author_handle} · {ts}"


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
                  first_message, author_handle, author_model, prefix="thread-",
                  no_reply=False):
    """Create a new thread file. Returns {thread_id, path}.

    If no_reply=True, sets `thread-no-reply: true` in frontmatter — append_message
    will refuse to add to it. Use for broadcast/announce threads where replies
    would mtime-storm every subscriber.
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

    body = (
        f"\n# {topic}\n\n"
        f"{_msg_header(author_handle, ts, author_model)}\n\n"
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


def append_message(*, threads_dir, thread_id, author_handle, author_model,
                   message, prefix="thread-"):
    path = _find_thread_path(threads_dir, thread_id, prefix=prefix)
    if path is None:
        raise KeyError(f"unknown thread-id: {thread_id}")
    text = path.read_text()
    fm, body = parse(text)
    if fm.get(f"{prefix}no-reply") is True:
        raise ThreadIsNoReply(thread_id)
    ts = _now_iso()
    new_block = (
        f"\n{_msg_header(author_handle, ts, author_model)}\n\n"
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


_MSG_RE = re.compile(r"^## (?P<who>\S+) · (?P<when>\S+) · (?P<model>\S+)\n\n(?P<body>.*?)(?=\n## |\Z)",
                     re.DOTALL | re.MULTILINE)


def read_thread(*, threads_dir, thread_id, prefix="thread-"):
    path = _find_thread_path(threads_dir, thread_id, prefix=prefix)
    if path is None:
        raise KeyError(f"unknown thread-id: {thread_id}")
    text = path.read_text()
    fm, body = parse(text)
    messages = []
    for m in _MSG_RE.finditer(body):
        messages.append({
            "from": m.group("who"),
            "at": m.group("when"),
            "model": m.group("model"),
            "body": m.group("body").strip(),
        })
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
