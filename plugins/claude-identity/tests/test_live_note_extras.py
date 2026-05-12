"""Additional live_note tests: config-driven dir + template, fail-fast."""
from pathlib import Path

import pytest

from lib.live_note import (
    DEFAULT_TEMPLATE,
    load_template,
    resolve_live_notes_dir,
    resolve_template_path,
    write_live_note,
)


SID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


# ---------------------------------------------------------------------------
# Config-driven live_notes_dir + template resolution
# ---------------------------------------------------------------------------

def test_resolve_live_notes_dir_reads_config(tmp_home):
    """Global config TOML `[paths] live_notes_dir = "..."` should be honored."""
    cfg_dir = Path(tmp_home) / ".claude" / "claude-identity"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "config.toml").write_text(
        '[paths]\nlive_notes_dir = "/custom/dir"\n'
    )
    result = resolve_live_notes_dir(home=str(tmp_home), project_root=str(tmp_home))
    assert str(result) == "/custom/dir"


def test_resolve_template_path_reads_config(tmp_home):
    """`[paths] live_note_template` overrides the default."""
    cfg_dir = Path(tmp_home) / ".claude" / "claude-identity"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "config.toml").write_text(
        '[paths]\nlive_note_template = "/some/template.md"\n'
    )
    result = resolve_template_path(home=str(tmp_home), project_root=str(tmp_home))
    assert str(result) == "/some/template.md"


def test_load_template_reads_file_when_present(tmp_home, tmp_path):
    """If the configured template file exists, load_template reads it."""
    cfg_dir = Path(tmp_home) / ".claude" / "claude-identity"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    template_path = tmp_path / "template.md"
    template_path.write_text("CUSTOM TEMPLATE FOR {{handle}}")
    (cfg_dir / "config.toml").write_text(
        f'[paths]\nlive_note_template = "{template_path}"\n'
    )
    result = load_template(home=str(tmp_home), project_root=str(tmp_home))
    assert result == "CUSTOM TEMPLATE FOR {{handle}}"


def test_load_template_falls_back_to_default_when_missing(tmp_home):
    """If the configured template file doesn't exist, fall back to DEFAULT_TEMPLATE."""
    cfg_dir = Path(tmp_home) / ".claude" / "claude-identity"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "config.toml").write_text(
        '[paths]\nlive_note_template = "/nonexistent/template.md"\n'
    )
    result = load_template(home=str(tmp_home), project_root=str(tmp_home))
    assert result == DEFAULT_TEMPLATE
