# claude-identity plugin notes

Conventions for sessions using this plugin:

- Run `/claude-identity:rename <name>` to set your persistent agent handle, or accept the auto-assigned word from the SessionStart wordlist. CC's built-in `/rename` is reserved for the session's current task/topic (status-line label) — it no longer writes the handle (as of v0.1.3). The two are independent.
- Without an explicit handle, the SessionStart hook deterministically assigns one from `lib/wordlist.py` (hashed on UUID).
- Use `/claude-identity:scope add` to declare interest. Other plugins (claude-threads, jd-context) react to changes via mtime-pull on `~/.claude/sessions-meta/<sid>.json`.
- Keep a per-agent live note in the Obsidian vault via `/claude-identity:live-update` (writes to `03 LLMs & agents/03.15 Agent live notes/<handle>.md`). Nelson follows the notes live in Obsidian. Use `bin/jump <handle>` for a zero-token shortcut to surface a specific agent's note.
- Cross-session tag assignment (`--session`) is unrestricted in v1. Spec 2 will add provenance + permission rules.
