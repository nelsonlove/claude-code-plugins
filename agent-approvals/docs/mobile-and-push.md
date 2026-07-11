# Mobile & push — plan and options (held for future)

Captures where the phone-notification work stands and the paths forward, so it can be
picked up later. Nothing here is "running" — it's tested components + a decision to make.

## What's built & tested

- **Bridge** (`apns-bridge/bridge.mjs`) — subscribes to `pickle serve`'s WebSocket and
  notifies on each new, still-pending request. Sinks:
  - **ntfy** (free) — publishes with **Approve/Reject buttons** that POST to `pickle serve`.
    *Verified against ntfy.sh* (buttons wired to the respond endpoint; `NTFY_ACTION_TOKEN`
    keeps the real token out of the payload).
  - console / macOS notification (dev).
  - **APNs** (native iOS) — still a stub; needs Apple credentials.
  - Hardened: persistent dedup (30d), `state == pending` only, `/register` bound to localhost.
- **iOS app** (`~/repos/pickle-ios`) — tier-1 SwiftUI: settings → inbox with live WS refresh →
  answer form from `response_type_definition`. Foundation layer type-checks; `xcodegen`
  project generates; **views are unverified** (need full Xcode, which isn't installed).
  Foreground-only (no background push).

## The blocker for "standing it up" now

- The plan was **self-hosted ntfy** on the Mac (private — token stays on the tailnet). But
  **ntfy's server is Linux-only**: the macOS binaries (brew *and* the official release) are
  client-only (no `serve`), and there's no Docker here. So self-hosting on the Mac is out.
- Standing up persistent services that **expose `pickle serve`** (it serves the Obsidian vault)
  and **embed the Pickle token** is security-sensitive — the harness flagged it, correctly.

## Free-push options (decide when ready)

| Option | Tap-to-approve | Token exposure | Exposes vault on network | Effort |
|---|---|---|---|---|
| **Telegram bot** ⭐ | yes | **none** (stays on Mac) | **no** | + Telegram sink in the bridge; BotFather bot (2 min) |
| ntfy.sh, notify-only | no (answer in Obsidian/app) | none | no (serve stays localhost) | tiny |
| ntfy.sh, with buttons | yes | token on **public** ntfy.sh | yes (tailnet) | tiny (already built) |
| self-host ntfy | yes | none | tailnet | needs a Linux box / Docker |

**Recommendation: Telegram.** The bridge sends inline Approve/Reject buttons, **long-polls
Telegram** for the tap, then answers `pickle serve` **locally** — so the token never leaves the
Mac and `pickle serve` can stay on localhost (no vault exposure). Only real cost: a Telegram sink
(~an afternoon) + a free BotFather bot + your chat id.

## Paid path (native)

Native iOS app (`pickle-ios`) + **APNs** — needs the **Apple Developer Program ($99/yr)** for the
push entitlement, a `.p8` key, and an App ID with push. Then finish the bridge's `sendPush()` APNs
sink. Gives in-app native notifications + the richer SwiftUI UI. The free tier covers everything
*except* push (Simulator + own-device sideloading are free).

## If/when standing it up — the safe recipe

- **Never** put the Pickle token in a launchd plist — read it at runtime in a wrapper
  (`export PICKLE_TOKEN="$(pickle token)"`), so it lives only in `~/.config/pickle/`.
- Bind any exposed service to the **Tailscale IP only** (`100.x`), never `0.0.0.0`/public.
- Telegram and ntfy-notify-only need **no** vault exposure (`pickle serve` stays localhost).
- Run the bridge (and `pickle serve` if exposure is needed) as launchd LaunchAgents
  (`RunAtLoad` + `KeepAlive`); removable via `launchctl unload` + `rm`.

## Prereqs recap

- `pickle serve` running (localhost is enough for Telegram / notify-only; Tailscale-bound only
  for the button paths and the iOS app).
- Tailscale is present (`100.79.254.104`) — needed only where the phone reaches `pickle serve`
  directly (ntfy buttons, the iOS app), not for Telegram/notify-only.
