#!/usr/bin/env bash
# Install the pickle-resume Tickle job + scripts from this plugin into the local
# Tickle config and (re)start the daemon. Idempotent. Copies (not symlinks) so it
# survives plugin-cache path changes; re-run after a plugin update.
set -euo pipefail
ROOT="${CLAUDE_PLUGIN_ROOT:?CLAUDE_PLUGIN_ROOT not set}"
TCFG="${TICKLE_CONFIG_HOME:-$HOME/Library/Application Support/tickle}"

command -v tickle >/dev/null 2>&1 || { echo "error: 'tickle' not on PATH — install callumalpass/tickle first."; exit 1; }

mkdir -p "$TCFG/jobs" "$TCFG/scripts/pickle-resume" \
         "$HOME/.claude/pickle-state/claims" "$HOME/.claude/pickle-state/processed"
cp "$ROOT/tickle/jobs/pickle-resume.yaml" "$TCFG/jobs/pickle-resume.yaml"
cp "$ROOT/tickle/scripts/pickle-resume/"*.sh "$TCFG/scripts/pickle-resume/"
chmod +x "$TCFG/scripts/pickle-resume/"*.sh

tickle validate pickle-resume
tickle service install >/dev/null 2>&1 || true
tickle service start   >/dev/null 2>&1 || true
echo "pickle-resume installed; daemon:"; tickle service status 2>&1 | grep -iE "state" | head -1 || true
