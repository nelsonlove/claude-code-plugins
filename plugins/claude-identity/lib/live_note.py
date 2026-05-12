"""Per-agent live note management (issue #24).

Each session maintains a live working note at:
    <live_notes_dir>/<handle>.md

Default `live_notes_dir` is `~/.claude/agent-live-notes/`. Override via
config — typically to an Obsidian-vault JD slot like
`<vault>/00-09 System/03 LLMs & agents/03.15 Agent live notes/`.

Created on first /claude-identity:live-update invocation, updated in place
thereafter. Distinct from claude-notebook's `03.13 Agent notebook` (historical
session rollups) and the shared append-only `03.50 Agent friction log`.

If the agent renames mid-session, the next write goes to a new file at
`<live_notes_dir>/<new-handle>.md`. The old file is left in place (no
auto-rename); users can archive it manually or via a future doctor pass.
"""
import hashlib
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from lib import sidecar


# Built-in fallback template, used only when the configured template file
# (default: `~/.claude/agent-live-notes/template.md`) is absent. Users with
# an Obsidian vault typically override to a template file inside the vault
# (e.g. `03.03 Templates for category 03/Agent live note for {{handle}}.md`).
DEFAULT_TEMPLATE = """---
title: Agent live note for {{handle}}
created: {{date}}T{{time}}
modified: {{date}}T{{time}}
tags: [agent-live]
handle: {{handle}}
session-id: {{session-id}}
scope: [{{scope-csv}}]
cadence: "{{cadence}}"
aliases: [Agent live note for {{handle}}]
linter-yaml-title-alias: Agent live note for {{handle}}
---

# Agent live note for {{handle}}

**Session**: `{{session-id-short}}` · handle `{{handle}}` · scope `{{scope-csv}}`
**Cadence**: {{cadence}}
**Last updated**: {{date}}T{{time}}

## Current task

(what the agent is doing right now)

## Completed in this session

(what landed)

## Pending / awaiting review

(items handed up to user or supervisor)

## Open questions

(things surfaced upstream, not yet resolved)

## Live notes

(freeform working area)
"""


def resolve_live_notes_dir(home=None, project_root=None):
    """Return Path to the directory holding per-agent `<handle>.md` notes.

    Resolution order:
      1. `live_notes_dir` from global / project-local config
      2. Baked default (`~/.claude/agent-live-notes/`)

    The default lives under `~/.claude/` so the plugin works out-of-the-box
    for any user. Users with an Obsidian vault typically override to a JD
    slot like `<vault>/00-09 System/03 LLMs & agents/03.15 Agent live notes/`.
    """
    if home is None:
        home = os.path.expanduser("~")
    if project_root is None:
        project_root = os.getcwd()
    from lib import config
    cfg = config.load_config(home, project_root)
    return Path(cfg["live_notes_dir"]).expanduser()


def resolve_template_path(home=None, project_root=None):
    """Return Path to the live-note template file. Resolution order:
      1. `live_note_template` from global / project-local config (full path)
      2. Baked default (`~/.claude/agent-live-notes/template.md`)

    If the resolved file doesn't exist on disk, `load_template()` falls back
    to the baked DEFAULT_TEMPLATE string — so an unconfigured fresh install
    still produces valid notes.
    """
    if home is None:
        home = os.path.expanduser("~")
    if project_root is None:
        project_root = os.getcwd()
    from lib import config
    cfg = config.load_config(home, project_root)
    return Path(cfg["live_note_template"]).expanduser()


def load_template(home=None, project_root=None):
    """Read the live-note template from the configured file. Falls back to
    the baked DEFAULT_TEMPLATE string if the file is missing or unreadable."""
    try:
        path = resolve_template_path(home, project_root)
        if path.exists():
            return path.read_text(encoding="utf-8")
    except OSError:
        pass
    return DEFAULT_TEMPLATE


def resolve_note_path(live_notes_dir, handle):
    """Path to a given handle's live note. `live_notes_dir` is the configured
    directory (full path)."""
    return Path(live_notes_dir) / f"{handle}.md"


def _now_parts():
    now = datetime.now(timezone.utc).astimezone()
    return now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")


def render_template(template_text, vars_):
    """Substitute {{key}} placeholders with values from vars_."""
    out = template_text
    for k, v in vars_.items():
        out = out.replace("{{" + k + "}}", str(v))
    return out


def _atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, str(path))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# Section parsing: a section starts at `## <name>` and ends at the next `## ` or EOF.
_SECTION_RE = re.compile(r"^## (.+?)\s*$", re.MULTILINE)


def replace_section(text, section_name, new_body):
    """Replace the body under `## section_name`. Returns the updated text.
    Raises KeyError if the section is absent — caller decides whether to append.
    """
    matches = list(_SECTION_RE.finditer(text))
    for i, m in enumerate(matches):
        if m.group(1).strip() == section_name:
            section_start = m.end()
            section_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            # Preserve one blank line between heading and new body, and trailing newline.
            new_block = "\n\n" + new_body.strip() + "\n\n"
            return text[: section_start] + new_block + text[section_end:]
    raise KeyError(f"section '{section_name}' not found")


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
_MODIFIED_RE = re.compile(r"^modified:\s*(.+?)\s*$", re.MULTILINE)


def read_modified_field(text):
    """Extract the `modified:` value from frontmatter. Returns None if absent."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None
    field = _MODIFIED_RE.search(m.group(1))
    return field.group(1).strip() if field else None


def body_hash(text):
    """SHA-256 hash of the note body (everything AFTER the closing `---`).

    Used by the live-note watcher as a watermark: stable across Obsidian Linter
    touches that only modify frontmatter timestamps, sensitive only to real
    edits within the message sections. Returns hex digest, or None if the file
    has no frontmatter (in which case we hash the whole text).
    """
    m = _FRONTMATTER_RE.match(text)
    body = text[m.end():] if m else text
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def update_frontmatter_fields(text, fields):
    """Update specific fields in YAML frontmatter. Adds the field if absent.
    Replaces only top-level `key: value` lines; ignores nested structure.
    Returns the updated text.
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return text  # no frontmatter; bail
    fm = m.group(1)
    new_fm = fm
    for k, v in fields.items():
        pattern = re.compile(rf"^{re.escape(k)}:\s*.*$", re.MULTILINE)
        line = f"{k}: {v}"
        if pattern.search(new_fm):
            new_fm = pattern.sub(line, new_fm)
        else:
            new_fm = new_fm.rstrip() + "\n" + line
    return f"---\n{new_fm}\n---" + text[m.end():]


def session_id_short(session_id):
    """First 8 chars of UUID (the conventional display prefix)."""
    return (session_id or "")[:8]


def write_live_note(
    home,
    session_id,
    handle,
    scope,
    cadence,
    section,
    body,
    live_notes_dir=None,
    template_text=None,
    vault=None,  # deprecated; ignored
):
    """Create or update a live note for the given handle.

    Args:
      home: $HOME path (used for sidecar state + config lookups)
      session_id: full UUID
      handle: agent handle (e.g. "quill"); rejected by caller if UUID-default
      scope: list of subscriber tags (from claude-identity:list_tags); may be []
      cadence: freeform cadence string (defaults to "as work progresses")
      section: optional section name to replace (e.g. "Current task"); if None,
               body is written into the "Live notes" section
      body: content to write
      live_notes_dir: override the directory for `<handle>.md` files (defaults
               to resolve_live_notes_dir() — `live_notes_dir` config key,
               default `~/.claude/agent-live-notes/`)
      template_text: override template content (defaults to load_template())
      vault: deprecated; ignored

    Handle-rename mid-session: the new write creates a fresh `<new-handle>.md`
    at the configured live_notes_dir. The old `<old-handle>.md` is left in
    place — users can archive it manually or via a future doctor pass.

    Returns: dict {ok: True, path: <str>, created: <bool>}
    """
    del vault  # accepted for back-compat, ignored
    if live_notes_dir is not None:
        notes_dir = Path(live_notes_dir)
    else:
        notes_dir = resolve_live_notes_dir(home=home)
    template = template_text if template_text is not None else load_template(home=home)
    target_section = section or "Live notes"
    note_path = resolve_note_path(notes_dir, handle)
    date, time = _now_parts()
    timestamp = f"{date}T{time}"
    scope_csv = ", ".join(scope) if scope else ""
    cadence = cadence or "as work progresses"

    vars_ = {
        "handle": handle,
        "date": date,
        "time": time,
        "session-id": session_id,
        "session-id-short": session_id_short(session_id),
        "scope-csv": scope_csv,
        "cadence": cadence,
    }

    created = not note_path.exists()
    if created:
        text = render_template(template, vars_)
        try:
            text = replace_section(text, target_section, body)
        except KeyError:
            text = text.rstrip() + f"\n\n## {target_section}\n\n{body.strip()}\n"
    else:
        text = note_path.read_text(encoding="utf-8")
        try:
            text = replace_section(text, target_section, body)
        except KeyError:
            text = text.rstrip() + f"\n\n## {target_section}\n\n{body.strip()}\n"
        # Refresh modified/scope/cadence in frontmatter on subsequent writes.
        text = update_frontmatter_fields(text, {
            "modified": timestamp,
            "scope": f"[{scope_csv}]",
            "cadence": f'"{cadence}"',
        })
    _atomic_write(note_path, text)
    # Record the post-write body hash so the watcher can detect user-edits.
    # We hash the body (not frontmatter) because Obsidian Linter may rewrite
    # the `modified:` timestamp format independent of any real edit; the body
    # is stable across Linter passes, sensitive only to message-section edits.
    final_text = note_path.read_text(encoding="utf-8")
    seen = body_hash(final_text)
    if seen and session_id:
        try:
            sidecar.set_live_note_seen_body_hash(home, session_id, seen)
        except Exception:
            pass  # state-tracking is best-effort; don't fail the write
    return {"ok": True, "path": str(note_path), "created": created}
