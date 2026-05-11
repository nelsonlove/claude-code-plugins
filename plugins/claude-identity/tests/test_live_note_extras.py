"""Additional live_note tests: rename-follow, config-driven template, fail-fast."""
import json
import os
from pathlib import Path

import pytest

from lib import sidecar
from lib.live_note import (
    DEFAULT_TEMPLATE,
    LIVE_NOTES_SUBPATH,
    load_template,
    resolve_template_path,
    resolve_vault_path,
    write_live_note,
)


SID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _note_path(vault, handle):
    return vault / LIVE_NOTES_SUBPATH / f"{handle}.md"


# ---------------------------------------------------------------------------
# Config-driven vault + template resolution
# ---------------------------------------------------------------------------

def test_resolve_vault_path_reads_config(tmp_home, monkeypatch):
    """Global config TOML `[paths] vault = "..."` should be honored."""
    monkeypatch.delenv("OBSIDIAN_VAULT", raising=False)
    cfg_dir = Path(tmp_home) / ".claude" / "claude-identity"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "config.toml").write_text(
        '[paths]\nvault = "/custom/vault/path"\n'
    )
    result = resolve_vault_path(home=str(tmp_home), project_root=str(tmp_home))
    assert str(result) == "/custom/vault/path"


def test_resolve_vault_path_env_overrides_config(tmp_home, monkeypatch):
    """OBSIDIAN_VAULT env wins over config."""
    monkeypatch.setenv("OBSIDIAN_VAULT", "/env/wins")
    cfg_dir = Path(tmp_home) / ".claude" / "claude-identity"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "config.toml").write_text(
        '[paths]\nvault = "/config/loses"\n'
    )
    result = resolve_vault_path(home=str(tmp_home), project_root=str(tmp_home))
    assert str(result) == "/env/wins"


def test_load_template_reads_file_when_present(tmp_home, monkeypatch, tmp_path):
    """If the template file exists in the vault, load_template reads it."""
    monkeypatch.delenv("OBSIDIAN_VAULT", raising=False)
    cfg_dir = Path(tmp_home) / ".claude" / "claude-identity"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "config.toml").write_text(
        f'[paths]\nvault = "{tmp_path}"\nlive_note_template = "templates/agent.md"\n'
    )
    template_path = tmp_path / "templates" / "agent.md"
    template_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_text("CUSTOM TEMPLATE FOR {{handle}}")
    result = load_template(home=str(tmp_home), project_root=str(tmp_home))
    assert result == "CUSTOM TEMPLATE FOR {{handle}}"


def test_load_template_falls_back_to_default_when_missing(tmp_home, monkeypatch, tmp_path):
    """If the configured template file doesn't exist, fall back to DEFAULT_TEMPLATE."""
    monkeypatch.delenv("OBSIDIAN_VAULT", raising=False)
    cfg_dir = Path(tmp_home) / ".claude" / "claude-identity"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "config.toml").write_text(
        f'[paths]\nvault = "{tmp_path}"\nlive_note_template = "missing/template.md"\n'
    )
    result = load_template(home=str(tmp_home), project_root=str(tmp_home))
    assert result == DEFAULT_TEMPLATE


# ---------------------------------------------------------------------------
# Handle-rename follow
# ---------------------------------------------------------------------------

def test_rename_follow_moves_old_file(tmp_home, tmp_path):
    """Mid-session /claude-identity:rename should make subsequent
    update_live_note rename the file from <old>.md to <new>.md."""
    # First write as 'oldname'
    write_live_note(
        home=str(tmp_home), session_id=SID, handle="oldname", scope=[],
        cadence="x", section=None, body="first body",
        vault=tmp_path,
    )
    old_path = _note_path(tmp_path, "oldname")
    assert old_path.exists()

    # Agent renames to 'newname', sidecar handle update happens via set_handle.
    # Then writes again — should rename the file.
    result = write_live_note(
        home=str(tmp_home), session_id=SID, handle="newname", scope=[],
        cadence="x", section=None, body="second body",
        vault=tmp_path,
    )
    new_path = _note_path(tmp_path, "newname")
    assert new_path.exists()
    assert not old_path.exists(), "old file should have been moved, not copied"
    assert result["renamed_from"] == "oldname"
    # Frontmatter handle: field updated to new value
    text = new_path.read_text()
    assert "handle: newname" in text
    # And the second body landed in the file:
    assert "second body" in text


def test_no_rename_when_handle_unchanged(tmp_home, tmp_path):
    write_live_note(
        home=str(tmp_home), session_id=SID, handle="stable", scope=[],
        cadence="x", section=None, body="b1",
        vault=tmp_path,
    )
    result = write_live_note(
        home=str(tmp_home), session_id=SID, handle="stable", scope=[],
        cadence="x", section=None, body="b2",
        vault=tmp_path,
    )
    assert result["renamed_from"] is None


def test_rename_skips_if_target_exists(tmp_home, tmp_path):
    """If both <old>.md and <new>.md exist (collision), don't clobber the new
    one. Keeps current handle's file as the canonical."""
    # Both files exist independently
    write_live_note(
        home=str(tmp_home), session_id=SID, handle="oldname", scope=[],
        cadence="x", section=None, body="from old session",
        vault=tmp_path,
    )
    # Manually create newname.md (simulating a peer session previously wrote)
    new_path = _note_path(tmp_path, "newname")
    new_path.parent.mkdir(parents=True, exist_ok=True)
    new_path.write_text("---\nhandle: newname\n---\n\n## Live notes\n\npeer content\n")

    # Now this agent renames from oldname → newname and writes
    result = write_live_note(
        home=str(tmp_home), session_id=SID, handle="newname", scope=[],
        cadence="x", section=None, body="our content",
        vault=tmp_path,
    )
    # Rename should NOT happen (target exists); we update the existing file instead
    assert result["renamed_from"] is None
    assert _note_path(tmp_path, "oldname").exists(), "old file untouched when target exists"
