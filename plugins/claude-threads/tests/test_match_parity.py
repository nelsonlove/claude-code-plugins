"""Match parity: claude-threads' lib.match must produce identical results to
claude-identity's lib.match for every fixture case."""
import json
from pathlib import Path

import pytest

from lib.match import match

FIXTURES = json.loads(
    (Path(__file__).parent / "fixtures" / "match_cases.json").read_text()
)


@pytest.mark.parametrize("case", FIXTURES["cases"], ids=lambda c: c["name"])
def test_parity(case):
    assert match(case["subscriber"], case["scope"]) == case["expected"]
