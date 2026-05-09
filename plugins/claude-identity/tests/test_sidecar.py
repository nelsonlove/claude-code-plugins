"""Tests for sessions-meta sidecar CRUD."""
import json
import os
import time
from pathlib import Path

import pytest

from lib.sidecar import (
    SidecarPath, create_if_absent, read_sidecar, add_tag, remove_tag, list_tags
)

SID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def test_create_if_absent_creates_with_schema_and_empty_tags(tmp_home):
    path = SidecarPath(tmp_home, SID).path
    assert not path.exists()
    created = create_if_absent(tmp_home, SID, default_tags=[])
    assert created is True
    data = json.loads(path.read_text())
    assert data["schema"] == 1
    assert data["session_id"] == SID
    assert data["tags"] == []
    assert "added" in data
    assert "modified" in data


def test_create_if_absent_no_op_when_exists(tmp_home):
    create_if_absent(tmp_home, SID, default_tags=[])
    first_mtime = SidecarPath(tmp_home, SID).path.stat().st_mtime
    time.sleep(0.01)
    created = create_if_absent(tmp_home, SID, default_tags=["02.14"])
    assert created is False
    # mtime should be unchanged
    assert SidecarPath(tmp_home, SID).path.stat().st_mtime == first_mtime


def test_create_if_absent_with_default_tags(tmp_home):
    create_if_absent(tmp_home, SID, default_tags=["02.*", "vault-sweeper"])
    data = json.loads(SidecarPath(tmp_home, SID).path.read_text())
    assert data["tags"] == ["02.*", "vault-sweeper"]


def test_add_tag_appends_and_bumps_mtime(tmp_home):
    create_if_absent(tmp_home, SID, default_tags=[])
    path = SidecarPath(tmp_home, SID).path
    mtime_before = path.stat().st_mtime
    time.sleep(0.01)
    add_tag(tmp_home, SID, "02.14")
    data = json.loads(path.read_text())
    assert data["tags"] == ["02.14"]
    assert path.stat().st_mtime > mtime_before


def test_add_tag_idempotent_no_mtime_bump(tmp_home):
    """Adding an existing tag is a no-op; mtime must not change (mtime-pull contract)."""
    create_if_absent(tmp_home, SID, default_tags=["02.14"])
    path = SidecarPath(tmp_home, SID).path
    mtime_before = path.stat().st_mtime
    time.sleep(0.01)
    add_tag(tmp_home, SID, "02.14")
    assert path.stat().st_mtime == mtime_before


def test_remove_tag(tmp_home):
    create_if_absent(tmp_home, SID, default_tags=["02.14", "vault-sweeper"])
    remove_tag(tmp_home, SID, "02.14")
    data = json.loads(SidecarPath(tmp_home, SID).path.read_text())
    assert data["tags"] == ["vault-sweeper"]


def test_remove_tag_missing_no_op(tmp_home):
    """Removing a tag that isn't there shouldn't crash; should be no-op (no mtime bump)."""
    create_if_absent(tmp_home, SID, default_tags=["02.14"])
    path = SidecarPath(tmp_home, SID).path
    mtime_before = path.stat().st_mtime
    time.sleep(0.01)
    remove_tag(tmp_home, SID, "nonexistent")
    assert path.stat().st_mtime == mtime_before


def test_list_tags_missing_sidecar_returns_empty(tmp_home):
    assert list_tags(tmp_home, SID) == []


def test_list_tags_returns_current(tmp_home):
    create_if_absent(tmp_home, SID, default_tags=["a", "b"])
    assert list_tags(tmp_home, SID) == ["a", "b"]


def test_atomic_write_via_replace(tmp_home, monkeypatch):
    """Verify sidecar writes go through os.replace (atomic). Inspect by patching."""
    calls = []

    real_replace = os.replace
    def spy_replace(src, dst):
        calls.append((src, dst))
        return real_replace(src, dst)

    monkeypatch.setattr("lib.sidecar.os.replace", spy_replace)
    create_if_absent(tmp_home, SID, default_tags=["x"])
    assert len(calls) == 1
    assert calls[0][1].endswith(f"{SID}.json")


def test_corrupt_json_treated_as_empty(tmp_home):
    """If sidecar JSON is corrupt, list_tags returns [] (fail-soft per spec)."""
    path = SidecarPath(tmp_home, SID).path
    path.write_text("{ this is not valid json")
    assert list_tags(tmp_home, SID) == []
