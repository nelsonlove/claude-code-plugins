#!/usr/bin/env bash
# Smoke test: identity-session-start.sh with project-local default_tags.
set -e

PLUGIN_DIR=$(cd "$(dirname "$0")/.." && pwd)
TEST_HOME=$(mktemp -d)
TEST_PROJECT=$(mktemp -d)
trap "rm -rf $TEST_HOME $TEST_PROJECT" EXIT

# Set up registry entry
mkdir -p "$TEST_HOME/.claude/sessions"
cat > "$TEST_HOME/.claude/sessions/$$.json" <<EOF
{"pid":$$,"sessionId":"hooktest-uuid","cwd":"$TEST_PROJECT","status":"idle"}
EOF

# Set up project-local default_tags
mkdir -p "$TEST_PROJECT/.claude"
cat > "$TEST_PROJECT/.claude/claude-identity.local.md" <<EOF
---
default_tags: ["02.*", "vault-sweeper"]
---
EOF

# Run hook from the test project dir
cd "$TEST_PROJECT"
HOME="$TEST_HOME" CLAUDE_SESSION_ID="hooktest-uuid" "$PLUGIN_DIR/hooks/identity-session-start.sh"

# Assert sidecar contains default_tags AND an auto-assigned handle from wordlist
SIDECAR="$TEST_HOME/.claude/sessions-meta/hooktest-uuid.json"
test -f "$SIDECAR"
PLUGIN_DIR="$PLUGIN_DIR" python3 -c "
import json, sys, os
sys.path.insert(0, os.environ['PLUGIN_DIR'])
data = json.load(open('$SIDECAR'))
assert data['tags'] == ['02.*', 'vault-sweeper'], f'got {data[\"tags\"]}'
# v0.1.3: auto-handle from wordlist, deterministic on session_id
assert 'handle' in data, f'handle field missing: keys={list(data.keys())}'
from lib.wordlist import pick_handle
expected = pick_handle('hooktest-uuid')
assert data['handle'] == expected, f'got {data[\"handle\"]}, expected {expected}'
print('OK')
"
