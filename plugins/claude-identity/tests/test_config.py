"""Tests for config loader: global TOML + per-project .local.md."""
import pytest

from lib.config import load_config, DEFAULT_SESSIONS_META_DIR


def test_returns_defaults_when_no_files(tmp_home, tmp_path):
    cfg = load_config(home=tmp_home, project_root=tmp_path)
    assert cfg["sessions_meta_dir"] == DEFAULT_SESSIONS_META_DIR
    assert cfg["default_tags"] == []


def test_global_overrides_default(tmp_home, tmp_path):
    g = tmp_home / ".claude" / "claude-identity"
    g.mkdir(parents=True)
    (g / "config.toml").write_text(
        '[paths]\nsessions_meta_dir = "/custom/path"\n'
    )
    cfg = load_config(home=tmp_home, project_root=tmp_path)
    assert cfg["sessions_meta_dir"] == "/custom/path"


def test_project_local_overrides_global(tmp_home, tmp_path):
    p = tmp_path / ".claude"
    p.mkdir()
    (p / "claude-identity.local.md").write_text(
        '---\ndefault_tags: ["02.14", "vault"]\n---\n'
    )
    cfg = load_config(home=tmp_home, project_root=tmp_path)
    assert cfg["default_tags"] == ["02.14", "vault"]


def test_malformed_global_falls_back_to_defaults(tmp_home, tmp_path):
    g = tmp_home / ".claude" / "claude-identity"
    g.mkdir(parents=True)
    (g / "config.toml").write_text("this is not toml")
    cfg = load_config(home=tmp_home, project_root=tmp_path)
    assert cfg["sessions_meta_dir"] == DEFAULT_SESSIONS_META_DIR
