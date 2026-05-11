"""Round-trippy frontmatter parser. Stdlib only — uses regex for the simple subset
of YAML our threads use. Preserves unknown keys, key order, and original formatting
for unchanged sections.

Supported scalar types: strings (quoted or unquoted), inline lists [a, b],
block-style lists (`key:` then indented `- item` lines), booleans, integers,
ISO-8601 timestamps. Block-style mappings are NOT supported (we don't use them).
"""
import copy
import re
from collections import OrderedDict


_FENCE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
# Strict integer detector: optional leading `-`, then digits. Replaces the
# v0.2.x `s.lstrip("-").isdigit()` check which incorrectly accepted "--123"
# and crashed `int(s)` downstream.
_INT_RE = re.compile(r"^-?\d+$")
# Splits an inline-list interior (between [ and ]) into items, respecting
# double-quoted strings so commas INSIDE quotes don't split the item. Without
# this, `["a, b", c]` split as 3 tokens (`"a`, `b"`, `c`) and round-tripped
# wrong. Single-quoted strings are also handled.
_INLINE_LIST_ITEM_RE = re.compile(r'"[^"]*"|\'[^\']*\'|[^,]+')
# Detects strings that need to be quoted on emit for the YAML to be safe
# under strict parsers (Obsidian Linter, ruamel, PyYAML). A character is only
# dangerous in particular positions in standard YAML — over-quoting would
# break round-trip-byte-identical for ISO timestamps like
# `2026-05-09T11:55:00-04:00` (the `:` is plain because no space follows).
#
# Conditions, any of which forces quoting:
#   - newline anywhere (breaks the line-per-key emit)
#   - leading or trailing whitespace (silently stripped by parsers)
#   - first char is a YAML indicator: [ ] { } # & * ! | > % @ ` ? " '
#   - starts with `- ` (would parse as block-list item)
#   - bare `-` alone
#   - `---` alone (YAML document separator)
#   - contains `: ` anywhere (key/value separator inside a value)
#   - contains ` #` anywhere (start-of-comment inside a value)
_NEEDS_QUOTING_RE = re.compile(
    r'\n'
    r'|^\s|\s$'
    r"|^[\[\]\{\}#&*!|>%@`?\"']"
    r'|^- |^-$|^---$'
    r'|: | #'
)


def parse(text: str):
    """Parse frontmatter from text. Returns (OrderedDict, body_str)."""
    m = _FENCE.match(text)
    if not m:
        return OrderedDict(), text
    fm_text = m.group(1)
    body = text[m.end():]
    fm = OrderedDict()
    lines = fm_text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.startswith("#"):
            i += 1
            continue
        kv = re.match(r"^([\w\-]+):\s*(.*)$", line)
        if not kv:
            i += 1
            continue
        key, val = kv.group(1), kv.group(2).strip()
        # Block-style list: `key:` (empty value) followed by indented `- item`
        # lines. Collect them all into a Python list. Without this, a hand-
        # edited file using block style silently parsed `participants: ""`.
        if val == "" and i + 1 < len(lines) and re.match(r"^\s+-\s", lines[i + 1]):
            items = []
            j = i + 1
            while j < len(lines) and re.match(r"^\s+-\s", lines[j]):
                items.append(_strip_quotes(lines[j].split("-", 1)[1].strip()))
                j += 1
            fm[key] = items
            i = j
            continue
        fm[key] = _parse_scalar(val)
        i += 1
    return fm, body


def _parse_scalar(s: str):
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []
        items = []
        for tok in _INLINE_LIST_ITEM_RE.findall(inner):
            tok = tok.strip()
            if tok:
                items.append(_strip_quotes(tok))
        return items
    if s in ("true", "false"):
        return s == "true"
    if _INT_RE.match(s):
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
    s = str(v)
    if _NEEDS_QUOTING_RE.search(s):
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return s


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
    Unknown keys preserved; `tags` is read-only (raises if `updates` mentions it).

    Returns a deep copy of `fm` so callers can safely mutate the result —
    e.g. `out["aliases"].append(x)` won't reach back into the original list."""
    if "tags" in updates:
        raise ValueError("Plugin must not write to `tags:` (user-owned)")
    out = copy.deepcopy(fm)
    if not isinstance(out, OrderedDict):
        out = OrderedDict(out)
    for k, v in updates.items():
        out[k] = copy.deepcopy(v) if isinstance(v, (list, dict)) else v
    return out
