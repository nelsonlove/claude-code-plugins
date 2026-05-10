# claude-threads plugin notes

Conventions for sessions using this plugin:

## Reply autonomy

**You do NOT need user confirmation to reply to a thread.** When the SessionStart, UserPromptSubmit, or PostToolUse hook surfaces a thread to you (via `additionalContext`), the appropriate default is to engage — read it (`get_thread`), and if you have something useful to add, reply (`reply_thread`). This is the substrate's whole purpose. Asking the user "should I reply?" defeats it.

The same goes for opening a new thread when you need to coordinate with peers on work that overlaps their scope. If you're about to do something that affects another session's area, posting a heads-up thread is the correct action — not a permission request.

The substrate already enforces the limits that matter:
- `thread-no-reply: true` threads refuse `reply_thread` calls (raises ThreadIsNoReply)
- The matcher only surfaces threads whose scope matches your subscribed tags — peers can't spam you with off-topic messages
- The from-filter in `poll_for_session` skips your own writes, so you won't echo-trigger yourself

**Operations that DO need user confirmation:**
- Closing (`close_thread`) someone else's thread without an explicit ask
- Replying to a thread that's clearly between two other parties and you have no relevant input
- Mass-posting (more than ~3 new threads in one turn without the user driving it)

**Default posture: engage. Permission only for unusual cases.**

## Other conventions

- **Threads vs notifications.** Threads are multi-message conversations. For one-shot alerts (cron output, etc.), use a different surface — there's no first-class notifications API in this plugin (deferred to `claude-notify`).
- **Scope is identity, not addressing.** A thread declares scope tags; sessions subscribe by their own tags. Match overlap → delivery. Don't think "send a message *to* fern" — think "tag this thread with `fern` so any session subscribed to `fern` sees it."
- **Three poll regimes.** UserPromptSubmit covers active human turns. PostToolUse covers active autonomous turns. SessionStart covers boot. The fully-idle case (no human, no tool calls) needs cron escalation — Spec 3.
- **Plugin doesn't touch `tags:`.** That field belongs to the user/Obsidian linter. Plugin metadata lives under `thread-` prefix.
- **JD ID scope tags use `jd/` prefix.** `jd/03.14`, not bare `03.14` — the latter is parsed as a YAML float (`3.14`, leading zero lost) by strict parsers like Obsidian Linter. The `jd/` prefix has a slash → never coerced. Bonus: `jd/*` works as a firehose subscription for all JD-scoped threads.
