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
# Live-notes directory: where per-agent `<handle>.md` files land. Default is
# under `~/.claude/` so the plugin works out-of-the-box for anyone; users
# typically override to an Obsidian-vault JD slot via the config TOML
# `[paths] live_notes_dir = "..."`.
DEFAULT_LIVE_NOTES_DIR = "~/.claude/agent-live-notes"
# Template file path. When the file is absent on disk, load_template() falls
# back to the baked DEFAULT_TEMPLATE string in lib.live_note — so an empty
# config still produces valid notes.
DEFAULT_LIVE_NOTE_TEMPLATE = "~/.claude/agent-live-notes/template.md"


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
    if "live_notes_dir" in paths:
        out["live_notes_dir"] = paths["live_notes_dir"]
    if "live_note_template" in paths:
        out["live_note_template"] = paths["live_note_template"]
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
        "live_notes_dir": DEFAULT_LIVE_NOTES_DIR,
        "live_note_template": DEFAULT_LIVE_NOTE_TEMPLATE,
        "default_tags": [],
    }
    cfg.update(_read_global(home))
    cfg.update(_read_project_local(project_root))
    return cfg
