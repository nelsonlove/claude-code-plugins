"""Round-trippy YAML frontmatter parser/writer.

Critical invariants:
- Unknown keys preserved verbatim
- `tags:` array NEVER touched by writer
- Key order preserved on read+write that don't change content
"""
import pytest

from lib.frontmatter import parse, write, update_keys

SAMPLE = """---
title: foo
created: 2026-05-09T11:55:00-04:00
modified: 2026-05-09T12:09:00-04:00
status: open
opener: 6afef2c8
participants: [6afef2c8, 7bd265f4]
tags: [jd/agent, jd/inter-session]
aliases: [foo]
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
    assert body.startswith("# foo")


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
