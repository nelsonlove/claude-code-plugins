#!/usr/bin/env bash
# Test: SessionStart hook detects when its deterministic wordlist pick is
# already claimed by another session's sidecar and falls through to the
# UUID-prefix default rather than silently double-assigning.
set -e

PLUGIN_DIR=$(cd "$(dirname "$0")/.." && pwd)
TEST_HOME=$(mktemp -d)
TEST_PROJECT=$(mktemp -d)
trap "rm -rf $TEST_HOME $TEST_PROJECT" EXIT

mkdir -p "$TEST_HOME/.claude/sessions"
cat > "$TEST_HOME/.claude/sessions/$$.json" <<EOF
{"pid":$$,"sessionId":"hookcollision-uuid","cwd":"$TEST_PROJECT","status":"idle"}
EOF

# Precompute the word our test session_id would hash to, and pre-claim it
# in a "ghost" sidecar.
EXPECTED=$(PYTHONPATH="$PLUGIN_DIR" python3 -c "
from lib.wordlist import pick_handle
print(pick_handle('hookcollision-uuid'))
")

if [ -z "$EXPECTED" ]; then
  echo "FAIL: pick_handle returned empty"
  exit 1
fi

mkdir -p "$TEST_HOME/.claude/sessions-meta"
cat > "$TEST_HOME/.claude/sessions-meta/other-session.json" <<EOF
{"schema":1,"session_id":"other-session","tags":[],"handle":"$EXPECTED","added":"x","modified":"y"}
EOF

# Now run the hook. The collision check should detect that the EXPECTED handle
# is already taken and fall through to no-handle (sidecar gets created without
# the handle field).
cd "$TEST_PROJECT"
HOME="$TEST_HOME" CLAUDE_SESSION_ID="hookcollision-uuid" "$PLUGIN_DIR/hooks/identity-session-start.sh"

SIDECAR="$TEST_HOME/.claude/sessions-meta/hookcollision-uuid.json"
test -f "$SIDECAR" || { echo "FAIL: sidecar not created"; exit 1; }

python3 -c "
import json
data = json.load(open('$SIDECAR'))
# The collision should have made us fall through: no 'handle' field.
assert 'handle' not in data, f'collision NOT detected; handle = {data.get(\"handle\")!r}'
print('OK')
"
