# claude-threads plugin notes

Conventions for sessions using this plugin:

- **Threads vs notifications.** Threads are multi-message conversations. For one-shot alerts (cron output, etc.), use a different surface — there's no first-class notifications API in this plugin (deferred to `claude-notify`).
- **Scope is identity, not addressing.** A thread declares scope tags; sessions subscribe by their own tags. Match overlap → delivery. Don't think "send a message *to* fern" — think "tag this thread with `fern` so any session subscribed to `fern` sees it."
- **Three poll regimes.** UserPromptSubmit covers active human turns. PostToolUse covers active autonomous turns. SessionStart covers boot. The fully-idle case (no human, no tool calls) needs cron escalation — Spec 3.
- **Plugin doesn't touch `tags:`.** That field belongs to the user/Obsidian linter. Plugin metadata lives under `thread-` prefix.
