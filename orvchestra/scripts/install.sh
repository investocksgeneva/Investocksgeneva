#!/bin/bash
# Installs Orvchestra as a launchd LaunchAgent, so `orvchestra serve` starts
# automatically at login and restarts if it ever crashes.
#
# This does NOT prevent macOS from sleeping when the lid is closed --
# launchd (like everything else) is suspended along with the rest of the
# system in clamshell sleep. Keep the lid open (or use an external display
# in clamshell mode with the lid closed and power connected) if you want
# Orvchestra to keep serving music unattended. See the README.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LABEL="com.orvchestra.serve"
PLIST_DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$HOME/Library/Application Support/Orvchestra/logs"

if [[ "$(uname)" != "Darwin" ]]; then
    echo "This installer is macOS-only (launchd is a macOS thing)." >&2
    exit 1
fi

UV_PATH="$(command -v uv || true)"
if [[ -z "$UV_PATH" ]]; then
    echo "Could not find 'uv' on your PATH. Install it first: https://docs.astral.sh/uv/" >&2
    exit 1
fi
UV_DIR="$(dirname "$UV_PATH")"

mkdir -p "$LOG_DIR"
mkdir -p "$HOME/Library/LaunchAgents"

sed \
    -e "s#__UV_PATH__#$UV_PATH#g" \
    -e "s#__UV_DIR__#$UV_DIR#g" \
    -e "s#__PROJECT_DIR__#$PROJECT_DIR#g" \
    -e "s#__LOG_DIR__#$LOG_DIR#g" \
    -e "s#__HOME__#$HOME#g" \
    "$SCRIPT_DIR/com.orvchestra.serve.plist.template" > "$PLIST_DEST"

# Unload first in case it's already installed (e.g. re-running after an
# update), so bootstrap below doesn't fail with "already loaded".
launchctl bootout "gui/$(id -u)" "$PLIST_DEST" >/dev/null 2>&1 || true

launchctl bootstrap "gui/$(id -u)" "$PLIST_DEST"
launchctl enable "gui/$(id -u)/$LABEL"

echo "Installed and started $LABEL."
echo "Logs: $LOG_DIR/serve.log and $LOG_DIR/serve.err.log"
echo "To stop watching it start automatically: scripts/uninstall.sh"
