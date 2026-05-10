"""Test the shared poll-and-emit helper used by all 3 hooks."""
import json
import time

import pytest

from lib.poll import poll_for_session
from lib.thread_store import create_thread


def test_poll_returns_empty_when_no_threads(tmp_home, threads_dir, write_sidecar):
    sid = "11111111-1111-1111-1111-111111111111"
    write_sidecar(sid, tags=["02.14"])
    result = poll_for_session(home=tmp_home, session_id=sid,
                              threads_dir=str(threads_dir),
                              last_poll_epoch=0)
    assert result["new_matches"] == []


def test_poll_returns_match_when_thread_in_scope(tmp_home, threads_dir, write_sidecar):
    sid = "22222222-2222-2222-2222-222222222222"
    write_sidecar(sid, tags=["02.*"])
    th = create_thread(threads_dir=threads_dir, opener_handle="alice", scope=["02.14"],
                       topic="t", first_message="m", author_handle="alice", author_model="x")
    result = poll_for_session(home=tmp_home, session_id=sid,
                              threads_dir=str(threads_dir),
                              last_poll_epoch=0)
    assert len(result["new_matches"]) == 1
    assert result["new_matches"][0]["thread_id"] == th["thread_id"]


def test_poll_skips_threads_older_than_last_poll(tmp_home, threads_dir, write_sidecar):
    sid = "33333333-3333-3333-3333-333333333333"
    write_sidecar(sid, tags=["02.*"])
    create_thread(threads_dir=threads_dir, opener_handle="a", scope=["02.14"],
                  topic="old", first_message="m", author_handle="a", author_model="x")
    time.sleep(0.05)
    cutoff = time.time()
    result = poll_for_session(home=tmp_home, session_id=sid,
                              threads_dir=str(threads_dir),
                              last_poll_epoch=cutoff)
    assert result["new_matches"] == []


def test_poll_uses_implicit_handle(tmp_home, threads_dir, write_sidecar, write_registry_entry):
    sid = "44444444-4444-4444-4444-444444444444"
    write_sidecar(sid, tags=[])
    write_registry_entry(pid=400, session_id=sid, name="fern")
    create_thread(threads_dir=threads_dir, opener_handle="a", scope=["fern"],
                  topic="direct", first_message="m", author_handle="a", author_model="x")
    result = poll_for_session(home=tmp_home, session_id=sid,
                              threads_dir=str(threads_dir),
                              last_poll_epoch=0)
    assert len(result["new_matches"]) == 1
