"""Match function: given subscriber tags and target scope tags, return True iff
any subscriber pattern matches any scope tag.

Public API contract — see [[claude-identity plugin design]]. Consumer plugins
(claude-threads, jd-context) re-implement this same algorithm; both are tested
against tests/fixtures/match_cases.json for parity.

Pattern semantics:
  - Tags without "path:" prefix → fnmatch glob (* ? [class])
  - Tags with "path:" prefix    → pathlib.PurePath.match (supports **)
  - Mixed types (one path: one not) never match.
  - JD-style hierarchy: subscriber `jd/07` also matches scope `jd/07.02`,
    `jd/07.02.01`, etc. — the parent-folder convention is implicit. (v0.2.3)
"""
import fnmatch
import re
from pathlib import PurePath


# JD-style tag: "jd/" then digits with optional dotted segments.
# Used to detect when subscriber tag should match descendants in addition to
# exact equality. e.g. subscriber `jd/07` matches scope `jd/07.02` because
# 07.02 is a child of category 07 in the Johnny Decimal numbering scheme.
_JD_TAG_RE = re.compile(r"^jd/\d+(\.\d+)*$")


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
    if pattern_is_path or scope_is_path:
        return False  # mixed types never match
    # Plain → fnmatch first (handles exact + wildcards: "02.*", "[01]2.14", etc.)
    if fnmatch.fnmatchcase(scope_tag, pattern):
        return True
    # JD hierarchy: subscriber `jd/N` also matches scope `jd/N.M[.K...]`.
    # Without this, subscribing to `jd/07` (whole category) wouldn't surface
    # threads scoped to `jd/07.02` (a project within that category).
    if _JD_TAG_RE.match(pattern) and scope_tag.startswith(pattern + "."):
        return True
    return False
