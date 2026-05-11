"""Tests for live_watcher (user-edit detection on per-agent live notes)."""
from pathlib import Path

import pytest

from lib import sidecar
from lib.live_note import LIVE_NOTES_SUBPATH, write_live_note
from lib.live_watcher import accept_change, current_modified, detect_user_edit


SID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _note_path(vault, handle):
    return vault / LIVE_NOTES_SUBPATH / f"{handle}.md"


def test_current_modified_missing_note_returns_none(tmp_path):
    assert current_modified(tmp_path, "quill") is None


def test_current_modified_returns_field_value(tmp_path):
    write_live_note(
        home=str(tmp_path), session_id=SID, handle="quill", scope=[],
        cadence="x", section=None, body="initial",
        vault=tmp_path,
    )
    value = current_modified(tmp_path, "quill")
    assert value is not None
    assert "T" in value  # ISO timestamp shape


def test_detect_no_change_after_self_write(tmp_home, tmp_path):
    """Agent writes, then immediately polls — should be 'no change' because
    write_live_note records the watermark."""
    write_live_note(
        home=str(tmp_home), session_id=SID, handle="quill", scope=[],
        cadence="x", section=None, body="hello",
        vault=tmp_path,
    )
    result = detect_user_edit(tmp_home, SID, "quill", vault=tmp_path)
    assert result["changed"] is False


def test_detect_user_edit_when_modified_field_changes(tmp_home, tmp_path):
    """Simulate a user edit by manually rewriting the file's modified field."""
    write_live_note(
        home=str(tmp_home), session_id=SID, handle="quill", scope=[],
        cadence="x", section=None, body="hello",
        vault=tmp_path,
    )
    path = _note_path(tmp_path, "quill")
    text = path.read_text()
    # Replace the modified field with a different value (simulating user edit)
    new_text = text.replace(
        text.split("modified: ")[1].split("\n")[0],
        "2099-01-01T00:00:00+0000"
    )
    path.write_text(new_text)
    result = detect_user_edit(tmp_home, SID, "quill", vault=tmp_path)
    assert result["changed"] is True
    assert result["current"] == "2099-01-01T00:00:00+0000"


def test_accept_change_silences_subsequent_polls(tmp_home, tmp_path):
    write_live_note(
        home=str(tmp_home), session_id=SID, handle="quill", scope=[],
        cadence="x", section=None, body="hello",
        vault=tmp_path,
    )
    path = _note_path(tmp_path, "quill")
    text = path.read_text()
    new_text = text.replace(
        text.split("modified: ")[1].split("\n")[0],
        "2099-01-01T00:00:00+0000"
    )
    path.write_text(new_text)
    # First poll: change detected
    result = detect_user_edit(tmp_home, SID, "quill", vault=tmp_path)
    assert result["changed"] is True
    accept_change(tmp_home, SID, result["current"])
    # Second poll: silent (we accepted the change)
    result2 = detect_user_edit(tmp_home, SID, "quill", vault=tmp_path)
    assert result2["changed"] is False


def test_detect_no_watermark_treats_current_as_baseline(tmp_home, tmp_path):
    """If the agent never wrote through update_live_note (no watermark), the
    watcher uses the current value as baseline rather than emitting."""
    # Create a note manually without going through write_live_note:
    notes_dir = tmp_path / LIVE_NOTES_SUBPATH
    notes_dir.mkdir(parents=True, exist_ok=True)
    (notes_dir / "quill.md").write_text(
        "---\nmodified: 2020-01-01T00:00:00\n---\n\nbody\n"
    )
    # No sidecar watermark set yet:
    assert sidecar.get_live_note_seen_modified(tmp_home, SID) is None
    result = detect_user_edit(tmp_home, SID, "quill", vault=tmp_path)
    assert result["changed"] is False
