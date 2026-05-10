"""JD-hierarchy expansion in the matcher (v0.2.3).

A subscriber tagged with `jd/<n>` should match any scope tag that's a
descendant in the Johnny Decimal numbering scheme — `jd/07` matches `jd/07.02`,
`jd/07.02.01`, etc. — because subscribing to a category implies subscribing to
its projects/subprojects.

This is a claude-threads-only behavior in v0.2.3; claude-identity gets the
same expansion in a v0.1.3 follow-up to maintain parity (the shared
match_cases.json fixture stays unchanged for now).
"""
import pytest

from lib.match import match


@pytest.mark.parametrize("subscriber,scope,expected", [
    # Exact equality still works
    (["jd/07"], ["jd/07"], True),
    # Hierarchy: project under category surfaces to category subscriber
    (["jd/07"], ["jd/07.02"], True),
    (["jd/07"], ["jd/07.99"], True),
    # Multi-level hierarchy: subprojects too
    (["jd/03.14"], ["jd/03.14.01"], True),
    (["jd/03"], ["jd/03.14.01"], True),
    # Sibling categories don't match
    (["jd/07"], ["jd/08"], False),
    (["jd/07"], ["jd/04.05"], False),
    # Boundary: must be `.` separator, not just shared prefix
    (["jd/07"], ["jd/07alpha"], False),
    (["jd/07"], ["jd/077"], False),
    (["jd/07"], ["jd/07-something"], False),
    # Reverse direction: subscriber `jd/07.02` should NOT match scope `jd/07`
    # (parent isn't a descendant of child)
    (["jd/07.02"], ["jd/07"], False),
    # Non-JD tags use plain fnmatch — no hierarchy expansion
    (["foo"], ["foo.bar"], False),
    (["jd/07"], ["jd-07.02"], False),  # different prefix shape
    # path: prefix tags unaffected
    (["path:/repos/foo"], ["jd/07.02"], False),
    (["jd/07"], ["path:/jd/07.02"], False),
])
def test_jd_hierarchy(subscriber, scope, expected):
    assert match(subscriber, scope) is expected


def test_jd_hierarchy_combined_with_other_subscriber_tags():
    """JD hierarchy is one matcher pass; other subscriber tags work alongside it."""
    # Subscribed to a category AND a handle
    assert match(["jd/07", "fern"], ["jd/07.02"]) is True
    assert match(["jd/07", "fern"], ["fern"]) is True
    # Neither matches
    assert match(["jd/07", "fern"], ["jd/08"]) is False
