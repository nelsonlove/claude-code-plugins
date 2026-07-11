# Submitting to the official Claude Code plugin directory

**Process:** fill out <https://clau.de/plugin-directory-submission>. Anthropic reviews external
plugins against quality + security standards before inclusion in `anthropics/claude-plugins-official`
(it's a curated, Anthropic-managed directory — not a self-serve PR).

## Honest fitness caveat (read first)

agent-approvals integrates several **third-party, unofficial** tools:

- **Pickle CLI** (callumalpass) — no official release; distributed here via a fork + Homebrew tap.
- **Tickle** daemon (callumalpass).
- **mdbase / ops** (callumalpass).
- An **Obsidian vault** + the **Pickle Obsidian plugin**.

A curated official directory favors broadly-usable, self-contained plugins. The hard dependency
on this stack is the most likely reason a reviewer would decline — and nothing in this repo
changes that; it's a structural fit question. The realistic home is your own / a community
marketplace (where it already installs and runs).

## Submission-readiness (done)

- [x] Standard plugin structure (`plugin.json` + `marketplace.json`); installs via `/plugin`.
- [x] One-command dependency install (`/setup`).
- [x] Core plugin has **no stubs** — tier-3 wired; skill + hook + resume complete.
- [x] Security pass: validated inputs, untrusted-payload framing, opt-in autonomous daemon,
      localhost-bound bridge, documented posture.
- [x] Mobile (`apns-bridge` / iOS) marked experimental/optional (not core).
- [x] `LICENSE` (MIT); README covers purpose / install / security / prerequisites.

## Likely reviewer gates still open

- [ ] Works for a user who does **not** already run Callum's stack — today: no (needs the deps).
- [ ] Every dependency installable without building from source — Pickle only via the fork tap
      (upstream ships no release). Closing this means shepherding upstream Pickle/Tickle toward
      official releases, or vendoring/replacing those deps.

## Recommendation

Submit only if you're prepared to make the plugin self-contained (official dep releases or
vendoring). Otherwise keep it in your marketplace.
