"""Single-word handle pool for SessionStart auto-assignment.

Per Nelson's call (2026-05-11): single words only, no Docker-style two-word
combos. Pool size is small relative to total agent population, so we accept
the birthday-paradox collision rate. When two sessions hash to the same word,
the SessionStart hook detects the collision (scanning other sidecars) and
falls through to the UUID-prefix default rather than silently double-assigning.

Curated mix: birds, plants, minerals, weather, crafts, CS pioneers, food,
mythological, animals. Selection is deterministic by session_id (full UUID
hashed mod pool size), so a session reconnecting with the same UUID gets the
same name back.
"""
import hashlib


WORDLIST = (
    # Birds
    "wren", "heron", "finch", "thrush", "kite", "raven", "swift",
    "lark", "robin", "owl", "petrel", "starling", "magpie", "kestrel",
    # Plants & flowers
    "fern", "moss", "sage", "willow", "alder", "cedar", "ivy", "lichen",
    "marigold", "clover", "thistle", "nettle", "yarrow", "rosehip",
    "bramble", "elder", "hawthorn", "rowan", "linden", "juniper",
    # Minerals & terrain
    "cairn", "quartz", "slate", "flint", "shale", "tide", "ember",
    "coral", "amber", "obsidian", "agate", "geode", "ridge", "delta",
    "fjord", "mesa", "tundra",
    # Weather & light
    "frost", "mist", "haze", "drift", "dapple", "dusk", "dawn", "shadow",
    "glimmer", "gloam", "rime", "halo",
    # Crafts & objects
    "quill", "loom", "anvil", "spindle", "kiln", "shard", "vellum",
    "satchel", "lantern", "compass", "sextant", "harp",
    # CS pioneers / scientists
    "ada", "babbage", "lovelace", "hopper", "turing", "knuth", "ritchie",
    "kernighan", "shannon", "vonneumann", "djikstra", "wirth", "stallman",
    "thompson", "kay",
    # Food
    "bento", "mochi", "miso", "ramen", "sushi", "tempura", "wasabi",
    "umami", "sourdough", "barley", "fennel", "pepper", "thyme",
    "rosemary", "basil",
    # Mythological / poetic
    "atlas", "calypso", "echo", "iris", "lyra", "nyx", "phoenix",
    "selene", "vega", "andromeda", "perseus", "orion",
    # Animals
    "otter", "fox", "lynx", "badger", "hare", "stoat", "marten", "ermine",
    "vole", "skunk", "ferret", "weasel",
    # Misc nature-adjacent
    "aslan", "goober", "davinci", "charles",
)

# Sanity check: no duplicates expected; if any sneak in via editing, fail loud
# at import time rather than silently shrinking the pool.
assert len(WORDLIST) == len(set(WORDLIST)), \
    f"wordlist has {len(WORDLIST) - len(set(WORDLIST))} duplicate(s)"


def pick_handle(session_id):
    """Deterministically pick a handle for a session_id from the pool.

    Hash the full UUID (not a prefix) so we use as much entropy as available.
    Returns one of the pool words; the same session_id always returns the same
    word across runs.
    """
    if not session_id:
        return ""
    digest = hashlib.sha256(session_id.encode("utf-8")).digest()
    # Take 4 bytes as an integer (32 bits of entropy is plenty for mod ~150).
    idx = int.from_bytes(digest[:4], "big") % len(WORDLIST)
    return WORDLIST[idx]
