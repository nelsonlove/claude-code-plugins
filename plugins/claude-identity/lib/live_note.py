"""Per-agent live note management (issue #24).

Each session maintains a live working note at:
    <vault>/00-09 System/03 LLMs & agents/03.15 Agent live notes/<handle>.md

Created on first /claude-identity:live-update invocation, updated in place
thereafter. Distinct from `03.13 Agent notebook` (historical rollups) and
`03.50 Agent friction log` (shared append-only).

Vault path resolution order:
    1. OBSIDIAN_VAULT env var
    2. Hardcoded default: ~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian
"""
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from lib import sidecar


DEFAULT_VAULT = (
    Path.home()
    / "Library"
    / "Mobile Documents"
    / "iCloud~md~obsidian"
    / "Documents"
    / "Obsidian"
)

LIVE_NOTES_SUBPATH = Path("00-09 System") / "03 LLMs & agents" / "03.15 Agent live notes"

DEFAULT_TEMPLATE = """---
title: Agent live note for {{handle}}
jd-id: "03.15"
created: {{date}}T{{time}}
modified: {{date}}T{{time}}
tags: [jd/agent-live]
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


def resolve_vault_path():
    """Return Path to the Obsidian vault. Env override, else hardcoded default."""
    env = os.environ.get("OBSIDIAN_VAULT")
    if env:
        return Path(env).expanduser()
    return DEFAULT_VAULT


def resolve_note_path(vault, handle):
    """Path to a given handle's live note within the vault."""
    return Path(vault) / LIVE_NOTES_SUBPATH / f"{handle}.md"


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
    vault=None,
    template_text=None,
):
    """Create or update a live note for the given handle.

    Args:
      home: $HOME path (currently unused; reserved for future config lookups)
      session_id: full UUID
      handle: agent handle (e.g. "quill"); rejected by caller if UUID-default
      scope: list of subscriber tags (from claude-identity:list_tags); may be []
      cadence: freeform cadence string (defaults to "as work progresses")
      section: optional section name to replace (e.g. "Current task"); if None,
               body is written into the "Live notes" section
      body: content to write
      vault: override vault path (defaults to resolve_vault_path())
      template_text: override template (defaults to DEFAULT_TEMPLATE)

    Returns: dict {ok: True, path: <str>, created: <bool>}
    """
    vault = Path(vault) if vault else resolve_vault_path()
    template = template_text or DEFAULT_TEMPLATE
    target_section = section or "Live notes"
    note_path = resolve_note_path(vault, handle)
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
    # Record the post-write `modified:` value so the watcher can detect
    # user-edits (any subsequent change to modified is by definition not us).
    final_text = note_path.read_text(encoding="utf-8")
    seen = read_modified_field(final_text)
    if seen and session_id:
        try:
            sidecar.set_live_note_seen_modified(home, session_id, seen)
        except Exception:
            pass  # state-tracking is best-effort; don't fail the write
    return {"ok": True, "path": str(note_path), "created": created}
