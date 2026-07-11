---
name: pickle-ask
description: Use when you need a durable, possibly-async human approval — files a Pickle request AND arms an unbounded waiter in one action, then reconciles whichever channel (Obsidian inbox or this chat) answers first. Encodes when to route a decision to Pickle vs ask in chat vs just act. Use for consequential/irreversible actions, or when the human may be away, or when the decision gates a long-running continuation.
---

# pickle-ask

One action that sends a Pickle approval **and** makes its answer come back to
this session — with graceful fallback to a cold resume when the session is gone.

## When to use which channel (decide in order)

1. **Does a human need to decide at all?** Reversible + low-stakes + within your
   mandate/allowlist → **just act.** Over-asking is a failure. (The permission
   allowlist is the real gate here.)
2. **Human present and collaborative?** Live session, engaged, decision is about
   scope / preference / direction → **ask in chat.** Synchronous and open-ended;
   Pickle would be worse (slower, forces a binary).
3. **Consequential/irreversible, OR human may be away, OR gates an async
   continuation?** → **pickle-ask** (this skill).

Unifying rule: *chat = synchronous collaboration with a present human; Pickle =
asynchronous authorization for a possibly-absent one.*

- **Cold/headless agents:** don't judge — Pickle is the permission escalation
  channel. File one whenever you'd otherwise hit a permission wall (wire it as
  `--permission-prompt-tool`). See [[pickle]] and the resume/permissions setup.
- **Upgrade rule:** a chat question that goes unanswered because the human left
  should be *converted* to a Pickle so it reaches their phone and the session
  can go cold. Chat and Pickle are two faces of one decision.

## How (one action)

1. `pickle-ask.sh <pickle-ask flags> [--ops-handoff <path>]` — files the request
   and **auto-stamps the join** (current `session_id` from
   `$CLAUDE_CODE_SESSION_ID`, `cwd`, ops handoff) into `metadata`. Prints `REQID`.
2. Immediately launch **`pickle-wait.sh <REQID>`** as a background task. It
   **claims** the request for this session (heartbeat every 2s) and waits
   **indefinitely** (no timeout); its completion re-invokes this session with the
   decision.
3. Record `REQID` + the waiter's task id so you can reconcile later.

The claim (`~/.claude/pickle-state/claims/<REQID>`) tells the Tickle cold-path
"a live session owns this — skip." If the background task dies while the session
lives, relaunch `pickle-wait.sh <REQID>` (never re-ask) — the wait is unbounded
and self-healing.

## Reconcile on resolve (exactly once)

The decision may arrive from more than one channel. Whoever answers first wins;
tear the rest down:

- **Answered in Obsidian** → the waiter fires → resume.
- **Answered in chat** → mirror it into Pickle: `pickle respond` with the
  decision (`responder: in-session`), or mark the request `status: cancelled` if
  the human redirected. Then `TaskStop` the waiter so its echo can't re-fire.
- **Tickle / another session already acted** → the shared processed marker no-ops it.

On reconcile, always mark it handled in **shared** state so the cold-path skips:
```
touch ~/.claude/pickle-state/processed/<REQID>
rm -f ~/.claude/pickle-state/claims/<REQID>
```

Invariants: one Pickle response is the source of truth; the shared
`pickle-state/processed/<id>` marker guarantees exactly-once (both warm and
Tickle honor it); a fresh `pickle-state/claims/<id>` entry means "a live session
owns it — don't jump in." Stop the waiter before writing the response, or dedupe
the echo with the marker.

## Cold fallback (session gone)

If the session dies, its waiter dies with it — ownership is released. Then:

- **Resume by id** (richest): Tickle runs `claude -p --resume <session-id>
  "<payload>, continue"` — the same conversation continued as a full autonomous
  agent, scoped by that context's `.claude/settings.json` permissions.
- **Rebuild from handoff** (fallback): a fresh agent reconstructs from
  `metadata.ops_handoff` (the [[ops]] `.ops/` registry).

Liveness = ownership: a live waiter means this session owns the request and
Tickle skips it; no waiter means Tickle may take over. No separate lockfile.
