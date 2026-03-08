# claude-notifications Plugin Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Claude Code plugin that provides a persistent cross-session notification inbox, allowing cron agents to leave messages that interactive sessions pick up.

**Architecture:** File-based store in `~/.claude/inbox/` (one markdown file per notification with YAML frontmatter). MCP server provides tools for Claude sessions to post/read/dismiss. Shell helper lets cron scripts post without Claude. Hooks inject pending notifications at session start and on each user prompt.

**Tech Stack:** Python 3 (MCP server, stdin/stdout JSON-RPC), Bash (shell helper + hooks)

**Proposal:** `/Users/nelson/Documents/00-09 System/00.02 System - Proposals/claude-notifications-plugin.md`

**Reference plugins:** `session-name` (MCP server pattern), `jd-workflows` (hooks pattern)

---

### Task 1: Scaffold plugin structure

**Files:**
- Create: `plugins/claude-notifications/.claude-plugin/plugin.json`
- Create: `plugins/claude-notifications/.mcp.json`

**Step 1: Create plugin.json**

```json
{
  "name": "claude-notifications",
  "version": "0.1.0",
  "description": "Persistent cross-session notification inbox for automated agents and cron jobs.",
  "author": {
    "name": "Nelson Love"
  }
}
```

**Step 2: Create .mcp.json**

```json
{
  "claude-notifications": {
    "type": "stdio",
    "command": "python3",
    "args": ["${CLAUDE_PLUGIN_ROOT}/server.py"]
  }
}
```

**Step 3: Commit**

```bash
cd ~/repos/claude-code-plugins
git add plugins/claude-notifications/
git commit -m "feat(claude-notifications): scaffold plugin structure"
```

---

### Task 2: MCP server — core inbox operations

**Files:**
- Create: `plugins/claude-notifications/server.py`

The server handles three tools: `post_notification`, `get_notifications`, `dismiss_notification`. Pattern follows `session-name/server.py` — plain Python, JSON-RPC over stdin/stdout.

**Step 1: Write server.py**

```python
#!/usr/bin/env python3
"""
claude-notifications MCP server

Persistent notification inbox for cross-session messaging.
Store: ~/.claude/inbox/ (one .md file per notification with YAML frontmatter).
"""
import sys
import json
import os
import re
import subprocess
from datetime import datetime, timezone

INBOX_DIR = os.path.expanduser("~/.claude/inbox")
os.makedirs(INBOX_DIR, exist_ok=True)


def send(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def make_filename(tags, source):
    """Generate inbox filename: {ISO-timestamp}_{primary-tag}_{source}.md"""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    primary_tag = tags[0] if tags else "untagged"
    # Sanitize source for filename
    safe_source = re.sub(r"[^a-zA-Z0-9_-]", "-", source)
    return f"{ts}_{primary_tag}_{safe_source}.md"


def write_notification(tags, source, message):
    """Write a notification file and fire terminal-notifier."""
    filename = make_filename(tags, source)
    filepath = os.path.join(INBOX_DIR, filename)

    # Build YAML frontmatter
    tags_yaml = json.dumps(tags)
    created = datetime.now(timezone.utc).isoformat()

    content = f"""---
tags: {tags_yaml}
source: {source}
created: {created}
---
{message}
"""
    with open(filepath, "w") as f:
        f.write(content)

    # Fire terminal-notifier as side effect
    try:
        subprocess.run(
            [
                "/opt/homebrew/bin/terminal-notifier",
                "-title", f"JD Notification [{tags[0]}]" if tags else "JD Notification",
                "-message", message[:200],
                "-sound", "default",
                "-group", f"jd-notify-{source}",
            ],
            capture_output=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # terminal-notifier not installed or timed out — not fatal

    return filename


def parse_notification(filepath):
    """Parse a notification file, returning dict with id, tags, source, created, message."""
    filename = os.path.basename(filepath)
    try:
        with open(filepath) as f:
            text = f.read()
    except (OSError, IOError):
        return None

    # Parse YAML frontmatter (simple parser — no PyYAML dependency)
    fm_match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    if not fm_match:
        return {"id": filename, "tags": [], "source": "", "created": "", "message": text.strip()}

    frontmatter, message = fm_match.group(1), fm_match.group(2).strip()

    # Extract fields from frontmatter
    tags_match = re.search(r'tags:\s*(\[.*?\])', frontmatter)
    source_match = re.search(r'source:\s*(.+)', frontmatter)
    created_match = re.search(r'created:\s*(.+)', frontmatter)

    tags = json.loads(tags_match.group(1)) if tags_match else []
    source = source_match.group(1).strip() if source_match else ""
    created = created_match.group(1).strip() if created_match else ""

    return {
        "id": filename,
        "tags": tags,
        "source": source,
        "created": created,
        "message": message,
    }


def tags_match(notification_tags, filter_tags):
    """Check if a notification matches any of the filter tags.

    Matching rules:
    - Exact match: "26.06" matches "26.06"
    - Area/category match: "26" matches "26" and "26.*"
    - Area range match: "20-29" matches "20-29"
    - A notification tagged ["26.06", "26", "20-29"] matches filters ["26"], ["20-29"], ["26.06"], etc.
    """
    if not filter_tags:
        return True
    return bool(set(notification_tags) & set(filter_tags))


def get_all_notifications(filter_tags=None):
    """Read all notifications, optionally filtered by tags. Sorted oldest first."""
    notifications = []
    if not os.path.isdir(INBOX_DIR):
        return notifications

    for filename in sorted(os.listdir(INBOX_DIR)):
        if not filename.endswith(".md"):
            continue
        filepath = os.path.join(INBOX_DIR, filename)
        notif = parse_notification(filepath)
        if notif and tags_match(notif["tags"], filter_tags):
            notifications.append(notif)

    return notifications


def dismiss(notification_id):
    """Delete a notification file by its ID (filename)."""
    filepath = os.path.join(INBOX_DIR, notification_id)
    try:
        os.unlink(filepath)
        return True
    except FileNotFoundError:
        return False


# ── Tool definitions ──────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "post_notification",
        "description": (
            "Post a notification to the persistent inbox. "
            "Use JD-style tags (e.g. ['26.06', '26', '20-29']) so notifications "
            "surface in relevant scoped sessions. Also fires a macOS notification."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "JD tags — area ('20-29'), category ('26'), or ID ('26.06'). Include all ancestors.",
                },
                "source": {
                    "type": "string",
                    "description": "Identifier for the posting agent (e.g. 'divorce-email-cron')",
                },
                "message": {
                    "type": "string",
                    "description": "The notification content. Can be multi-line markdown.",
                },
            },
            "required": ["tags", "source", "message"],
        },
    },
    {
        "name": "get_notifications",
        "description": (
            "Read pending notifications from the inbox. "
            "Optionally filter by JD tags to see only relevant notifications."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional JD tags to filter by. Omit to see all.",
                },
            },
        },
    },
    {
        "name": "dismiss_notification",
        "description": "Dismiss (delete) a notification from the inbox by its ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "The notification ID (filename) to dismiss.",
                },
            },
            "required": ["id"],
        },
    },
]


# ── MCP message handler ──────────────────────────────────────────────────────

def handle(msg):
    method = msg.get("method", "")
    msg_id = msg.get("id")

    if method == "initialize":
        send({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "claude-notifications", "version": "0.1.0"},
            },
        })

    elif method == "tools/list":
        send({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"tools": TOOLS},
        })

    elif method == "tools/call":
        params = msg.get("params", {})
        tool = params.get("name")
        args = params.get("arguments", {})

        if tool == "post_notification":
            tags = args.get("tags", [])
            source = args.get("source", "unknown")
            message = args.get("message", "")
            filename = write_notification(tags, source, message)
            send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": f"Notification posted: {filename}"}]
                },
            })

        elif tool == "get_notifications":
            filter_tags = args.get("tags")
            notifications = get_all_notifications(filter_tags)
            if not notifications:
                text = "No pending notifications."
            else:
                lines = [f"**{len(notifications)} pending notification(s):**\n"]
                for n in notifications:
                    tag_str = ", ".join(n["tags"])
                    lines.append(f"- **[{tag_str}]** ({n['source']}, {n['created'][:10]}): {n['message'][:200]}")
                    lines.append(f"  ID: `{n['id']}`")
                text = "\n".join(lines)
            send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": text}]
                },
            })

        elif tool == "dismiss_notification":
            nid = args.get("id", "")
            if dismiss(nid):
                send({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Dismissed: {nid}"}]
                    },
                })
            else:
                send({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Not found: {nid}"}]
                    },
                })

        else:
            send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Unknown tool: {tool}"},
            })

    # Notifications (no id) — no response needed


for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        handle(json.loads(line))
    except Exception:
        pass
```

**Step 2: Manually test server responds to initialize**

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | python3 ~/repos/claude-code-plugins/plugins/claude-notifications/server.py
```

Expected: JSON response with `protocolVersion`, `serverInfo.name` = `claude-notifications`

**Step 3: Commit**

```bash
cd ~/repos/claude-code-plugins
git add plugins/claude-notifications/server.py
git commit -m "feat(claude-notifications): MCP server with post/get/dismiss tools"
```

---

### Task 3: Shell helper for cron scripts

**Files:**
- Create: `plugins/claude-notifications/bin/notify.sh`

**Step 1: Write bin/notify.sh**

```bash
#!/usr/bin/env bash
# notify.sh — Post a notification to the claude-notifications inbox.
# Usage: notify.sh --tags "26.06,26,20-29" --source "my-cron" "Message body here"
#
# Writes directly to ~/.claude/inbox/ — no Claude or MCP server required.
# Also fires terminal-notifier for immediate macOS alert.

set -euo pipefail

INBOX_DIR="$HOME/.claude/inbox"
mkdir -p "$INBOX_DIR"

# ── Parse args ────────────────────────────────────────────────────────────────
TAGS=""
SOURCE="unknown"
MESSAGE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --tags)   TAGS="$2"; shift 2 ;;
        --source) SOURCE="$2"; shift 2 ;;
        *)        MESSAGE="$1"; shift ;;
    esac
done

if [[ -z "$MESSAGE" ]]; then
    echo "Usage: notify.sh --tags 'tag1,tag2' --source 'name' 'message'" >&2
    exit 1
fi

# ── Build tags array ──────────────────────────────────────────────────────────
IFS=',' read -ra TAG_ARRAY <<< "$TAGS"
TAGS_JSON=$(printf '%s\n' "${TAG_ARRAY[@]}" | python3 -c 'import sys,json; print(json.dumps([t.strip() for t in sys.stdin.read().strip().split("\n") if t.strip()]))')

# ── Write notification file ───────────────────────────────────────────────────
TIMESTAMP=$(date -u +"%Y-%m-%dT%H-%M-%S")
CREATED=$(date -u +"%Y-%m-%dT%H:%M:%S")
PRIMARY_TAG="${TAG_ARRAY[0]:-untagged}"
SAFE_SOURCE=$(echo "$SOURCE" | tr -c 'a-zA-Z0-9_-' '-')
FILENAME="${TIMESTAMP}_${PRIMARY_TAG}_${SAFE_SOURCE}.md"

cat > "$INBOX_DIR/$FILENAME" << NOTIF
---
tags: ${TAGS_JSON}
source: ${SOURCE}
created: ${CREATED}
---
${MESSAGE}
NOTIF

echo "Posted: $FILENAME"

# ── Fire terminal-notifier ────────────────────────────────────────────────────
if command -v /opt/homebrew/bin/terminal-notifier &>/dev/null; then
    /opt/homebrew/bin/terminal-notifier \
        -title "JD Notification [${PRIMARY_TAG}]" \
        -message "${MESSAGE:0:200}" \
        -sound default \
        -group "jd-notify-${SAFE_SOURCE}" 2>/dev/null || true
fi
```

**Step 2: Make executable**

```bash
chmod +x ~/repos/claude-code-plugins/plugins/claude-notifications/bin/notify.sh
```

**Step 3: Test it**

```bash
~/repos/claude-code-plugins/plugins/claude-notifications/bin/notify.sh \
  --tags "00,00-09" --source "test" "This is a test notification"
ls ~/.claude/inbox/
cat ~/.claude/inbox/*test*
```

Expected: File created in `~/.claude/inbox/` with correct frontmatter and content. terminal-notifier alert fires.

**Step 4: Clean up test file**

```bash
rm ~/.claude/inbox/*test*
```

**Step 5: Commit**

```bash
cd ~/repos/claude-code-plugins
git add plugins/claude-notifications/bin/
git commit -m "feat(claude-notifications): shell helper for posting from cron scripts"
```

---

### Task 4: SessionStart hook

**Files:**
- Create: `plugins/claude-notifications/hooks/hooks.json`
- Create: `plugins/claude-notifications/hooks/session-start.sh`

**Step 1: Write hooks.json**

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/hooks/session-start.sh"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/hooks/user-prompt-submit.sh"
          }
        ]
      }
    ]
  }
}
```

**Step 2: Write session-start.sh**

```bash
#!/usr/bin/env bash
# Inject pending notifications into session context at startup.

INBOX_DIR="$HOME/.claude/inbox"
LAST_CHECK_DIR="$HOME/.claude/inbox-state"
mkdir -p "$LAST_CHECK_DIR"

# Record session start time for UserPromptSubmit to compare against
echo "$(date -u +%s)" > "$LAST_CHECK_DIR/$$"

# Read all pending notifications
if [ ! -d "$INBOX_DIR" ] || [ -z "$(ls -A "$INBOX_DIR" 2>/dev/null)" ]; then
    exit 0
fi

COUNT=$(ls -1 "$INBOX_DIR"/*.md 2>/dev/null | wc -l | tr -d ' ')
if [ "$COUNT" -eq 0 ]; then
    exit 0
fi

# Build summary
SUMMARY="You have ${COUNT} pending notification(s) in the inbox. Use get_notifications to read them, or dismiss_notification to clear them. The user can also run /inbox."

ESCAPED=$(echo "$SUMMARY" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read().strip()))')

cat << EOF
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": ${ESCAPED}
  }
}
EOF

exit 0
```

**Step 3: Make executable**

```bash
chmod +x ~/repos/claude-code-plugins/plugins/claude-notifications/hooks/session-start.sh
```

**Step 4: Commit**

```bash
cd ~/repos/claude-code-plugins
git add plugins/claude-notifications/hooks/
git commit -m "feat(claude-notifications): SessionStart hook injects pending notification count"
```

---

### Task 5: UserPromptSubmit hook

**Files:**
- Create: `plugins/claude-notifications/hooks/user-prompt-submit.sh`

**Step 1: Write user-prompt-submit.sh**

```bash
#!/usr/bin/env bash
# Check for NEW notifications since last check and inject if found.

INBOX_DIR="$HOME/.claude/inbox"
LAST_CHECK_DIR="$HOME/.claude/inbox-state"
mkdir -p "$LAST_CHECK_DIR"

LAST_CHECK_FILE="$LAST_CHECK_DIR/$$"

# If no last-check file, this is the first prompt — create it and skip
# (SessionStart already showed the initial count)
if [ ! -f "$LAST_CHECK_FILE" ]; then
    echo "$(date -u +%s)" > "$LAST_CHECK_FILE"
    exit 0
fi

LAST_CHECK=$(cat "$LAST_CHECK_FILE")
NOW=$(date -u +%s)

# Update last-check timestamp
echo "$NOW" > "$LAST_CHECK_FILE"

# Find notification files newer than last check
if [ ! -d "$INBOX_DIR" ]; then
    exit 0
fi

NEW_COUNT=0
NEW_FILES=""
for f in "$INBOX_DIR"/*.md; do
    [ -f "$f" ] || continue
    FILE_TIME=$(stat -f %m "$f" 2>/dev/null || stat -c %Y "$f" 2>/dev/null || echo 0)
    if [ "$FILE_TIME" -gt "$LAST_CHECK" ]; then
        NEW_COUNT=$((NEW_COUNT + 1))
        NEW_FILES="$NEW_FILES $(basename "$f")"
    fi
done

if [ "$NEW_COUNT" -eq 0 ]; then
    exit 0
fi

SUMMARY="New since last check: ${NEW_COUNT} notification(s) arrived in the inbox. Use get_notifications to read them."

ESCAPED=$(echo "$SUMMARY" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read().strip()))')

cat << EOF
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": ${ESCAPED}
  }
}
EOF

exit 0
```

**Step 2: Make executable**

```bash
chmod +x ~/repos/claude-code-plugins/plugins/claude-notifications/hooks/user-prompt-submit.sh
```

**Step 3: Commit**

```bash
cd ~/repos/claude-code-plugins
git add plugins/claude-notifications/hooks/user-prompt-submit.sh
git commit -m "feat(claude-notifications): UserPromptSubmit hook detects new notifications mid-session"
```

---

### Task 6: /inbox command

**Files:**
- Create: `plugins/claude-notifications/skills/inbox/SKILL.md`

**Step 1: Write the skill**

```markdown
---
name: inbox
description: View, filter, and dismiss pending notifications from the cross-session inbox. Use when the user says "/inbox", "check inbox", "any notifications", or "clear notifications".
---

# Inbox

Show the user their pending notifications and let them act on them.

## Steps

1. Call `get_notifications` (no tag filter) to fetch all pending notifications.
2. Present them grouped by tag, showing source, date, and message.
3. Ask the user what they'd like to do:
   - Dismiss individual notifications by ID
   - Dismiss all notifications
   - Leave them for later
4. Call `dismiss_notification` for any the user wants to clear.
```

**Step 2: Commit**

```bash
cd ~/repos/claude-code-plugins
git add plugins/claude-notifications/skills/
git commit -m "feat(claude-notifications): /inbox skill for viewing and managing notifications"
```

---

### Task 7: Register plugin in marketplace

**Files:**
- Modify: `~/repos/claude-code-plugins/.claude-plugin/marketplace.json`

**Step 1: Read current marketplace.json**

Check the current format and add the new plugin entry.

**Step 2: Add claude-notifications entry**

Add to the plugins list:
```json
{
  "name": "claude-notifications",
  "version": "0.1.0",
  "description": "Persistent cross-session notification inbox for automated agents and cron jobs.",
  "source": "./plugins/claude-notifications"
}
```

**Step 3: Commit**

```bash
cd ~/repos/claude-code-plugins
git add .claude-plugin/marketplace.json
git commit -m "feat(claude-notifications): register in local marketplace"
```

---

### Task 8: Update divorce cron to use notify.sh

**Files:**
- Modify: `/Users/nelson/Documents/20-29 Family/26 Divorce/26.06 Legal email archive/update_case_files.sh`

**Step 1: Replace notify_success/notify_failure with calls to plugin's notify.sh**

Replace the `notify_success` function body with:
```bash
notify_success() {
    "$HOME/repos/claude-code-plugins/plugins/claude-notifications/bin/notify.sh" \
        --tags "26.06,26,20-29" --source "divorce-email-cron" "$1"
}
```

Replace the `notify_failure` function body with:
```bash
notify_failure() {
    "$HOME/repos/claude-code-plugins/plugins/claude-notifications/bin/notify.sh" \
        --tags "26.06,26,20-29" --source "divorce-email-cron" "FAILED: $1"
}
```

**Step 2: Update the Claude prompt to use post_notification**

In the PROMPT variable, add after the existing tasks:
```
5. Post a summary of what changed using the post_notification tool with tags ["26.06", "26", "20-29"] and source "divorce-email-cron". Include specifics about new emails and any action items.
```

And add `post_notification` to `--allowedTools`:
```bash
--allowedTools "Read,Write,Edit,Bash,Glob,Grep,mcp__claude-notifications__post_notification"
```

**Step 3: Test cron script dry-run**

```bash
bash -x "/Users/nelson/Documents/20-29 Family/26 Divorce/26.06 Legal email archive/update_case_files.sh"
```

Verify: notification file appears in `~/.claude/inbox/`, terminal-notifier fires.

**Step 4: Clean up test notification**

```bash
rm ~/.claude/inbox/*divorce*
```

**Step 5: Commit**

```bash
cd "/Users/nelson/Documents/20-29 Family/26 Divorce/26.06 Legal email archive"
git add update_case_files.sh 2>/dev/null || true
```

Note: this file may not be in a git repo — that's fine, the change is still recorded.

---

### Task 9: Install and end-to-end test

**Step 1: Install the plugin**

```bash
cd ~/repos/claude-code-plugins
# Plugin should auto-discover from the local marketplace
```

**Step 2: Test post via shell helper**

```bash
~/repos/claude-code-plugins/plugins/claude-notifications/bin/notify.sh \
    --tags "00,00-09" --source "test-run" "End-to-end test notification"
```

**Step 3: Start a new Claude session and verify**

Start a new `claude` session. Verify:
- SessionStart hook reports 1 pending notification
- `get_notifications` tool returns the test notification
- `/inbox` command shows it
- `dismiss_notification` removes it

**Step 4: Clean up and commit**

```bash
rm -f ~/.claude/inbox/*test-run*
cd ~/repos/claude-code-plugins
git add -A
git commit -m "feat(claude-notifications): complete plugin with inbox, hooks, and cron integration"
```

---

### Task 10: Log the work

**Step 1: Append to CLAUDE.org activity log**

```
** 2026-03-08 — Built claude-notifications plugin
   - Persistent cross-session notification inbox for automated agents
   - MCP server (post/get/dismiss), shell helper (bin/notify.sh), hooks (SessionStart + UserPromptSubmit), /inbox skill
   - Files: ~/repos/claude-code-plugins/plugins/claude-notifications/
   - Updated divorce cron to use notify.sh instead of ad-hoc terminal-notifier
   - Proposal: 00.02 System - Proposals/claude-notifications-plugin.md
```
