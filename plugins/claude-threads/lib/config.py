"""Layered config: defaults < $HOME/.claude/claude-threads/config.toml <
$PROJECT/.claude/claude-threads.local.md"""
import os
import re
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


DEFAULTS = {
    "threads_dir": "~/.claude/threads",
    "frontmatter_prefix": "thread-",
    "auto_tag_cwd": False,
}


def _expand(p):
    return os.path.expanduser(p) if isinstance(p, str) else p


def _read_global(home):
    p = Path(home) / ".claude" / "claude-threads" / "config.toml"
    if not p.exists():
        return {}
    try:
        with p.open("rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError):
        return {}
    out = {}
    if "threads_dir" in data.get("paths", {}):
        out["threads_dir"] = data["paths"]["threads_dir"]
    if "prefix" in data.get("frontmatter", {}):
        out["frontmatter_prefix"] = data["frontmatter"]["prefix"]
    if "auto_tag_cwd" in data.get("scope", {}):
        out["auto_tag_cwd"] = bool(data["scope"]["auto_tag_cwd"])
    return out


def _read_project_local(project_root):
    p = Path(project_root) / ".claude" / "claude-threads.local.md"
    if not p.exists():
        return {}
    try:
        text = p.read_text()
    except OSError:
        return {}
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    fm = m.group(1)
    out = {}
    if mm := re.search(r"^threads_dir:\s*(.+)$", fm, re.MULTILINE):
        out["threads_dir"] = mm.group(1).strip().strip('"').strip("'")
    if mm := re.search(r"^auto_tag_cwd:\s*(true|false)\s*$", fm, re.MULTILINE):
        out["auto_tag_cwd"] = mm.group(1) == "true"
    if mm := re.search(r"^frontmatter_prefix:\s*(.*)$", fm, re.MULTILINE):
        out["frontmatter_prefix"] = mm.group(1).strip().strip('"').strip("'")
    return out


def load_config(*, home, project_root):
    cfg = dict(DEFAULTS)
    cfg.update(_read_global(home))
    cfg.update(_read_project_local(project_root))
    cfg["threads_dir"] = _expand(cfg["threads_dir"])
    return cfg
