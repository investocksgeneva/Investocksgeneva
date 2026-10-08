# Setting up Orvchestra on another machine

Orvchestra has no license lock-in or single-machine design — it's just your
own code plus a local SQLite database per install. You can run it on as many
Macs as you like (e.g. one at home, one at the office). **Each install is
completely independent**: its own library, its own play history, star
ratings, listening stats, smart playlists, and saved radio stations. Nothing
syncs between installs — think of it as two separate Orvchestras that happen
to share the same source code, not one app in two places.

## 1. Get the code

```bash
git clone <this repo's URL>
cd Investocksgeneva/orvchestra
```

## 2. Install prerequisites (if not already on that machine)

- Python 3.12+
- Node.js 20+ and npm
- [`uv`](https://docs.astral.sh/uv/): `curl -LsSf https://astral.sh/uv/install.sh | sh`

## 3. Install and build

```bash
uv sync --group dev
cd web && npm install && npm run build && cd ..
```

## 4. Copy your music over

Copy the actual music files to the new machine however you like (external
drive, AirDrop, network share). Keep each album's folder structure and tags
intact; the location on disk doesn't need to match any other machine's —
Orvchestra reads tags, not paths.

## 5. Point Orvchestra at it

```bash
uv run orvchestra roots add "/path/to/music/on/this/machine" --label "Office"
uv run orvchestra scan
uv run orvchestra stats   # sanity check the counts
```

## 6. Run it in the background automatically

```bash
scripts/install.sh
```

This installs the same launchd LaunchAgent (`com.orvchestra.serve`) used on
every other install — starts `orvchestra serve` at login, restarts it if it
ever crashes, logs to `~/Library/Application Support/Orvchestra/logs/`.

To restart it after pulling code changes:

```bash
launchctl kickstart -k gui/$(id -u)/com.orvchestra.serve
```

(Only needed for backend changes — `src/orvchestra/**`. A frontend-only
change just needs `cd web && npm run build` and a browser refresh; the
running service serves `web/dist` straight off disk.)

## 7. Open it

`http://<this machine's LAN IP>:8347` from a phone or laptop on the same
Wi-Fi. If there's a WiiM (or other DLNA renderer) on that network too,
"Play on WiiM" discovers it independently there — no configuration needed,
same as the first machine.

## Keeping multiple installs up to date

Each machine is its own `git clone` of the same repo. Pull + rebuild on
whichever one you changed:

```bash
git pull origin <branch>
cd web && npm run build   # if the frontend changed
# then, only for backend changes:
launchctl kickstart -k gui/$(id -u)/com.orvchestra.serve
```

There's no push from one machine to another — if you want a code change
(a new feature, a bug fix) on every install, you pull it on each one
separately.
