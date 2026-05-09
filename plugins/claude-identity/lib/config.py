"""Config loader. Layered:
  1. Per-project: <project_root>/.claude/claude-identity.local.md (YAML frontmatter)
  2. Global: $HOME/.claude/claude-identity/config.toml
  3. Baked defaults

Uses tomllib (stdlib in Python 3.11+) for TOML, regex for YAML frontmatter (since
we want zero deps — the only YAML we read is `default_tags: ["a", "b"]` which is
trivially extractable).
"""
import re
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


DEFAULT_SESSIONS_META_DIR = "~/.claude/sessions-meta"


def _global_config_path(home):
    return Path(home) / ".claude" / "claude-identity" / "config.toml"


def _project_local_path(project_root):
    return Path(project_root) / ".claude" / "claude-identity.local.md"


def _read_global(home):
    p = _global_config_path(home)
    if not p.exists():
        return {}
    try:
        with p.open("rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError):
        return {}
    out = {}
    paths = data.get("paths", {})
    if "sessions_meta_dir" in paths:
        out["sessions_meta_dir"] = paths["sessions_meta_dir"]
    return out


def _read_project_local(project_root):
    p = _project_local_path(project_root)
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
    tag_match = re.search(r"^default_tags:\s*\[(.*?)\]", fm, re.MULTILINE)
    if tag_match:
        out["default_tags"] = [
            t.strip().strip('"').strip("'")
            for t in tag_match.group(1).split(",")
            if t.strip()
        ]
    return out


def load_config(home, project_root):
    """Layered config: defaults < global < project-local."""
    cfg = {
        "sessions_meta_dir": DEFAULT_SESSIONS_META_DIR,
        "default_tags": [],
    }
    cfg.update(_read_global(home))
    cfg.update(_read_project_local(project_root))
    return cfg
