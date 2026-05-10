"""Round-trippy frontmatter parser. Stdlib only — uses regex for the simple subset
of YAML our threads use. Preserves unknown keys, key order, and original formatting
for unchanged sections.

Supported scalar types in frontmatter: strings (quoted or unquoted), inline lists
[a, b], booleans, integers, ISO-8601 timestamps. Block-style mappings are NOT
supported (we don't use them).
"""
import re
from collections import OrderedDict


_FENCE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def parse(text: str):
    """Parse frontmatter from text. Returns (OrderedDict, body_str)."""
    m = _FENCE.match(text)
    if not m:
        return OrderedDict(), text
    fm_text = m.group(1)
    body = text[m.end():]
    fm = OrderedDict()
    for line in fm_text.split("\n"):
        if not line.strip() or line.startswith("#"):
            continue
        kv = re.match(r"^([\w\-]+):\s*(.*)$", line)
        if not kv:
            continue
        key, val = kv.group(1), kv.group(2).strip()
        fm[key] = _parse_scalar(val)
    return fm, body


def _parse_scalar(s: str):
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [_strip_quotes(t.strip()) for t in inner.split(",") if t.strip()]
    if s in ("true", "false"):
        return s == "true"
    if s.lstrip("-").isdigit():
        return int(s)
    return _strip_quotes(s)


def _strip_quotes(s: str) -> str:
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    return s


def _format_scalar(v) -> str:
    if isinstance(v, list):
        items = [_format_list_item(x) for x in v]
        return "[" + ", ".join(items) + "]"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    return str(v)


def _format_list_item(v) -> str:
    """Inside a flow sequence, always quote string items so the output
    survives a round-trip through strict YAML parsers (Obsidian Linter, ruamel,
    PyYAML). Bare scalars in flow sequences are ambiguous to standard parsers
    when they contain spaces, dashes, dots, or anything that could parse as
    another type — this caused fields to be silently blanked in v0.2.0."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    s = str(v)
    escaped = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def write(fm, body):
    """Serialize frontmatter dict + body back into a string."""
    if not fm:
        return body
    lines = ["---"]
    for k, v in fm.items():
        lines.append(f"{k}: {_format_scalar(v)}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines) + body


def update_keys(fm, updates):
    """Return a new OrderedDict with updates merged in. New keys append after existing.
    Unknown keys preserved; `tags` is read-only (raises if `updates` mentions it)."""
    if "tags" in updates:
        raise ValueError("Plugin must not write to `tags:` (user-owned)")
    out = OrderedDict(fm)
    for k, v in updates.items():
        out[k] = v  # appends if new, overwrites if existing
    return out
