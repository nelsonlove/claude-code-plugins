"""Tests for the single-word handle wordlist."""
import re

from lib.wordlist import WORDLIST, pick_handle


def test_wordlist_is_nonempty():
    assert len(WORDLIST) > 0


def test_wordlist_has_no_duplicates():
    """Curated list deduped at module load."""
    assert len(WORDLIST) == len(set(WORDLIST))


def test_wordlist_entries_are_valid_handles():
    """Every word must pass the registry validator (lowercase, 2-32 chars,
    word-style). Otherwise SessionStart auto-assign would write a value that
    set_handle would later reject."""
    valid_re = re.compile(r"^[a-z][a-z0-9]{1,15}(-[a-z][a-z0-9]{1,15})?$")
    for word in WORDLIST:
        assert valid_re.match(word), f"wordlist entry '{word}' fails registry validator"


def test_wordlist_no_reserved_tokens():
    reserved = {"*", "all", "any", "none", "self", "external", "unknown"}
    assert not (set(WORDLIST) & reserved)


def test_wordlist_no_uuid_prefix_shape():
    """8-hex-char words are rejected by the validator; pool must not contain them."""
    uuid_prefix = re.compile(r"^[0-9a-f]{8}$")
    for word in WORDLIST:
        assert not uuid_prefix.match(word), f"'{word}' looks like a UUID prefix"


def test_pick_handle_deterministic():
    sid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    first = pick_handle(sid)
    second = pick_handle(sid)
    assert first == second


def test_pick_handle_distributes():
    """Different session_ids should not all map to the same word."""
    sids = [f"{i:032x}-0000-0000-0000-000000000000" for i in range(100)]
    picks = {pick_handle(s) for s in sids}
    # With 100 inputs and a pool of ~150 words, we expect more than 30 unique
    # results (birthday paradox: ~50-60 typical). Loose lower bound for safety.
    assert len(picks) > 30, f"only {len(picks)} unique handles in 100 picks"


def test_pick_handle_returns_pool_word():
    sid = "12345678-1234-1234-1234-123456789012"
    assert pick_handle(sid) in WORDLIST


def test_pick_handle_empty_sid_returns_empty():
    assert pick_handle("") == ""
    assert pick_handle(None) == ""
