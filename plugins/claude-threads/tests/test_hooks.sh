#!/usr/bin/env bash
# Smoke test: all 3 hooks run, emit additionalContext when match exists.
set -e

PLUGIN_DIR=$(cd "$(dirname "$0")/.." && pwd)
TEST_HOME=$(mktemp -d)
TEST_PROJECT=$(mktemp -d)
trap "rm -rf $TEST_HOME $TEST_PROJECT" EXIT

# Set up registry + sessions-meta + a thread that should match
SID="hooktest-$$-aaaa"
mkdir -p "$TEST_HOME/.claude/sessions" "$TEST_HOME/.claude/sessions-meta" \
         "$TEST_HOME/.claude/threads-state" "$TEST_HOME/.claude/threads"
cat > "$TEST_HOME/.claude/sessions/$$.json" <<EOF
{"pid":$$,"sessionId":"$SID","cwd":"$TEST_PROJECT","status":"idle"}
EOF
cat > "$TEST_HOME/.claude/sessions-meta/$SID.json" <<EOF
{"schema":1,"session_id":"$SID","tags":["02.*"],"added":"x","modified":"x"}
EOF
# Use Python helper to create a matching thread
PYTHONPATH="$PLUGIN_DIR" HOME="$TEST_HOME" python3 -c "
from lib.thread_store import create_thread
from pathlib import Path
create_thread(threads_dir=Path('$TEST_HOME/.claude/threads'),
              opener_handle='alice', scope=['02.14'], topic='test',
              first_message='hi', author_handle='alice', author_model='x')
"

# Run each hook
export CLAUDE_PLUGIN_ROOT="$PLUGIN_DIR"
for hook in threads-session-start threads-user-prompt-submit threads-post-tool-use; do
  echo "Testing $hook..."
  OUT=$(HOME="$TEST_HOME" "$PLUGIN_DIR/hooks/$hook.sh")
  if echo "$OUT" | grep -q "new thread"; then
    echo "  ✓ emitted match"
  else
    echo "  ✗ FAILED — output: $OUT"
    exit 1
  fi
  # Reset last_poll so next hook also sees the match
  rm -f "$TEST_HOME/.claude/threads-state/$SID.json"
done

echo "All 3 hooks OK."
