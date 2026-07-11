#!/usr/bin/env bash
# SessionStart: inject the "when to use Pickle" decision policy into every session,
# so agents know to escalate consequential/async decisions instead of guessing.
set -euo pipefail
cat >/dev/null 2>&1 || true   # consume the SessionStart JSON on stdin
python3 - <<'PY'
import json
policy = (
"Approval policy (agent-approvals): route each decision by its consequence and whether the human is present.\n"
"- ACT: if it is reversible and within your mandate, just do it — do not ask.\n"
"- ASK IN CHAT: if the human is present and it is a scope / preference / direction question.\n"
"- FILE A PICKLE APPROVAL (use the pickle-ask skill): before a consequential or irreversible action\n"
"  (commit/push to shared branches, deploy, send external messages, spend money, delete data), OR when\n"
"  the human may be away, OR when the decision gates long-running / unattended work. Prefer this over\n"
"  guessing or blocking. If unsure between chat and Pickle: if the answer can wait or you might lose the\n"
"  human's attention, use Pickle.\n"
"- NOTIFY THE HUMAN / HAND OFF TO ANOTHER AGENT: use the comms-send skill (never assume a human reads\n"
"  your session). Blockers, handoffs, FYIs, and async pings route through the comms agent via comms-send,\n"
"  not raw pickle commands."
)
print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": policy}}))
PY
