# agent-approvals

A Claude Code **plugin**: durable human approvals for coding agents that **resume the
agent when you answer** — whether the session is still live or long gone.

Glue over three local-first tools by [@callumalpass](https://github.com/callumalpass):
[Pickle](https://github.com/callumalpass/pickle) (approval inbox),
[Tickle](https://github.com/callumalpass/tickle) (job daemon), and
[mdbase](https://github.com/callumalpass/mdbase) / [ops](https://github.com/callumalpass/ops)
(markdown-native state).

## The model

An agent hits a decision it can't make → files a Pickle request and stops guessing.
You answer from Obsidian (or your phone). The answer comes back two ways:

- **Warm** — session still alive: a background waiter (`pickle-wait.sh`) catches your
  answer and re-invokes *that same session* with full context.
- **Cold** — session gone: the Tickle daemon polls, sees the answer, and runs
  `claude -p --resume <id>` to continue the same conversation.

**Liveness = ownership.** The warm waiter writes a heartbeat *claim*; Tickle skips any
request a live session claims and only takes over once the claim goes stale. A shared
`processed` marker guarantees exactly-once — so warm and cold never double-fire.

## What's in the plugin

- `skills/pickle-ask/` — Claude Code skill (auto-discovered): when to route a decision to
  Pickle vs chat vs act; `pickle-ask.sh` (file + stamp join) and `pickle-wait.sh`
  (claiming waiter).
- `commands/setup-tickle.md` — `/setup-tickle`: installs the cold-resume Tickle job.
- `tickle/` — the job (`pickle-resume.yaml`) + claim-aware gate/resume scripts that
  `/setup-tickle` copies into the Tickle config.

- `hooks/` — a **SessionStart hook** that injects the *when to use Pickle* decision policy into every session (act / ask in chat / file an approval), so agents escalate consequential or async decisions instead of guessing. Delete `hooks/` to disable.

Runtime state lives outside the plugin: `~/.claude/pickle-state/{claims,processed}`.

## Install

```
/plugin marketplace add nelsonlove/agent-approvals
/plugin install agent-approvals
```

The `pickle-ask` skill and the approval-policy hook load automatically. Then run **`/setup`**
once — it installs the dependency chain (`pickle`, `mdbase-cli`, `tickle`), wires up the
cold-resume job, and starts the daemon.

You still provide the vault side yourself: the **Pickle Obsidian plugin** installed and pointed
at a collection, and `pickle collections add … --set-default` pointing the CLI at that folder.

### Optional (experimental): mobile

`apns-bridge/` + [docs/ios-client.md](docs/ios-client.md) are reference infra for a phone
client (via `pickle serve` + APNs). They require Apple Developer credentials and are **not**
part of the core plugin — the approval loop works fully without them.


## Deferred

- **Pickle-gated permissions** — route the cold agent's permission prompts to Pickle via
  `--permission-prompt-tool` (needs a small MCP shim). Today the cold resume inherits
  your normal permissions.

## Security

- **The cold-resume daemon is opt-in.** Installing the plugin only adds the skill + the
  approval-policy hook (both inert). The autonomous part — a Tickle job that runs `claude -p`
  when an approval is answered — activates only after you run `/setup-tickle`.
- **It runs with your normal permissions.** The resumed/rebuilt agent inherits your user +
  project `.claude/settings.json`; scope it there (allowlist / `--permission-mode`) to
  constrain the unattended agent.
- **Inputs are validated.** `resume.sh` only resumes a UUID session id, only runs in an
  existing directory, only reads ops handoffs at safe *relative* paths (no `..`/absolute),
  and caps + frames the answer payload as untrusted data in the prompt.
- **Keep the server private.** `pickle serve` and the apns-bridge are for a private network
  (Tailscale); the bridge binds `127.0.0.1`. Never expose them publicly; set a Pickle token.

## Not included

No secrets (the Pickle config token stays in `~/.config/pickle/`) and no runtime state.
