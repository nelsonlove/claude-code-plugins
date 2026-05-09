"""Tests for lib.match — runs the shared fixtures plus edge cases."""
import json
from pathlib import Path

import pytest

from lib.match import match

FIXTURES = json.loads(
    (Path(__file__).parent / "fixtures" / "match_cases.json").read_text()
)


@pytest.mark.parametrize("case", FIXTURES["cases"], ids=lambda c: c["name"])
def test_fixture_case(case):
    result = match(case["subscriber"], case["scope"])
    assert result == case["expected"], f"{case['name']}: expected {case['expected']}, got {result}"


def test_returns_bool_not_truthy():
    """Public API must return strict bool for JSON-RPC predictability."""
    assert match(["02.14"], ["02.14"]) is True
    assert match(["xx"], ["02.14"]) is False
