#!/usr/bin/env bash
# Install the agent-approvals dependency chain and wire up the cold-resume job.
# Idempotent. Requires Homebrew (pickle/mdbase-cli) + network (tickle release).
set -uo pipefail
ROOT="${CLAUDE_PLUGIN_ROOT:?CLAUDE_PLUGIN_ROOT not set}"
have() { command -v "$1" >/dev/null 2>&1; }
BIN="/opt/homebrew/bin"; [ -w "$BIN" ] 2>/dev/null || BIN="$HOME/.local/bin"; mkdir -p "$BIN"
echo "== agent-approvals setup =="

# 1) pickle + mdbase-cli via the Homebrew tap
if ! have pickle || ! have mdbase; then
  if have brew; then
    brew tap nelsonlove/tap >/dev/null 2>&1 || true
    have pickle || brew install nelsonlove/tap/pickle || true
    have mdbase || brew install nelsonlove/tap/mdbase-cli || true
  else
    echo "  ! Homebrew not found — install pickle (nelsonlove/tap/pickle) + mdbase-cli manually."
  fi
fi

# 2) tickle from its GitHub release (platform-detected)
if ! have tickle; then
  os=$(uname -s | tr '[:upper:]' '[:lower:]')
  arch=$(uname -m); case "$arch" in arm64|aarch64) arch=arm64;; x86_64|amd64) arch=amd64;; esac
  asset="tickle-${os}-${arch}"
  echo "  installing tickle ($asset) -> $BIN/tickle"
  if curl -fsSL "https://github.com/callumalpass/tickle/releases/latest/download/$asset" -o "$BIN/tickle"; then
    chmod +x "$BIN/tickle"
  else
    echo "  ! could not fetch $asset — see https://github.com/callumalpass/tickle/releases"
  fi
fi

echo "-- dependencies --"
for t in pickle mdbase tickle; do echo "  $t: $(command -v "$t" || echo MISSING)"; done

# 3) install the resume job + start the daemon
if have tickle; then bash "$ROOT/scripts/setup-tickle.sh"; else echo "  (skipping resume-job install: tickle missing)"; fi

# 4) surface the collection config (user sets this once, per their vault)
if have pickle; then
  echo "-- pickle collections --"
  pickle collections list 2>/dev/null | sed 's/^/  /' \
    || echo "  none — run: pickle collections add <name> <path-to-your-Obsidian-Pickle-folder> --set-default"
fi
echo "== done =="
