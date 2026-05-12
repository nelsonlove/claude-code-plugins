"""Tests for live_note (per-agent live notes)."""
from pathlib import Path

import pytest

from lib.live_note import (
    DEFAULT_TEMPLATE,
    render_template,
    replace_section,
    resolve_note_path,
    resolve_live_notes_dir,
    session_id_short,
    update_frontmatter_fields,
    write_live_note,
)


SID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def test_resolve_live_notes_dir_default(monkeypatch, tmp_home):
    """No config → default `~/.claude/agent-live-notes/` expanded."""
    monkeypatch.delenv("OBSIDIAN_VAULT", raising=False)
    result = resolve_live_notes_dir(home=str(tmp_home), project_root=str(tmp_home))
    assert str(result).endswith("/.claude/agent-live-notes")


def test_resolve_note_path(tmp_path):
    """Per-agent note lands at <live_notes_dir>/<handle>.md — no subpath."""
    assert resolve_note_path(tmp_path, "quill") == tmp_path / "quill.md"


def test_session_id_short():
    assert session_id_short("aaaaaaaa-bbbb-cccc") == "aaaaaaaa"
    assert session_id_short("") == ""


def test_render_template_substitutes():
    t = "hi {{handle}}, session {{session-id-short}}"
    out = render_template(t, {"handle": "quill", "session-id-short": "abcd1234"})
    assert out == "hi quill, session abcd1234"


def test_replace_section_replaces_body_only():
    text = "## A\n\nold A\n\n## B\n\nold B\n"
    out = replace_section(text, "A", "new A body")
    assert "new A body" in out
    assert "old B" in out  # B untouched
    assert "old A" not in out


def test_replace_section_missing_raises():
    with pytest.raises(KeyError):
        replace_section("## A\n\nbody\n", "B", "x")


def test_update_frontmatter_fields_replaces_existing():
    text = '---\ntitle: foo\nmodified: 2020-01-01T00:00:00\n---\n\nbody\n'
    out = update_frontmatter_fields(text, {"modified": "2026-05-11T12:00:00"})
    assert "modified: 2026-05-11T12:00:00" in out
    assert "modified: 2020-01-01T00:00:00" not in out


def test_update_frontmatter_fields_adds_missing():
    text = '---\ntitle: foo\n---\n\nbody\n'
    out = update_frontmatter_fields(text, {"cadence": '"every 5 min"'})
    assert 'cadence: "every 5 min"' in out


def test_write_live_note_creates_from_template(tmp_path):
    result = write_live_note(
        home=str(tmp_path),
        session_id=SID,
        handle="quill",
        scope=["jd/03.14", "announce"],
        cadence="as work progresses",
        section="Current task",
        body="testing the live note",
        live_notes_dir=tmp_path,
    )
    assert result["created"] is True
    path = Path(result["path"])
    assert path.exists()
    assert path == tmp_path / "quill.md"
    text = path.read_text()
    assert "handle: quill" in text
    assert f"session-id: {SID}" in text
    assert "scope: [jd/03.14, announce]" in text
    assert "testing the live note" in text
    # The default "(what the agent is doing right now)" body should be gone:
    assert "(what the agent is doing right now)" not in text
    # jd-id should NOT be in template (config-driven dir, not vault-specific)
    assert "jd-id:" not in text


def test_write_live_note_updates_existing(tmp_path):
    write_live_note(
        home=str(tmp_path), session_id=SID, handle="quill", scope=[],
        cadence="as work progresses",
        section="Current task", body="first content",
        live_notes_dir=tmp_path,
    )
    result = write_live_note(
        home=str(tmp_path), session_id=SID, handle="quill", scope=["jd/04*"],
        cadence="every 5 min",
        section="Current task", body="updated content",
        live_notes_dir=tmp_path,
    )
    assert result["created"] is False
    text = Path(result["path"]).read_text()
    assert "updated content" in text
    assert "first content" not in text
    # Frontmatter updated:
    assert "scope: [jd/04*]" in text
    assert 'cadence: "every 5 min"' in text


def test_write_live_note_defaults_section_to_live_notes(tmp_path):
    """When --section is omitted, body lands in 'Live notes' section."""
    write_live_note(
        home=str(tmp_path), session_id=SID, handle="quill", scope=[],
        cadence="as work progresses",
        section=None, body="freeform jot",
        live_notes_dir=tmp_path,
    )
    text = (tmp_path / "quill.md").read_text()
    assert "freeform jot" in text
    notes_idx = text.index("## Live notes")
    jot_idx = text.index("freeform jot")
    assert jot_idx > notes_idx


def test_write_live_note_unknown_section_appends(tmp_path):
    """An unknown --section name should append a new section, not error."""
    write_live_note(
        home=str(tmp_path), session_id=SID, handle="quill", scope=[],
        cadence="as work progresses",
        section="Custom Section", body="custom body",
        live_notes_dir=tmp_path,
    )
    text = (tmp_path / "quill.md").read_text()
    assert "## Custom Section" in text
    assert "custom body" in text


def test_write_live_note_after_rename_new_file_old_stays(tmp_path):
    """Per Nelson's call: handle rename doesn't move the old file. New write
    creates `<new-handle>.md` fresh; `<old-handle>.md` stays in place."""
    write_live_note(
        home=str(tmp_path), session_id=SID, handle="oldname", scope=[],
        cadence="x", section=None, body="first",
        live_notes_dir=tmp_path,
    )
    write_live_note(
        home=str(tmp_path), session_id=SID, handle="newname", scope=[],
        cadence="x", section=None, body="second",
        live_notes_dir=tmp_path,
    )
    assert (tmp_path / "oldname.md").exists(), "old file should still exist"
    assert (tmp_path / "newname.md").exists(), "new file should be created"
    new_text = (tmp_path / "newname.md").read_text()
    assert "second" in new_text
    assert "handle: newname" in new_text


def test_default_template_has_required_sections():
    """All canonical sections from issue #24 must be present."""
    for section in ["Current task", "Completed in this session",
                    "Pending / awaiting review", "Open questions", "Live notes"]:
        assert f"## {section}" in DEFAULT_TEMPLATE


def test_default_template_no_jd_id():
    """Per Nelson's call: live notes shouldn't carry jd-id frontmatter
    (their location is configurable; jd-id only makes sense for vault users)."""
    assert "jd-id:" not in DEFAULT_TEMPLATE
