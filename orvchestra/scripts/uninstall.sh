#!/bin/bash
# Stops and removes the Orvchestra launchd LaunchAgent installed by
# install.sh. Your library database and app data are untouched.
set -euo pipefail

LABEL="com.orvchestra.serve"
PLIST_DEST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [[ "$(uname)" != "Darwin" ]]; then
    echo "This uninstaller is macOS-only." >&2
    exit 1
fi

if [[ -f "$PLIST_DEST" ]]; then
    launchctl bootout "gui/$(id -u)" "$PLIST_DEST" >/dev/null 2>&1 || true
    rm -f "$PLIST_DEST"
    echo "Removed $LABEL."
else
    echo "$LABEL is not installed."
fi
