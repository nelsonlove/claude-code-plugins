---
name: setup-tickle
description: Install this plugin's Tickle cold-resume job into the local Tickle daemon (run once).
---

Install the `pickle-resume` Tickle job so an approval can resume a session **cold**
(when it is no longer live). This copies the job + scripts from the plugin into the
local Tickle config and starts the daemon.

First confirm Tickle is installed; if `tickle` is not on PATH, tell the user to install
it (https://github.com/callumalpass/tickle) and stop. Otherwise run:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/setup-tickle.sh"
```

Then report what it installed and whether the daemon is running.
