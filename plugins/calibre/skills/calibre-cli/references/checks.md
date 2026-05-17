# Calibre metadata safety checks

Reusable heuristics that guard against confidently-wrong metadata writes. Reference these from any command or external plugin that proposes metadata changes — they're the difference between "fixed the record" and "silently corrupted the record."

## Title-overlap check

**Purpose.** Detect when a proposed title differs sharply from the current title — a signal that the metadata source returned the wrong book (footgun #19) or that a vision-based proposal hallucinated.

**When to apply.** Before showing any proposed metadata to the user as "ready to apply," whether the proposal came from `fetch-ebook-metadata`, Claude vision, or any other source.

**The heuristic.** Tokenize both titles, drop stopwords, lowercase, set-intersect. Require at least 2 significant shared words for the proposal to count as "plausibly the same book."

```bash
# Inputs: $PROPOSED and $CURRENT (title strings).
# Output: exit 0 if overlap is acceptable, exit 1 otherwise.
#
# IMPORTANT: pass titles via env vars, NOT shell interpolation into the Python source.
# Titles routinely contain apostrophes ("The Devil's Dictionary", "Nietzsche's Genealogy").
# A single quote inside a -c "..." Python literal closes the string early and raises
# SyntaxError. The quoted heredoc (<<'PYEOF') keeps the Python source literal so the
# env-var values flow through cleanly.
export PROPOSED CURRENT
python3 - <<'PYEOF'
import os, sys
stops = {'the','a','an','of','for','in','and','&','to','on','by','from','with'}
a = set(w.lower() for w in os.environ['PROPOSED'].split() if w.lower() not in stops)
b = set(w.lower() for w in os.environ['CURRENT'].split()  if w.lower() not in stops)
overlap = a & b
if not overlap or len(overlap) < 2:
    print(f'NO SIGNIFICANT OVERLAP — likely wrong book. Proposed={a}, Current={b}')
    sys.exit(1)
print(f'Overlap: {overlap} — looks plausible')
PYEOF
```

**Edge case — current title is itself garbage.** If the current title is a filename (`0195036506.pdf`), a hash (`a3f8c91d.pdf`), or otherwise meaningless, the overlap will be empty *even when the proposal is correct*. Detect this case and exempt it.

**Exit-code convention (shared with the overlap check):**

- `exit 0` = "proceed with the normal flow" → current title looks real; **run the overlap check next**.
- `exit 1` = "short-circuit" → current title is garbage; **skip the overlap check** and handle via the fallback below.

This matches the overlap check's `exit 0` = plausible / `exit 1` = mismatch, so a wrapper script that chains the two can treat any `exit 1` as "stop the normal apply path."

```bash
# Garbage-shape detection — current title gives no signal, so overlap is meaningless.
python3 - <<'PYEOF'
import os, sys, re
t = os.environ['CURRENT']
GARBAGE = [
    r'^\d{10,13}(\.\w+)?$',          # ISBN-shaped
    r'^[A-Fa-f0-9]{8,}(\.\w+)?$',    # hash-shaped (case-insensitive; matches A3F8... and a3f8...)
    r'^(book|untitled|final|draft|file|document)[\s_-]*\d*(\.\w+)?$',  # generic
    r'^\w{1,3}(\.\w+)?$',            # absurdly short
]
if any(re.match(p, t, re.I) for p in GARBAGE):
    sys.exit(1)   # short-circuit: current is garbage, skip the overlap check
sys.exit(0)       # proceed normally: current is real, run the overlap check
PYEOF
```

When the garbage detector short-circuits (`exit 1`), the overlap check is *uninformative* — fall back to: (a) asking the user to confirm against the cover, (b) requiring a higher-confidence signal from the proposal source (e.g., for Claude proposals, require `confidence: high` on the title), or (c) leaving the record alone.

**Why 2 words minimum, not 1.** "The", "A", "An", "Of" etc. would single-word-match between almost any pair of titles even after stopword filtering misses an unusual one. Two significant words is the empirical threshold that catches series-volume mix-ups (Vol VI vs Vol VII share "Routledge", "History", "Philosophy" — overlap is 3+ — but completely-different books share fewer than 2).

**Failure mode this catches.** ISBN-13 9780195036503 returns "Spirit of Hegel" (correct); a one-digit-off ISBN 9780195036510 returns "Mary in Art" (wrong but confidently fetched). Overlap of `{spirit, hegel}` vs `{mary, art}` is `{}` → blocked.

**Failure mode this misses.** Two books with overlapping titles ("Introduction to Philosophy" by Author A vs "Introduction to Philosophy" by Author B). Overlap = `{introduction, philosophy}` → passes, but the wrong author lands in the DB. Mitigate by extending the check to authors when both source and target have authors — for proposed records where the author is also being changed, require either title-overlap-passes AND old-author-substring-of-new-author, or explicit user confirmation.

## Future checks (placeholder)

Other reusable checks belong here as they emerge:

- Author-name plausibility (e.g., "John Smith;" vs "John Smith" — the trailing punctuation flag from audit Class C)
- ISBN checksum validation before submitting to lookup
- Language code ISO-639 validation

Add each as a named subsection so commands and external plugins can reference them by anchor (e.g., `references/checks.md#title-overlap-check`).
