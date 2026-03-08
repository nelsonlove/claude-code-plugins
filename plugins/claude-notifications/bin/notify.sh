#!/usr/bin/env bash
# notify.sh — Post a notification directly to ~/.claude/inbox/
# Usage: notify.sh --tags "26.06,26,20-29" --source "name" "message"
#
# Writes a .md file with YAML frontmatter. No Claude or MCP needed.
# Also fires terminal-notifier if available.

set -euo pipefail

INBOX_DIR="$HOME/.claude/inbox"
TERMINAL_NOTIFIER="/opt/homebrew/bin/terminal-notifier"

tags=""
source_name=""
message=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --tags)
            tags="$2"
            shift 2
            ;;
        --source)
            source_name="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: notify.sh --tags \"26.06,26,20-29\" --source \"name\" \"message\""
            exit 0
            ;;
        *)
            message="$1"
            shift
            ;;
    esac
done

if [[ -z "$source_name" || -z "$message" ]]; then
    echo "Error: --source and message are required." >&2
    echo "Usage: notify.sh --tags \"26.06,26,20-29\" --source \"name\" \"message\"" >&2
    exit 1
fi

mkdir -p "$INBOX_DIR"

# Build timestamp and filename
ts_file=$(date -u +"%Y-%m-%dT%H-%M-%S")
ts_yaml=$(date -u +"%Y-%m-%dT%H:%M:%S")

# Primary tag = first tag, or "misc"
IFS=',' read -ra tag_array <<< "$tags"
primary_tag="${tag_array[0]:-misc}"

# Sanitize source for filename
safe_source=$(printf '%s' "$source_name" | tr -c 'a-zA-Z0-9_-' '-' | sed 's/-\{2,\}/-/g; s/^-//; s/-$//')
safe_source="${safe_source:-unknown}"

filename="${ts_file}_${primary_tag}_${safe_source}.md"
filepath="${INBOX_DIR}/${filename}"

# Build tags YAML array
tags_yaml="["
first=true
IFS=',' read -ra tag_array <<< "$tags"
for t in "${tag_array[@]}"; do
    t=$(echo "$t" | xargs)  # trim whitespace
    [[ -z "$t" ]] && continue
    if $first; then
        tags_yaml+="\"${t}\""
        first=false
    else
        tags_yaml+=", \"${t}\""
    fi
done
tags_yaml+="]"

cat > "$filepath" <<EOF
---
tags: ${tags_yaml}
source: ${source_name}
created: ${ts_yaml}
---
${message}
EOF

echo "Notification posted: ${filename}"

# Fire macOS notification (best-effort)
if [[ -x "$TERMINAL_NOTIFIER" ]]; then
    "$TERMINAL_NOTIFIER" \
        -title "Claude: ${source_name}" \
        -message "${message:0:200}" \
        -group "claude-notifications" \
        >/dev/null 2>&1 || true
fi
