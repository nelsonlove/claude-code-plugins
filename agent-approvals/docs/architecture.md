# Architecture — durable agent approvals, and how a mobile (iOS) client fits

This describes how the pieces fit together, framed for building an **iOS app** — which,
like the existing Android app, is just another **client of `pickle serve`**.

## 0. The one principle

**The markdown files are the source of truth.** Every tool — the CLI, `pickle serve`,
the Obsidian plugin, the Android/iOS app, the resume daemon — is only a reader/writer over
the same [mdbase](https://github.com/callumalpass/mdbase) collection files. Surfaces never
call each other; they **share state on disk**. So adding an iOS client is additive and
low-risk: it's one more reader/writer, not a new integration to wire.

## 1. The pieces

| Component | Role | Plane |
|---|---|---|
| **Pickle** (CLI + `pickle serve` + Obsidian plugin) | typed human-approval inbox (mdbase collection) | both |
| **agent-approvals** (this plugin) | the glue: `pickle-ask` (file + claim + wait), claim coordination, Tickle resume job | terminal |
| **Tickle** (launchd daemon) | cold-resume launcher — runs a gate + `claude -p --resume` | terminal |
| **ops** (`.ops/` registry) | repo-local system-of-record (items/tasks/handoffs) | repo |
| **TaskNotes** (Obsidian plugin + HTTP/MCP) | personal task ledger | vault |
| **mdbase** | the shared typed-markdown format under all of the above | — |
| **Claude Code session** | the agent; resumable by session id | terminal |
| **iOS app** (proposed) | native client of `pickle serve` | mobile |

## 2. Two planes, one format

- **Vault plane (Obsidian):** personal notes, TaskNotes tasks, a Pickle inbox (an in-vault,
  **non-dot** collection rendered as an Obsidian **Base**).
- **Repo/terminal plane (`~/projects/*/.ops`):** operational memory + repo-local Pickle
  collections (`.ops/_pickle`), read by agents and the CLI.
- The unifier is the **format** (mdbase markdown), not a location. The **agent** is the thing
  that operates across planes (reads `.ops`, files Pickle, updates TaskNotes).

Obsidian ignores dot-folders, so `.ops/` is invisible to it — which is why repo collections
are reachable via the CLI/server/mobile app but **not** the Obsidian plugin.

## 3. Data model (what a client reads/writes)

A Pickle collection is a folder: `_types/`, `requests/`, `responses/`, `attachments/<id>/`.

**Request lifecycle is derived from response links** (not a status field):
`no linked response = pending`, `one = answered`, `>1 = conflict`, `status: cancelled = cancelled`.

**Request** (key fields): `id` (ulid), `title`, `message` (short prompt), `body` (long context),
`kind` (`approval|choice|input|notice|message`), `priority`, `response_type`,
`response_type_definition` (the mdbase schema a client renders a form from), `attachments`,
`links`, `metadata`, `created_at`, plus derived `state`.

**Our join metadata** (stamped by `pickle-ask`, opaque to clients): `workflow: "pickle-ask"`,
`session_id`, `cwd`, `ops_handoff`. Clients can ignore these; the resume loop uses them.

**Response**: for approvals `{ "decision": "approve|reject|revise", "comment": "..." }`;
for `message` requests, a `pickle_response_ack`. Plus `responder`, `responded_at`.

## 4. Surfaces integrate through the files

Two surfaces pointed at the same folder are automatically consistent:

- **CLI** — any collection, by absolute path.
- **Obsidian plugin** — one **in-vault, non-dot** collection, rendered as a Base; Obsidian
  watches the folder, so external writes appear live.
- **`pickle serve`** — exposes **all** configured collections over one HTTP/WebSocket API.
- **Mobile clients (Android/iOS)** — talk to `pickle serve` → see all collections + push.

Example: answer on the phone → server writes a `responses/*.md` into the collection folder →
if that's the in-vault collection, the Obsidian Base updates; and the agent-approvals waiter
or Tickle notices the answer and resumes the session. Nobody called anybody — the file did it.

Boundary: the Obsidian plugin sees only the in-vault collection; repo `.ops/_pickle`
collections are server/CLI/mobile-only.

## 5. The resume loop (agent-approvals)

- **Warm** — `pickle-ask` files a request and arms `pickle-wait` (writes a heartbeat *claim*,
  waits indefinitely). On answer it re-invokes the *same* live session with full context.
- **Cold** — session gone → the Tickle daemon polls for answered + **ours** (`workflow=pickle-ask`)
  + resumable (`session_id`) + unclaimed requests, and runs `claude -p --resume <id>` to
  continue the same transcript.
- **Coordination** — *liveness = ownership*: a fresh claim makes Tickle skip; a stale claim
  (dead session) lets it take over; a shared `processed` marker guarantees exactly-once.

**A mobile answer feeds this loop for free** — because it writes the same response files the
waiter and Tickle already watch. The app needs to know nothing about sessions, Tickle, or ops.

## 6. Where the iOS app fits — the `pickle serve` contract

The iOS app is a **read/answer surface for Pickle collections**. It rides the exact API the
Android client uses.

### Networking
- Server: `pickle serve --listen 0.0.0.0:8787` (any port).
- Reach it over **Tailscale** (private mesh) — do **not** expose it publicly.
- Base URL e.g. `https://<tailscale-host>:8787`.

### Auth (token from the server's `~/.config/pickle/config.json`, or `pickle token`)
Send the token any one of these ways:
- `Authorization: Bearer <token>`
- `X-Pickle-Token: <token>`
- `?token=<token>`

If the server's token is empty, auth is skipped — never run that over a network.

### Collection selection
- `GET /api/v1/collections` — list them.
- Per request: header `X-Pickle-Collection: <name>` or query `?collection=<name>`; omit → default.

### Endpoints
| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness |
| GET | `/api/v1/collections` | list collections |
| GET | `/api/v1/inbox?status=pending\|answered\|all` | list requests |
| GET | `/api/v1/requests/{id}` | one request (+ `response_type_definition`) |
| POST | `/api/v1/requests` | create (agents; app usually doesn't) |
| POST | `/api/v1/requests/{id}/responses` | **submit the answer** |
| GET | `/api/v1/requests/{id}/attachments/{attachmentId}` | download attachment bytes |
| GET | `/api/v1/types`, `/api/v1/types/{name}` | schema definitions |
| GET | `/api/v1/events?after=<cursor>&limit=100` | event catch-up |
| WS  | `/api/v1/stream` | realtime events (`http→ws`, `https→wss`; same auth) |

### Realtime / notifications
- Subscribe to `wss://<host>:8787/api/v1/stream` for `request.created` / `request.answered`
  events (server re-scans every ~1s and pushes).
- **iOS-specific decision:** iOS suspends long-lived sockets in the background, so the WS gives
  you realtime only while foregrounded. For true background push you need **APNs**, which
  `pickle serve` does not provide. Options: (a) keep the socket while foregrounded and, on
  launch/resume, reconcile via `GET /api/v1/inbox?status=answered`; (b) build a small APNs
  bridge that subscribes to the stream server-side and pushes. This is the main design fork
  for an iOS port vs. Android's foreground service.

### Rendering the answer form
Each request carries `response_type_definition` — the mdbase type schema (fields, enums,
required markers). Build the response form from it (approve/reject/revise + comment for
approvals; ack for messages) and POST the payload to `/responses`.

### Attachments
`GET /api/v1/requests/{id}/attachments/{attachmentId}` returns bytes (png/jpg/webp/md/txt) —
render inline so the human can review the exact captured artifact.

## 7. Gotchas to design around

- **Event ids are not a durable cursor.** `/events` recomputes ids per snapshot; deletions/
  imports re-rank them. Dedup on **request id + state**, and reconcile via
  `/inbox?status=answered` on launch rather than trusting a saved `after` cursor.
- **Conflicts are real.** Two responses to one request → `conflict` state. Surface it; don't
  silently pick one. (Answering the same request on phone *and* in Obsidian causes this.)
- **The app is write-thin.** It should only create/answer requests. Sessions, Tickle, ops, and
  TaskNotes are out of scope — they react to the files the app writes.

## 8. Picture

```
                     ┌──────────────────────────────────────────────┐
                     │        mdbase markdown  (source of truth)     │
                     │     requests/  responses/  _types/  attach/   │
                     └── ▲ ──────── ▲ ──────── ▲ ──────── ▲ ─────────┘
      reads/writes       │          │          │          │
   ┌─────────────┐  ┌────┴────┐ ┌───┴────┐ ┌───┴─────┐ ┌──┴──────────┐
   │ Claude agent│  │ pickle  │ │Obsidian│ │ pickle  │ │ agent-appr. │
   │ (pickle-ask)│  │  CLI    │ │ plugin │ │ serve   │ │ waiter +    │
   └──────┬──────┘  └─────────┘ │ + Base │ │ HTTP/WS │ │ Tickle      │
          │ files a request     └────────┘ └────▲────┘ └──────┬──────┘
          │                                      │ Tailscale   │ resumes
          │                               ┌──────┴───────┐     ▼
          └────────── waits / resumed ◄───│ iOS / Android │  claude -p --resume <id>
                                          │    client     │
                                          └──────────────┘
```

Answer anywhere (Obsidian / iOS / CLI) → one response file → Obsidian reflects it **and** the
agent resumes. One format, many surfaces, no direct coupling.

## See also

- [ios-client.md](ios-client.md) — APNs-bridge design + Swift data models for building the iOS client.
