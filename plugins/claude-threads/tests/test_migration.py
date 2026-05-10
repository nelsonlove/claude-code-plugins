"""Test the migration script for pre-existing 02.14 threads."""
import shutil
from pathlib import Path

import pytest

from migrations.migrate_02_14 import migrate_thread_file, is_already_migrated

FIXTURE = Path(__file__).parent / "fixtures" / "existing_02_14_thread.md"


def test_migrate_renames_status_and_opener(tmp_path):
    target = tmp_path / "thread.md"
    shutil.copy(FIXTURE, target)
    migrate_thread_file(target, scope=["02.14"])

    text = target.read_text()
    # Original keys are renamed
    assert "thread-status: open" in text
    assert "thread-opener: 6afef2c8" in text
    # Original `status:` line should be gone
    fm = text.split("---")[1]
    assert "\nstatus: " not in fm
    assert "\nopener: " not in fm
    # participants dropped
    assert "participants:" not in fm
    # New thread-id added
    assert "thread-id: " in text
    # Scope added (always quoted on write per v0.2.1)
    assert 'thread-scope: ["02.14"]' in text
    # tags untouched (also re-emitted with quotes since they're a list value)
    assert 'tags: ["jd/agent", "jd/inter-session"]' in text
    # Body preserved
    assert "Existing message body..." in text


def test_migrate_idempotent(tmp_path):
    target = tmp_path / "thread.md"
    shutil.copy(FIXTURE, target)
    migrate_thread_file(target, scope=["02.14"])
    first_text = target.read_text()
    # Running again should be no-op
    migrate_thread_file(target, scope=["02.14"])
    assert target.read_text() == first_text


def test_is_already_migrated_detects_thread_id(tmp_path):
    target = tmp_path / "thread.md"
    target.write_text("---\nthread-id: abc12345\n---\n\nbody\n")
    assert is_already_migrated(target) is True


def test_is_already_migrated_false_for_old(tmp_path):
    target = tmp_path / "thread.md"
    shutil.copy(FIXTURE, target)
    assert is_already_migrated(target) is False
