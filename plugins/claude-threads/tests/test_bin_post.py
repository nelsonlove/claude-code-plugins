"""Test the standalone bin/post CLI for cross-session message posting."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

BIN = Path(__file__).parent.parent / "bin" / "post"


def run_cli(env, *args, input_text=None):
    return subprocess.run(
        [sys.executable, str(BIN), *args],
        capture_output=True, text=True, env=env, input=input_text,
    )


@pytest.fixture
def cli_env(tmp_home):
    """Env with HOME set so the script writes to the test's tmp threads dir."""
    e = os.environ.copy()
    e["HOME"] = str(tmp_home)
    e["MY_HANDLE"] = "test-author"
    return e


def test_new_thread_returns_id_on_stdout(cli_env, tmp_home):
    r = run_cli(cli_env, "--new", "--scope", "jd/03.14",
                "--topic", "smoke", "first message")
    assert r.returncode == 0
    tid = r.stdout.strip()
    assert len(tid) == 8
    # File landed in default ~/.claude/threads
    threads = list((tmp_home / ".claude" / "threads").glob("*.md"))
    assert len(threads) == 1
    text = threads[0].read_text()
    assert tid in text
    assert "first message" in text
    assert 'thread-scope: ["jd/03.14"]' in text


def test_to_shortcut_scopes_thread_to_handle(cli_env, tmp_home):
    r = run_cli(cli_env, "--to", "fern", "--topic", "ping", "hey")
    assert r.returncode == 0
    text = next((tmp_home / ".claude" / "threads").glob("*ping*.md")).read_text()
    assert 'thread-scope: ["fern"]' in text


def test_thread_reply_with_4char_prefix(cli_env, tmp_home):
    r1 = run_cli(cli_env, "--new", "--scope", "demo", "--topic", "convo", "first")
    tid = r1.stdout.strip()
    r2 = run_cli(cli_env, "--thread", tid[:4], "second from peer")
    assert r2.returncode == 0
    assert r2.stdout.strip() == tid
    text = next((tmp_home / ".claude" / "threads").glob("*convo*.md")).read_text()
    assert text.count("## ") == 2  # two messages
    assert "second from peer" in text


def test_thread_reply_unknown_id_errors(cli_env):
    r = run_cli(cli_env, "--thread", "deadbeef", "msg")
    assert r.returncode != 0
    assert "no thread matches" in r.stderr.lower()


def test_no_reply_flag_refuses_replies(cli_env, tmp_home):
    r1 = run_cli(cli_env, "--new", "--scope", "announce", "--no-reply",
                 "--topic", "alert", "production deployed")
    assert r1.returncode == 0
    tid = r1.stdout.strip()
    text = next((tmp_home / ".claude" / "threads").glob("*alert*.md")).read_text()
    assert "thread-no-reply: true" in text
    # Reply attempt should fail with informative error
    r2 = run_cli(cli_env, "--thread", tid, "any details?")
    assert r2.returncode == 3
    assert "no-reply" in r2.stderr.lower()
    assert "side thread" in r2.stderr.lower()


def test_explicit_author_overrides_env(cli_env, tmp_home):
    r = run_cli(cli_env, "--as", "external-cron", "--new", "--scope", "ops",
                "--topic", "cron", "from cron")
    assert r.returncode == 0
    text = next((tmp_home / ".claude" / "threads").glob("*cron*.md")).read_text()
    assert "thread-opener: external-cron" in text
    assert "## external-cron" in text


def test_handle_resolution_falls_through_to_external(tmp_home):
    """No MY_HANDLE env, no parent CC session in registry → 'external'."""
    e = os.environ.copy()
    e["HOME"] = str(tmp_home)
    # Explicitly clear MY_HANDLE if inherited
    e.pop("MY_HANDLE", None)
    r = run_cli(e, "--new", "--scope", "ops", "--topic", "no-handle", "msg")
    assert r.returncode == 0
    text = next((tmp_home / ".claude" / "threads").glob("*no-handle*.md")).read_text()
    assert "thread-opener: external" in text


def test_new_without_scope_or_topic_errors(cli_env):
    r = run_cli(cli_env, "--new", "msg")
    assert r.returncode != 0
    r2 = run_cli(cli_env, "--new", "--scope", "x", "msg")
    assert r2.returncode != 0  # missing --topic


def test_mode_is_required(cli_env):
    r = run_cli(cli_env, "msg")
    assert r.returncode != 0  # no mode flag
