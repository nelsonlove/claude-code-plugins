"""Test layered config: defaults < global TOML < per-project local.md."""
from lib.config import load_config


def test_defaults(tmp_home, tmp_path):
    cfg = load_config(home=tmp_home, project_root=tmp_path)
    assert cfg["threads_dir"].endswith("/.claude/threads")
    assert cfg["frontmatter_prefix"] == "thread-"
    assert cfg["auto_tag_cwd"] is False


def test_global_overrides(tmp_home, tmp_path):
    g = tmp_home / ".claude" / "claude-threads"
    g.mkdir(parents=True)
    (g / "config.toml").write_text(
        '[paths]\nthreads_dir = "/custom"\n'
        '[frontmatter]\nprefix = ""\n'
        '[scope]\nauto_tag_cwd = true\n'
    )
    cfg = load_config(home=tmp_home, project_root=tmp_path)
    assert cfg["threads_dir"] == "/custom"
    assert cfg["frontmatter_prefix"] == ""
    assert cfg["auto_tag_cwd"] is True


def test_project_local_overrides(tmp_home, tmp_path):
    p = tmp_path / ".claude"
    p.mkdir()
    (p / "claude-threads.local.md").write_text(
        '---\nthreads_dir: "/Users/nelson/vault/02.14"\n'
        'auto_tag_cwd: true\n---\n'
    )
    cfg = load_config(home=tmp_home, project_root=tmp_path)
    assert cfg["threads_dir"] == "/Users/nelson/vault/02.14"
    assert cfg["auto_tag_cwd"] is True
