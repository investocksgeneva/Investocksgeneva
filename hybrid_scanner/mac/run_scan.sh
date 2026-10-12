#!/bin/bash
# Daily hybrid scan — run by launchd every weekday evening (see install.sh),
# or by hand: ./hybrid_scanner/mac/run_scan.sh
#
# Writes   ~/HybridScanner/reports/YYYY-MM-DD/report.html (+ CSVs, charts)
# Links    ~/HybridScanner/latest-report.html to the newest report
# Shows    a macOS notification with the signals and watch list
# Logs to  ~/HybridScanner/logs/scan-YYYY-MM-DD.log
#
# Personal settings (account size, risk, extra options) live in
# ~/HybridScanner/settings.env — created by install.sh, safe to edit.

set -uo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
HOME_DIR="${HYBRID_HOME:-$HOME/HybridScanner}"
PY="$REPO/.venv/bin/python"
TODAY="$(date +%Y-%m-%d)"
OUT="$HOME_DIR/reports/$TODAY"
LOG="$HOME_DIR/logs/scan-$TODAY.log"

mkdir -p "$OUT" "$HOME_DIR/logs" "$HOME_DIR/state"

notify() {  # notify "title" "message" — arguments, never spliced into AppleScript
  /usr/bin/osascript -e 'on run argv' -e 'display notification (item 2 of argv) with title (item 1 of argv)' \
    -e 'end run' "$1" "$2" >/dev/null 2>&1 || true
}

# Defaults; settings.env overrides them.
ACCOUNT_EQUITY=100000
RISK_PER_TRADE=0.01
UNIVERSE=sp500
EXTRA_ARGS=""
# shellcheck source=/dev/null
[ -f "$HOME_DIR/settings.env" ] && source "$HOME_DIR/settings.env"

if [ ! -x "$PY" ]; then
  notify "Hybrid scan failed" "Python environment missing — run hybrid_scanner/mac/install.sh again."
  echo "$(date) missing $PY" >>"$LOG"
  exit 1
fi

cd "$REPO" || exit 1
scan() {
  echo "=== $(date) — hybrid scan (equity $ACCOUNT_EQUITY, risk $RISK_PER_TRADE, universe $UNIVERSE)"
  # shellcheck disable=SC2086  # EXTRA_ARGS is intentionally word-split
  "$PY" -m hybrid_scanner.main --universe "$UNIVERSE" \
    --equity "$ACCOUNT_EQUITY" --risk "$RISK_PER_TRADE" \
    --export --plot --output-dir "$OUT" --report "$OUT/report.html" \
    --state-file "$HOME_DIR/state/last_bar.txt" \
    --notify macos --alert-title "Hybrid scan" $EXTRA_ARGS
}
if [ -t 1 ]; then
  # Run by hand in Terminal: show progress as well as logging it.
  echo "Scanning $UNIVERSE — about 2 minutes. Progress below; full log: $LOG"
  scan 2>&1 | tee -a "$LOG"
  rc=${PIPESTATUS[0]}
else
  scan >>"$LOG" 2>&1  # scheduled run: log only
  rc=$?
fi

if [ "$rc" -ne 0 ]; then
  notify "Hybrid scan failed (exit $rc)" "See $LOG"
elif [ -f "$OUT/report.html" ]; then
  ln -sfn "$OUT/report.html" "$HOME_DIR/latest-report.html"
else
  rmdir "$OUT" 2>/dev/null  # holiday / no new bar: drop the empty folder
fi

# Keep 90 days of reports and logs. Only touches dated folders/files we created.
find "$HOME_DIR/reports" -mindepth 1 -maxdepth 1 -type d -name '20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]' -mtime +90 -exec rm -rf {} + 2>/dev/null
find "$HOME_DIR/logs" -maxdepth 1 -type f -name 'scan-*.log' -mtime +90 -delete 2>/dev/null

exit "$rc"
