"""Thread file CRUD tests."""
import json
from pathlib import Path

import pytest

from lib.thread_store import (
    create_thread, append_message, read_thread, list_threads, close_thread
)


def test_create_thread_writes_file_with_schema(tmp_home, threads_dir):
    th = create_thread(
        threads_dir=threads_dir,
        opener_handle="alice",
        scope=["02.14"],
        topic="reconcile inbox triage",
        first_message="Initial message body",
        author_handle="alice",
    )
    assert th["thread_id"]
    assert len(th["thread_id"]) == 8
    path = Path(th["path"])
    assert path.exists()
    text = path.read_text()
    assert "thread-id:" in text
    assert "thread-status: open" in text
    assert "thread-opener: alice" in text
    assert 'thread-scope: ["02.14"]' in text
    assert "Initial message body" in text


def test_create_thread_does_not_write_tags_field(tmp_home, threads_dir):
    th = create_thread(threads_dir=threads_dir, opener_handle="alice",
                       scope=["02.14"], topic="t", first_message="m",
                       author_handle="alice")
    text = Path(th["path"]).read_text()
    # Plugin must not auto-add tags: field
    fm = text.split("---")[1]
    assert "tags:" not in fm


def test_filename_format(tmp_home, threads_dir, monkeypatch):
    """Filename: YYYY-MM-DD <topic>.md"""
    import lib.thread_store as ts
    monkeypatch.setattr(ts, "_today_iso_date", lambda: "2026-05-09")
    th = create_thread(threads_dir=threads_dir, opener_handle="a",
                       scope=["x"], topic="reconcile inbox triage",
                       first_message="m", author_handle="a")
    assert Path(th["path"]).name == "2026-05-09 reconcile inbox triage.md"


def test_filename_collision_appends_numeric(tmp_home, threads_dir, monkeypatch):
    import lib.thread_store as ts
    monkeypatch.setattr(ts, "_today_iso_date", lambda: "2026-05-09")
    create_thread(threads_dir=threads_dir, opener_handle="a", scope=["x"],
                  topic="dup", first_message="m1", author_handle="a")
    th2 = create_thread(threads_dir=threads_dir, opener_handle="a", scope=["x"],
                       topic="dup", first_message="m2", author_handle="a")
    assert Path(th2["path"]).name == "2026-05-09 dup (2).md"


def test_append_message_updates_modified(tmp_home, threads_dir):
    th = create_thread(threads_dir=threads_dir, opener_handle="a", scope=["x"],
                      topic="t", first_message="m1", author_handle="a")
    import time; time.sleep(1.05)  # _now_iso is second-precision; need >1s to observe a bump
    append_message(threads_dir=threads_dir, thread_id=th["thread_id"],
                   author_handle="bob",
                   message="reply body")
    text = Path(th["path"]).read_text()
    # v0.2.3 header: `## <subject> · <ts> · <author>` — author is at the end.
    assert "· bob\n" in text
    assert "reply body" in text
    # modified should be newer than created
    fm_section = text.split("---")[1]
    import re
    created = re.search(r"^created:\s*(.*)$", fm_section, re.MULTILINE).group(1).strip()
    modified = re.search(r"^modified:\s*(.*)$", fm_section, re.MULTILINE).group(1).strip()
    assert modified > created


def test_close_thread_sets_status_resolved(tmp_home, threads_dir):
    th = create_thread(threads_dir=threads_dir, opener_handle="a", scope=["x"],
                      topic="t", first_message="m", author_handle="a")
    close_thread(threads_dir=threads_dir, thread_id=th["thread_id"])
    text = Path(th["path"]).read_text()
    assert "thread-status: resolved" in text
    # Original `open` line should be gone
    assert "thread-status: open" not in text


def test_list_threads_returns_all(tmp_home, threads_dir):
    create_thread(threads_dir=threads_dir, opener_handle="a", scope=["02.14"],
                  topic="t1", first_message="m", author_handle="a")
    create_thread(threads_dir=threads_dir, opener_handle="b", scope=["74.01"],
                  topic="t2", first_message="m", author_handle="b")
    threads = list_threads(threads_dir=threads_dir)
    assert len(threads) == 2


def test_read_thread_returns_structured(tmp_home, threads_dir):
    th = create_thread(threads_dir=threads_dir, opener_handle="alice", scope=["02.14"],
                      topic="t", first_message="hello", author_handle="alice")
    out = read_thread(threads_dir=threads_dir, thread_id=th["thread_id"])
    assert out["thread_id"] == th["thread_id"]
    assert out["status"] == "open"
    assert out["opener"] == "alice"
    assert out["scope"] == ["02.14"]
    assert len(out["messages"]) == 1
    assert "hello" in out["messages"][0]["body"]


def test_create_thread_no_reply_writes_flag(tmp_home, threads_dir):
    """no_reply=True writes thread-no-reply: true in frontmatter."""
    from pathlib import Path
    th = create_thread(threads_dir=threads_dir, opener_handle="a", scope=["announce"],
                       topic="broadcast", first_message="m",
                       author_handle="a", no_reply=True)
    text = Path(th["path"]).read_text()
    assert "thread-no-reply: true" in text


def test_create_thread_default_omits_no_reply_flag(tmp_home, threads_dir):
    """no_reply defaults to False; field is omitted entirely."""
    from pathlib import Path
    th = create_thread(threads_dir=threads_dir, opener_handle="a", scope=["02.14"],
                       topic="t", first_message="m",
                       author_handle="a")
    text = Path(th["path"]).read_text()
    assert "thread-no-reply" not in text


def test_append_message_to_no_reply_thread_raises(tmp_home, threads_dir):
    """append_message refuses no-reply threads with a clear error directing the
    caller to spawn a side thread."""
    from lib.thread_store import append_message, ThreadIsNoReply
    th = create_thread(threads_dir=threads_dir, opener_handle="a", scope=["announce"],
                       topic="t", first_message="m",
                       author_handle="a", no_reply=True)
    with pytest.raises(ThreadIsNoReply) as excinfo:
        append_message(threads_dir=threads_dir, thread_id=th["thread_id"],
                       author_handle="b", message="reply attempt")
    assert th["thread_id"] in str(excinfo.value)
    assert "side thread" in str(excinfo.value).lower()


# v0.2.3 — subject-line tests

def test_first_message_subject_defaults_to_topic(tmp_home, threads_dir):
    """Without explicit subject, the opener message's header subject = topic."""
    th = create_thread(threads_dir=threads_dir, opener_handle="a", scope=["x"],
                       topic="my topic", first_message="body content",
                       author_handle="a")
    text = Path(th["path"]).read_text()
    assert "## my topic · " in text
    assert "· a\n" in text  # author at end


def test_explicit_subject_for_first_message(tmp_home, threads_dir):
    """Passing subject= overrides the topic-default for the opener."""
    th = create_thread(threads_dir=threads_dir, opener_handle="a", scope=["x"],
                       topic="my topic", first_message="body",
                       author_handle="a", subject="kickoff")
    text = Path(th["path"]).read_text()
    assert "## kickoff · " in text


def test_append_subject_derived_from_message_first_line(tmp_home, threads_dir):
    """append_message without subject= uses the first non-empty body line."""
    from lib.thread_store import append_message
    th = create_thread(threads_dir=threads_dir, opener_handle="a", scope=["x"],
                       topic="t", first_message="m1", author_handle="a")
    append_message(threads_dir=threads_dir, thread_id=th["thread_id"],
                   author_handle="bob",
                   message="status update on rollout\n\nlonger details follow")
    text = Path(th["path"]).read_text()
    assert "## status update on rollout · " in text


def test_append_subject_strips_markdown_heading_chars(tmp_home, threads_dir):
    """If user writes `# topic` as first line, derived subject drops the hashes."""
    from lib.thread_store import append_message
    th = create_thread(threads_dir=threads_dir, opener_handle="a", scope=["x"],
                       topic="t", first_message="m1", author_handle="a")
    append_message(threads_dir=threads_dir, thread_id=th["thread_id"],
                   author_handle="bob",
                   message="### Update\n\ndetails")
    text = Path(th["path"]).read_text()
    assert "## Update · " in text


def test_append_explicit_subject(tmp_home, threads_dir):
    """append_message with explicit subject= uses it verbatim."""
    from lib.thread_store import append_message
    th = create_thread(threads_dir=threads_dir, opener_handle="a", scope=["x"],
                       topic="t", first_message="m1", author_handle="a")
    append_message(threads_dir=threads_dir, thread_id=th["thread_id"],
                   author_handle="bob", subject="follow-up",
                   message="this body would otherwise become the subject")
    text = Path(th["path"]).read_text()
    assert "## follow-up · " in text


def test_read_thread_exposes_subject(tmp_home, threads_dir):
    """read_thread returns subject in each message dict."""
    from lib.thread_store import append_message
    th = create_thread(threads_dir=threads_dir, opener_handle="a", scope=["x"],
                       topic="opener subject", first_message="m1", author_handle="a")
    append_message(threads_dir=threads_dir, thread_id=th["thread_id"],
                   author_handle="bob", subject="reply subject", message="m2")
    out = read_thread(threads_dir=threads_dir, thread_id=th["thread_id"])
    subjects = [m["subject"] for m in out["messages"]]
    assert subjects == ["opener subject", "reply subject"]
    assert [m["from"] for m in out["messages"]] == ["a", "bob"]
