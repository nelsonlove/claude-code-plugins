"""Match function: given subscriber tags and target scope tags, return True iff
any subscriber pattern matches any scope tag.

Public API contract — see [[claude-identity plugin design]]. Consumer plugins
(claude-threads, jd-context) re-implement this same algorithm; both are tested
against tests/fixtures/match_cases.json for parity.

Pattern semantics:
  - Tags without "path:" prefix → fnmatch glob (* ? [class])
  - Tags with "path:" prefix    → pathlib.PurePath.match (supports **)
  - Mixed types (one path: one not) never match.
"""
import fnmatch
from pathlib import PurePath


def match(subscriber_tags, target_scope):
    """Return True iff any subscriber pattern matches any target_scope tag."""
    for pattern in subscriber_tags:
        for scope_tag in target_scope:
            if _match_one(pattern, scope_tag):
                return True
    return False


def _match_one(pattern: str, scope_tag: str) -> bool:
    pattern_is_path = pattern.startswith("path:")
    scope_is_path = scope_tag.startswith("path:")

    if pattern_is_path and scope_is_path:
        return PurePath(scope_tag[5:]).match(pattern[5:])
    if not pattern_is_path and not scope_is_path:
        return fnmatch.fnmatchcase(scope_tag, pattern)
    return False
