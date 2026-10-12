# Run the hybrid scanner on your Mac

Every weekday evening after the US close, your Mac scans the S&P 500, saves a
report with the signals and their charts, and shows a notification. No
accounts, no cloud, and nothing to keep open.

Setup takes about 10 minutes, once.

---

## 1. Install Python (once)

macOS comes with Python 3.9, which is too old for the scanner.

1. Go to **https://www.python.org/downloads/macos/**.
2. Download the latest **Python 3.12** (or 3.13) **"macOS 64-bit universal2 installer"**.
3. Open the downloaded `.pkg` and click through the installer.

## 2. Download the scanner (once)

Open **Terminal** (press ⌘-Space, type *Terminal*, press Enter) and paste:

```bash
cd ~
git clone https://github.com/investocksgeneva/Investocksgeneva.git
```

> If macOS asks to install the **command line developer tools**, click
> *Install*, wait for it to finish, then paste the command again.

⚠️ Keep the folder in your **home folder** (`~/Investocksgeneva`). Do not put it
in Documents, Desktop, Downloads or iCloud. macOS blocks scheduled jobs from
reading those folders, so the evening scan would silently fail. The installer
checks this for you.

## 3. Install and schedule (once)

```bash
cd ~/Investocksgeneva
./hybrid_scanner/mac/install.sh
```

The installer:

1. **Checks Python.** It finds your Python 3.12 or 3.13.
2. **Installs packages.** It creates the scanner's own private environment and
   installs what it needs. This takes about a minute.
3. **Creates `~/HybridScanner`.** This holds your reports, logs and
   `settings.env`.
4. **Runs a test scan** on AAPL, MSFT and NVDA. It opens a test report in your
   browser and shows a test notification.
5. **Schedules the scan** for **Monday to Friday at 23:00** (your Mac's time).
   In Geneva that is an hour or more after the New York close, all year
   round.

> **No notification appeared?** Go to System Settings → Notifications →
> **Script Editor** and turn on *Allow notifications*. macOS shows scanner
> notifications under Script Editor's name.

Want a different time? Run the installer again with your time, for example
22:30:

```bash
SCAN_HOUR=22 SCAN_MINUTE=30 ./hybrid_scanner/mac/install.sh
```

---

## Shortcuts: no Terminal needed

Open your **HybridScanner** folder: in Finder press ⇧⌘H, then double-click
*HybridScanner*. It contains:

| Double-click | What it does |
|---|---|
| **Run scan now** | Scans the S&P 500 (about 2 minutes, with progress shown), then opens the report |
| **Open latest report** | Opens the most recent report in your browser |
| **Edit settings** | Opens your account size and risk settings in TextEdit |
| **Update scanner** | Downloads the latest version and reinstalls it |
| **HOW TO USE.txt** | A one-page cheat sheet with every command |

The first time you open each shortcut, macOS may ask *"Are you sure you want
to open it?"*. Click **Open**.

## Every day

* **After the scan,** a notification arrives, for example
  *"2 signal(s): PANW, APH — Watch: CRWD, JCI, NVDA"*.
* **To read the latest report,** run `open ~/HybridScanner/latest-report.html`,
  or open the `HybridScanner` folder in Finder (⇧⌘H takes you to your home
  folder).
* **Past reports** are in `~/HybridScanner/reports/<date>/`, each with
  `report.html`, `signals.csv` and the chart images. They are kept for 90
  days.
* **To scan right now,** run `~/Investocksgeneva/hybrid_scanner/mac/run_scan.sh`.

Each report shows:

* the **entry signals**, with entry, stop, target, position size and a chart
  for each;
* the **watch list**, meaning stocks with a valid pullback that haven't
  triggered yet;
* all **momentum candidates**.

**Scanning while the US market is open** (15:30–22:00 Geneva time) is safe.
The scanner ignores today's unfinished candle and uses the last completed day.
A hammer at 17:00 can look completely different by the close, so signals
are only ever based on finished candles.

**On US market holidays** there is no new data. The scan notices, stays
silent and writes nothing.

**If your Mac is asleep** at 23:00, the scan runs as soon as it wakes. If the
Mac is **shut down**, that day's scan is skipped.

## Your settings

Open `~/HybridScanner/settings.env` in TextEdit:

```bash
open -e ~/HybridScanner/settings.env
```

```bash
ACCOUNT_EQUITY=100000   # your account size, used for position sizing
RISK_PER_TRADE=0.01     # 1% of the account risked per trade
EXTRA_ARGS=""           # any other options, e.g. "--set risk.target_r_multiple=3"
```

Changes apply from the next scan. There is no need to reinstall.

## Updating to the latest version

```bash
cd ~/Investocksgeneva && git pull && ./hybrid_scanner/mac/install.sh
```

## Removing it

```bash
~/Investocksgeneva/hybrid_scanner/mac/uninstall.sh
```

This stops the schedule. Your reports and settings are kept, and the script
prints the commands to delete them as well.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| A *"Hybrid scan failed"* notification | Read the log it names, in `~/HybridScanner/logs/`. The most common cause is no internet at scan time. |
| No notification at all | System Settings → Notifications → Script Editor → Allow. |
| `No Python 3.11+ found` | Do step 1, then re-run the installer. |
| `privacy-protected folder` | Move the folder: `mv ~/Documents/Investocksgeneva ~/` and re-run. |
| You want clickable notifications that open the report | `brew install terminal-notifier` (needs [Homebrew](https://brew.sh)). The scanner uses it automatically when it is installed. |
| You want to check the schedule is active | `launchctl list \| grep hybridscanner` should print one line. |

The signals are research output, not investment advice. The levels are as of
the signal's bar, so check the live price and the chart before acting.
