"""Round-trippy YAML frontmatter parser/writer.

Critical invariants:
- Unknown keys preserved verbatim
- `tags:` array NEVER touched by writer
- Key order preserved on read+write that don't change content
- List items always quoted on write (survives Obsidian Linter and other strict YAML parsers)
"""
from collections import OrderedDict

import pytest

from lib.frontmatter import parse, write, update_keys

SAMPLE = """---
title: foo
created: 2026-05-09T11:55:00-04:00
modified: 2026-05-09T12:09:00-04:00
status: open
opener: 6afef2c8
participants: ["6afef2c8", "7bd265f4"]
tags: ["jd/agent", "jd/inter-session"]
aliases: ["foo"]
linter-yaml-title-alias: foo
---

# foo

body here
"""


def test_parse_returns_dict_and_body():
    fm, body = parse(SAMPLE)
    assert fm["title"] == "foo"
    assert fm["status"] == "open"
    assert fm["participants"] == ["6afef2c8", "7bd265f4"]
    assert fm["tags"] == ["jd/agent", "jd/inter-session"]
    assert "# foo" in body


def test_round_trip_no_change_is_byte_identical():
    fm, body = parse(SAMPLE)
    out = write(fm, body)
    assert out == SAMPLE


def test_update_keys_preserves_unknown_fields():
    fm, body = parse(SAMPLE)
    new_fm = update_keys(fm, {"thread-id": "abc12345", "thread-status": "open"})
    # New keys appended after existing ones
    assert new_fm["thread-id"] == "abc12345"
    # Originals preserved
    assert new_fm["title"] == "foo"
    assert new_fm["tags"] == ["jd/agent", "jd/inter-session"]


def test_update_keys_does_not_touch_tags():
    fm, body = parse(SAMPLE)
    new_fm = update_keys(fm, {"thread-status": "answered"})
    assert new_fm["tags"] == ["jd/agent", "jd/inter-session"]


def test_no_frontmatter_returns_empty_dict():
    fm, body = parse("# just a body\n")
    assert fm == {}
    assert body == "# just a body\n"


def test_parse_preserves_iso_strings():
    """ISO-8601 strings with timezone must round-trip exactly."""
    fm, body = parse(SAMPLE)
    out = write(fm, body)
    assert "2026-05-09T11:55:00-04:00" in out


def test_write_quotes_list_items_with_special_chars():
    """List items with spaces, dashes, special chars must be quoted on write
    so the output survives strict YAML parsers (Obsidian Linter etc.)."""
    fm = {"aliases": ["cross-session test from 30503d7b"], "thread-scope": ["03.14"]}
    out = write(fm, "")
    assert 'aliases: ["cross-session test from 30503d7b"]' in out
    assert 'thread-scope: ["03.14"]' in out


def test_write_quotes_list_item_with_yaml_alias_char():
    """Bare * in a flow sequence is a YAML alias reference; must be quoted to be a literal."""
    fm = {"thread-scope": ["*"]}
    out = write(fm, "")
    assert 'thread-scope: ["*"]' in out


def test_parse_and_write_round_trip_with_unquoted_input():
    """Existing files with unquoted lists parse correctly; on next write they get
    normalized to quoted form (one-time format upgrade for older files)."""
    legacy = '---\naliases: [foo bar]\n---\n\nbody\n'
    fm, body = parse(legacy)
    assert fm["aliases"] == ["foo bar"]
    out = write(fm, body)
    assert 'aliases: ["foo bar"]' in out


# v0.2.4 hardening tests (issue #18 follow-ups)


def test_parse_does_not_crash_on_double_dash_string():
    """`--123` is NOT an integer (the v0.2.x check `lstrip("-").isdigit()`
    accepted it and `int(s)` then crashed). Should parse as a string."""
    fm, _ = parse('---\nfoo: --123\n---\n\nbody\n')
    assert fm["foo"] == "--123"


def test_parse_handles_negative_int():
    """A leading `-` alone IS an integer when followed by digits."""
    fm, _ = parse('---\noffset: -42\n---\n\nbody\n')
    assert fm["offset"] == -42


def test_parse_treats_bare_dash_as_string():
    """`-` alone shouldn't be interpreted as a number."""
    fm, _ = parse('---\nfoo: "-"\n---\n\nbody\n')
    assert fm["foo"] == "-"


def test_parse_inline_list_respects_quoted_commas():
    """Quoted strings with internal commas must NOT be split. Pre-fix this
    parsed `["a, b", c]` into 3 tokens instead of 2."""
    fm, _ = parse('---\nitems: ["a, b", c]\n---\n\nbody\n')
    assert fm["items"] == ["a, b", "c"]


def test_parse_inline_list_handles_single_quotes():
    """Single-quoted items with commas behave the same as double-quoted."""
    fm, _ = parse("---\nitems: ['x, y', z]\n---\n\nbody\n")
    assert fm["items"] == ["x, y", "z"]


def test_parse_block_style_list():
    """`participants:` followed by indented `- foo` lines should populate
    a list, not be silently dropped to empty string."""
    text = (
        "---\n"
        "participants:\n"
        "  - alice\n"
        "  - bob\n"
        "  - cairo\n"
        "title: t\n"
        "---\n\nbody\n"
    )
    fm, _ = parse(text)
    assert fm["participants"] == ["alice", "bob", "cairo"]
    assert fm["title"] == "t"


def test_parse_block_style_list_with_quoted_items():
    """Quoted items in block lists get unquoted on parse."""
    text = (
        "---\n"
        "scope:\n"
        '  - "a, b"\n'
        "  - c\n"
        "---\n\nbody\n"
    )
    fm, _ = parse(text)
    assert fm["scope"] == ["a, b", "c"]


def test_parse_block_style_list_round_trips_to_inline():
    """Block-style on read, inline on write (Linter prefers inline form
    and our tests assert inline format for thread-scope etc.)."""
    text = (
        "---\nthread-scope:\n  - jd/03.14\n  - fern\n---\n\nbody\n"
    )
    fm, body = parse(text)
    out = write(fm, body)
    assert 'thread-scope: ["jd/03.14", "fern"]' in out


def test_format_scalar_quotes_strings_with_special_chars():
    """A scalar string containing `]`, newline, or `: ` must be quoted
    on write so it doesn't produce malformed YAML."""
    fm = {"summary": "see [link]: http://x"}
    out = write(fm, "")
    # `: ` is the YAML key/value separator → must quote
    assert '"see [link]: http://x"' in out


def test_format_scalar_does_not_quote_iso_timestamps():
    """ISO timestamps contain `:` but not `: ` (no space after) — they're
    plain scalars in YAML and must round-trip unquoted to keep the Linter
    happy."""
    fm = {"created": "2026-05-09T11:55:00-04:00"}
    out = write(fm, "")
    assert "created: 2026-05-09T11:55:00-04:00" in out
    assert '"2026-05-09' not in out


def test_format_scalar_does_not_quote_simple_jd_id():
    """Plain JD IDs like `02.14` shouldn't be quoted (they're already strings
    after parse, but writing them back unquoted is the Linter-preferred form
    and matches the rest of the plugin's output)."""
    fm = {"id": "02.14"}
    out = write(fm, "")
    assert "id: 02.14\n" in out


def test_format_scalar_quotes_leading_dash_string():
    """Leading `- ` would be parsed as a block-list item; bare `-` is null.
    Both must be quoted when emitted as scalar."""
    fm = {"foo": "- not a list"}
    out = write(fm, "")
    assert '"- not a list"' in out


def test_update_keys_returns_independent_deep_copy():
    """Mutating a list-valued field on the result must not reach back into
    the input dict — pre-fix the result was a shallow copy and `out[k].append`
    silently mutated the caller's `fm`."""
    original_aliases = ["a", "b"]
    fm = OrderedDict()
    fm["aliases"] = original_aliases
    fm["title"] = "t"
    out = update_keys(fm, {"thread-status": "open"})
    out["aliases"].append("c")
    assert original_aliases == ["a", "b"]
    out["aliases"][0] = "X"
    assert original_aliases[0] == "a"
