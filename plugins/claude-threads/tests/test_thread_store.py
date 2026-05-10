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
        author_model="claude-opus-4-7",
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
                       author_handle="alice", author_model="x")
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
                       first_message="m", author_handle="a", author_model="x")
    assert Path(th["path"]).name == "2026-05-09 reconcile inbox triage.md"


def test_filename_collision_appends_numeric(tmp_home, threads_dir, monkeypatch):
    import lib.thread_store as ts
    monkeypatch.setattr(ts, "_today_iso_date", lambda: "2026-05-09")
    create_thread(threads_dir=threads_dir, opener_handle="a", scope=["x"],
                  topic="dup", first_message="m1", author_handle="a", author_model="x")
    th2 = create_thread(threads_dir=threads_dir, opener_handle="a", scope=["x"],
                       topic="dup", first_message="m2", author_handle="a", author_model="x")
    assert Path(th2["path"]).name == "2026-05-09 dup (2).md"


def test_append_message_updates_modified(tmp_home, threads_dir):
    th = create_thread(threads_dir=threads_dir, opener_handle="a", scope=["x"],
                      topic="t", first_message="m1", author_handle="a", author_model="x")
    import time; time.sleep(0.01)
    append_message(threads_dir=threads_dir, thread_id=th["thread_id"],
                   author_handle="bob", author_model="claude-opus-4-7",
                   message="reply body")
    text = Path(th["path"]).read_text()
    assert "## bob ·" in text
    assert "reply body" in text
    # modified should be newer than created
    fm_section = text.split("---")[1]
    import re
    created = re.search(r"^created:\s*(.*)$", fm_section, re.MULTILINE).group(1).strip()
    modified = re.search(r"^modified:\s*(.*)$", fm_section, re.MULTILINE).group(1).strip()
    assert modified > created


def test_close_thread_sets_status_resolved(tmp_home, threads_dir):
    th = create_thread(threads_dir=threads_dir, opener_handle="a", scope=["x"],
                      topic="t", first_message="m", author_handle="a", author_model="x")
    close_thread(threads_dir=threads_dir, thread_id=th["thread_id"])
    text = Path(th["path"]).read_text()
    assert "thread-status: resolved" in text
    # Original `open` line should be gone
    assert "thread-status: open" not in text


def test_list_threads_returns_all(tmp_home, threads_dir):
    create_thread(threads_dir=threads_dir, opener_handle="a", scope=["02.14"],
                  topic="t1", first_message="m", author_handle="a", author_model="x")
    create_thread(threads_dir=threads_dir, opener_handle="b", scope=["74.01"],
                  topic="t2", first_message="m", author_handle="b", author_model="x")
    threads = list_threads(threads_dir=threads_dir)
    assert len(threads) == 2


def test_read_thread_returns_structured(tmp_home, threads_dir):
    th = create_thread(threads_dir=threads_dir, opener_handle="alice", scope=["02.14"],
                      topic="t", first_message="hello", author_handle="alice", author_model="x")
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
                       author_handle="a", author_model="x", no_reply=True)
    text = Path(th["path"]).read_text()
    assert "thread-no-reply: true" in text


def test_create_thread_default_omits_no_reply_flag(tmp_home, threads_dir):
    """no_reply defaults to False; field is omitted entirely."""
    from pathlib import Path
    th = create_thread(threads_dir=threads_dir, opener_handle="a", scope=["02.14"],
                       topic="t", first_message="m",
                       author_handle="a", author_model="x")
    text = Path(th["path"]).read_text()
    assert "thread-no-reply" not in text


def test_append_message_to_no_reply_thread_raises(tmp_home, threads_dir):
    """append_message refuses no-reply threads with a clear error directing the
    caller to spawn a side thread."""
    from lib.thread_store import append_message, ThreadIsNoReply
    th = create_thread(threads_dir=threads_dir, opener_handle="a", scope=["announce"],
                       topic="t", first_message="m",
                       author_handle="a", author_model="x", no_reply=True)
    with pytest.raises(ThreadIsNoReply) as excinfo:
        append_message(threads_dir=threads_dir, thread_id=th["thread_id"],
                       author_handle="b", author_model="x", message="reply attempt")
    assert th["thread_id"] in str(excinfo.value)
    assert "side thread" in str(excinfo.value).lower()
