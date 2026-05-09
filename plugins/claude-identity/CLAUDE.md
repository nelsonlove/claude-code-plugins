# claude-identity plugin notes

Conventions for sessions using this plugin:

- Run `/rename <name>` early in the session to set your handle. Without it your handle is the first 8 chars of your UUID.
- Use `/identity:scope add` to declare interest. Other plugins (claude-threads, jd-context) react to changes via mtime-pull on `~/.claude/sessions-meta/<sid>.json`.
- Cross-session tag assignment (`--session`) is unrestricted in v1. Spec 2 will add provenance + permission rules.
