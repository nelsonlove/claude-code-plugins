"""Tests for live_watcher (user-edit detection on per-agent live notes).

Watermark is a sha256 of the note body (after frontmatter), so Obsidian Linter
rewriting the `modified:` timestamp doesn't trigger false positives — only
real edits within the message sections do.
"""
from lib import sidecar
from lib.live_note import LIVE_NOTES_SUBPATH, write_live_note
from lib.live_watcher import accept_change, current_body_hash, detect_user_edit


SID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _note_path(vault, handle):
    return vault / LIVE_NOTES_SUBPATH / f"{handle}.md"


def test_current_body_hash_missing_note_returns_none(tmp_path):
    assert current_body_hash(tmp_path, "quill") is None


def test_current_body_hash_returns_hex_digest(tmp_path):
    write_live_note(
        home=str(tmp_path), session_id=SID, handle="quill", scope=[],
        cadence="x", section=None, body="initial",
        vault=tmp_path,
    )
    value = current_body_hash(tmp_path, "quill")
    assert value is not None
    assert len(value) == 64  # sha256 hex digest


def test_detect_no_change_after_self_write(tmp_home, tmp_path):
    """Agent writes, then immediately polls — should be 'no change' because
    write_live_note records the body-hash watermark."""
    write_live_note(
        home=str(tmp_home), session_id=SID, handle="quill", scope=[],
        cadence="x", section=None, body="hello",
        vault=tmp_path,
    )
    result = detect_user_edit(tmp_home, SID, "quill", vault=tmp_path)
    assert result["changed"] is False


def test_modified_field_rewrite_alone_does_not_trigger(tmp_home, tmp_path):
    """Critical: Linter rewriting only the frontmatter modified: field
    (leaving the body untouched) must NOT fire a user-edit event.
    (Issue #1 from PR #26 review.)"""
    import re as _re
    write_live_note(
        home=str(tmp_home), session_id=SID, handle="quill", scope=[],
        cadence="x", section=None, body="hello",
        vault=tmp_path,
    )
    path = _note_path(tmp_path, "quill")
    text = path.read_text()
    # Surgically rewrite ONLY the frontmatter's `modified:` line, mimicking
    # what Obsidian Linter does. Body lines (including `**Last updated**:`)
    # are left alone — Linter doesn't touch them.
    fm_match = _re.match(r"^(---\n)(.*?)(\n---)", text, _re.DOTALL)
    assert fm_match
    new_fm = _re.sub(
        r"^modified:\s*.*$",
        "modified: 2099-01-01T00:00:00+0000",
        fm_match.group(2),
        flags=_re.MULTILINE,
    )
    new_text = fm_match.group(1) + new_fm + fm_match.group(3) + text[fm_match.end():]
    path.write_text(new_text)
    result = detect_user_edit(tmp_home, SID, "quill", vault=tmp_path)
    assert result["changed"] is False  # body unchanged → no event


def test_detect_user_edit_when_body_changes(tmp_home, tmp_path):
    """Real user edit (body content changed) should fire."""
    write_live_note(
        home=str(tmp_home), session_id=SID, handle="quill", scope=[],
        cadence="x", section=None, body="hello",
        vault=tmp_path,
    )
    path = _note_path(tmp_path, "quill")
    text = path.read_text()
    # Simulate a real user edit: rewrite a body section.
    new_text = text.replace("hello", "Nelson's edit here")
    path.write_text(new_text)
    result = detect_user_edit(tmp_home, SID, "quill", vault=tmp_path)
    assert result["changed"] is True


def test_accept_change_silences_subsequent_polls(tmp_home, tmp_path):
    write_live_note(
        home=str(tmp_home), session_id=SID, handle="quill", scope=[],
        cadence="x", section=None, body="hello",
        vault=tmp_path,
    )
    path = _note_path(tmp_path, "quill")
    text = path.read_text()
    path.write_text(text.replace("hello", "user edited"))
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
    notes_dir = tmp_path / LIVE_NOTES_SUBPATH
    notes_dir.mkdir(parents=True, exist_ok=True)
    (notes_dir / "quill.md").write_text(
        "---\nmodified: 2020-01-01T00:00:00\n---\n\nbody\n"
    )
    # No sidecar watermark set yet:
    assert sidecar.get_live_note_seen_body_hash(tmp_home, SID) is None
    result = detect_user_edit(tmp_home, SID, "quill", vault=tmp_path)
    assert result["changed"] is False
