"""Round-trippy YAML frontmatter parser/writer.

Critical invariants:
- Unknown keys preserved verbatim
- `tags:` array NEVER touched by writer
- Key order preserved on read+write that don't change content
- List items always quoted on write (survives Obsidian Linter and other strict YAML parsers)
"""
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
