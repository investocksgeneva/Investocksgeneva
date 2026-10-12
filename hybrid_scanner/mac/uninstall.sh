#!/bin/bash
# Remove the scheduled scan. Reports, settings and the code are kept;
# the script prints how to delete them if you want everything gone.

set -uo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
HOME_DIR="${HYBRID_HOME:-$HOME/HybridScanner}"
LABEL="com.investocksgeneva.hybridscanner"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null && echo "✓ Stopped the scheduled scan" \
  || echo "• No scheduled scan was running"
if [ -f "$PLIST" ]; then
  rm -f "$PLIST" && echo "✓ Removed $PLIST"
fi

cat <<EOF

Kept (delete manually if you no longer want them):
  Reports, logs, settings:  rm -rf "$HOME_DIR"
  Python environment:       rm -rf "$REPO/.venv"
  Downloaded price cache:   rm -rf "$REPO/data/cache"
EOF
