#!/bin/bash
# One-time setup of the hybrid scanner on a Mac.
#
#   ./hybrid_scanner/mac/install.sh               # install + test + schedule (weekdays 23:00)
#   SCAN_HOUR=22 SCAN_MINUTE=30 ./hybrid_scanner/mac/install.sh   # different time
#   ./hybrid_scanner/mac/install.sh --no-schedule # install + test only
#
# Safe to re-run: it updates packages and rewrites the schedule.

set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
HOME_DIR="${HYBRID_HOME:-$HOME/HybridScanner}"
LABEL="com.investocksgeneva.hybridscanner"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
SCAN_HOUR="${SCAN_HOUR:-23}"
SCAN_MINUTE="${SCAN_MINUTE:-0}"
SCHEDULE=1
TEST=1
for arg in "$@"; do
  case "$arg" in
    --no-schedule) SCHEDULE=0 ;;
    --no-test) TEST=0 ;;
    *) echo "Unknown option: $arg"; exit 2 ;;
  esac
done

step() { printf '\n\033[1m▸ %s\033[0m\n' "$1"; }
ok()   { printf '  ✓ %s\n' "$1"; }
fail() { printf '\n\033[31m✗ %s\033[0m\n' "$1" >&2; exit 1; }

# --------------------------------------------------------------------------- #
step "Checking this Mac"
[ "$(uname -s)" = "Darwin" ] || fail "This installer is for macOS."
case "$REPO" in
  "$HOME/Documents"*|"$HOME/Desktop"*|"$HOME/Downloads"*|"$HOME/Library/Mobile Documents"*)
    fail "The project is in a privacy-protected folder:
    $REPO
  macOS blocks scheduled jobs from reading Documents, Desktop, Downloads and iCloud.
  Move it to your home folder, then run this again:
    mv \"$REPO\" ~/Investocksgeneva && cd ~/Investocksgeneva && ./hybrid_scanner/mac/install.sh" ;;
esac
ok "Project folder: $REPO"

# --------------------------------------------------------------------------- #
step "Finding Python 3.11 or newer"
PYTHON=""
for cand in python3.13 python3.12 python3.11 \
            /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
            /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
            /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 \
            /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
  p="$(command -v "$cand" 2>/dev/null || true)"
  [ -n "$p" ] || continue
  if "$p" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    PYTHON="$p"; break
  fi
done
if [ -z "$PYTHON" ]; then
  fail "No Python 3.11+ found. (The python3 that ships with macOS is 3.9 — too old.)
  Install Python 3.12 from https://www.python.org/downloads/macos/
  (the 'macOS 64-bit universal2 installer'), then run this script again."
fi
ok "Using $PYTHON ($("$PYTHON" --version))"

# --------------------------------------------------------------------------- #
step "Creating the scanner's own Python environment (.venv)"
if [ -x "$REPO/.venv/bin/python" ] && ! "$REPO/.venv/bin/python" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
  rm -rf "$REPO/.venv"  # built with an old Python — rebuild
fi
[ -x "$REPO/.venv/bin/python" ] || "$PYTHON" -m venv "$REPO/.venv"
"$REPO/.venv/bin/python" -m pip install --quiet --upgrade pip
"$REPO/.venv/bin/python" -m pip install --quiet -r "$REPO/hybrid_scanner/requirements.txt"
ok "Packages installed (pandas, numpy, yfinance, matplotlib, …)"

# --------------------------------------------------------------------------- #
step "Preparing $HOME_DIR"
mkdir -p "$HOME_DIR/reports" "$HOME_DIR/logs" "$HOME_DIR/state"
if [ ! -f "$HOME_DIR/settings.env" ]; then
  cat >"$HOME_DIR/settings.env" <<'EOF'
# Hybrid scanner — personal settings. Edit freely; used by every scheduled run.

# Account size used for position sizing (in your account currency)
ACCOUNT_EQUITY=100000

# Risk per trade as a fraction of equity (0.01 = 1%)
RISK_PER_TRADE=0.01

# Universe: sp500
UNIVERSE=sp500

# Any other scanner options, e.g.:
#   EXTRA_ARGS="--set risk.target_r_multiple=3 --set pullback.ma_period=10"
EXTRA_ARGS=""
EOF
  ok "Created settings.env (account size, risk per trade) — edit any time"
else
  ok "Kept your existing settings.env"
fi
chmod +x "$REPO/hybrid_scanner/mac/"*.sh

# --------------------------------------------------------------------------- #
if [ "$TEST" = 1 ]; then
  step "Test scan on 3 tickers (checks internet access, notifications, report)"
  TEST_OUT="$HOME_DIR/reports/install-test"
  if (cd "$REPO" && MPLBACKEND=Agg "$REPO/.venv/bin/python" -m hybrid_scanner.main \
        --tickers AAPL MSFT NVDA --alert-window 20 --plot \
        --output-dir "$TEST_OUT" --report "$TEST_OUT/report.html" \
        --notify macos --alert-title "Hybrid scan (install test)") >"$HOME_DIR/logs/install-test.log" 2>&1; then
    ok "Test scan worked — opening the test report"
    open "$TEST_OUT/report.html" || true
    echo "  If no notification appeared: System Settings → Notifications → Script Editor → Allow."
  else
    fail "Test scan failed. Details: $HOME_DIR/logs/install-test.log
  Most common cause: no internet access to Yahoo Finance (query1.finance.yahoo.com)."
  fi
fi

# --------------------------------------------------------------------------- #
if [ "$SCHEDULE" = 1 ]; then
  step "Scheduling the scan: Monday–Friday at $(printf '%02d:%02d' "$SCAN_HOUR" "$SCAN_MINUTE") (this Mac's time)"
  mkdir -p "$HOME/Library/LaunchAgents"
  {
    cat <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$REPO/hybrid_scanner/mac/run_scan.sh</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>HYBRID_HOME</key><string>$HOME_DIR</string>
    <key>MPLBACKEND</key><string>Agg</string>
  </dict>
  <key>StartCalendarInterval</key>
  <array>
EOF
    for day in 1 2 3 4 5; do
      echo "    <dict><key>Weekday</key><integer>$day</integer><key>Hour</key><integer>$SCAN_HOUR</integer><key>Minute</key><integer>$SCAN_MINUTE</integer></dict>"
    done
    cat <<EOF
  </array>
  <key>StandardOutPath</key><string>$HOME_DIR/logs/launchd.log</string>
  <key>StandardErrorPath</key><string>$HOME_DIR/logs/launchd.log</string>
  <key>ProcessType</key><string>Background</string>
</dict>
</plist>
EOF
  } >"$PLIST"
  plutil -lint "$PLIST" >/dev/null || fail "Generated schedule file is invalid: $PLIST"
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$PLIST" || fail "Could not register the schedule with launchd."
  ok "Scheduled ($PLIST)"
  echo "  If the Mac is asleep at that time, the scan runs as soon as it wakes."
  echo "  If it is shut down, that day's scan is skipped."
fi

# --------------------------------------------------------------------------- #
step "Done"
cat <<EOF
  Reports:        $HOME_DIR/reports/<date>/report.html
  Latest report:  open "$HOME_DIR/latest-report.html"
  Settings:       $HOME_DIR/settings.env
  Run now:        $REPO/hybrid_scanner/mac/run_scan.sh
  Logs:           $HOME_DIR/logs/
  Remove:         $REPO/hybrid_scanner/mac/uninstall.sh
EOF
