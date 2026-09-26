# Orvchestra

A private, streaming-style player for a local FLAC/lossless library, running
entirely on hardware you already own: your Mac as the server, a WiiM Amp Pro
(DLNA/UPnP renderer) as the hi-fi output, and your phone or laptop browser as
the remote. Zero subscriptions, zero cloud, your files never move.

This repository is built one phase at a time; see the project's phase plan
for the full roadmap ("Play on WiiM" control, listening history, in-browser
playback, family sharing). **This README currently documents Phase 1 (the
library engine) and Phase 2 (the DLNA MediaServer)** — between them, your
library is now indexed and playable gaplessly on the WiiM Amp Pro, with no
web app or "push to WiiM" control yet (that's Phase 3).

## Requirements

- Python 3.12+
- macOS 14+ (developed on Intel x86_64; the code avoids any
  Apple-Silicon-only or macOS-only API so it can move to a Linux always-on
  box later unchanged — the one deliberate exception is the dataless-file
  and volume-UUID checks, which detect their platform and no-op on Linux)
- [`uv`](https://docs.astral.sh/uv/) (recommended) or `pip`

## Install

```bash
cd orvchestra
uv sync --group dev   # installs orvchestra + dev/test dependencies
```

Without `uv`:

```bash
cd orvchestra
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"   # (or: pip install -e . ; pip install pytest soundfile numpy lameenc)
```

## Where Orvchestra keeps its data

Everything Orvchestra writes for itself — the SQLite database, cached
artwork thumbnails, logs — lives under:

- macOS: `~/Library/Application Support/Orvchestra/`
- Linux (for the eventual always-on box): `~/.local/share/orvchestra/`

Set `ORVCHESTRA_DATA_DIR` to point somewhere else (this is how the test
suite isolates itself from your real app-data directory — every test runs
against a throwaway temp directory, never your actual library database).

**Your music files are never modified, moved, renamed, or deleted.** The
scanner only ever calls `stat()` and opens files read-only to read tags.

## CLI usage

```bash
# Tell Orvchestra about a folder (or external drive) to index.
uv run orvchestra roots add "/Volumes/Music/FLAC" --label "External SSD"
uv run orvchestra roots list

# Scan all configured roots (or just one with --root).
uv run orvchestra scan

# See what's in the library.
uv run orvchestra stats
```

Re-running `orvchestra scan` on an unchanged library is fast: a file whose
`(size, mtime)` still matches the database is skipped without being opened
at all, so a rescan of an untouched 1 TB library is dominated by directory
traversal, not tag parsing.

### What a scan does, precisely

1. For each configured root, first checks whether its path is currently
   reachable. If not (external drive unplugged), the root and every one of
   its tracks are marked `offline` — never deleted — and the scan moves on
   to the next root. Plugging the drive back in and re-scanning brings
   everything back `online` automatically, matched back up by relative
   path.
2. Walks the root, skipping hidden files/folders (anything starting with
   `.`, which also catches macOS's `._` AppleDouble sidecar files) and
   known junk folders (`.Trashes`, `System Volume Information`, etc.).
3. Skips cloud-only ("dataless") placeholder files outright — Orvchestra
   will never trigger an iCloud download just to scan your library.
4. For each remaining audio file (`.flac`, `.m4a`/ALAC, `.mp3`, `.wav`,
   `.dsf`/`.dff`), compares `(size, mtime)` against what's recorded. If it
   matches, the file is left alone. Otherwise its tags are read with
   `mutagen` and its row is inserted or updated.
5. Cover art is resolved embedded-first, then `cover.jpg`/`folder.jpg` in
   the same folder; art is content-hashed so identical artwork (the common
   case for every track on an album) is only thumbnailed once, into
   300px/1000px JPEGs cached under the app-data directory.
6. Any track previously in the database but no longer found on disk (and
   whose root *is* reachable — a genuinely deleted or moved file) is marked
   `offline`, never removed, so play history and playlists survive.

## Phase 2: the DLNA MediaServer

```bash
uv run orvchestra serve
```

This starts two things in one process, one asyncio event loop:

1. **The DLNA/UPnP control-plane** (`orvchestra.dlna`), on port 8200 by
   default: SSDP advertisement and search-response so the WiiM Home app
   discovers "Orvchestra (MacBook)" automatically, the device/service
   description XML, and the ContentDirectory `Browse`/`Search` and
   ConnectionManager SOAP actions. This is built on
   `async_upnp_client.server` (`UpnpServer`/`UpnpServerDevice`/
   `UpnpServerService`) rather than hand-rolled SOAP/SSDP parsing — the
   library already generates correct device-description and SCPD XML by
   reflecting over declared actions and state variables, and its own source
   comments show it's specifically been hardened against WiiM/Linkplay
   quirks (e.g. some Linkplay firmwares put `<upnp:class>` in an
   unexpected place in DIDL-Lite responses; the library already tolerates
   that when parsing, which matters if a later phase adds a control point
   that talks back to other renderers).
2. **The media/artwork HTTP endpoint** (`orvchestra.media`), on port 8347 by
   default, via FastAPI/uvicorn: `GET /track/{id}.{ext}` streams the
   original file byte-for-byte with HTTP Range/206 support (Starlette's
   `FileResponse` handles this natively — no hand-written byte-range
   parsing), and `GET /art/{hash}/{size}.jpg` serves the cached thumbnails.
   Both routes answer `HEAD` too, since DLNA renderers commonly probe
   headers before the real `GET`.

DIDL-Lite `<res>` elements point at the media endpoint's URLs; the DLNA
service never serves file bytes itself. **Why two ports instead of one:**
`async_upnp_client`'s server framework is built on aiohttp, which can't share
a listening socket with FastAPI/uvicorn's ASGI server — two genuinely
different HTTP stacks can't bind the same port. Rather than reimplement
SSDP/SOAP/SCPD by hand to avoid that (exactly the kind of fragile,
easy-to-get-subtly-wrong protocol code the phase plan says to avoid unless
no suitable library exists), Orvchestra runs both servers in the one
`orvchestra serve` process and one asyncio loop — still a single background
service, just listening on two ports. Phase 3's browser-facing web app and
JSON API are planned for the FastAPI side, since that's the piece built to
grow.

### The browse tree

```
Artists → (artist) → (album) → (track)
Albums (A–Z) → (album) → (track)
Genres → (genre) → (track)
Years → (year) → (album) → (track)
Recently Added → (album) → (track)
Playlists → (empty until Phase 4)
```

Every ObjectID is `<kind>:<url-safe-base64>`, so artist/album/genre names
with slashes, unicode, or anything else tag text can contain round-trip
safely through SOAP/XML (`src/orvchestra/dlna/ids.py`). Album containers use
the same `(album_artist, album, year)` key as `v_albums`/`v_album_art`, so
compilations correctly appear as one "Various Artists" album regardless of
each track's own artist tag, and multi-disc albums appear as one container
with all discs' tracks inside, ordered by `(disc_number, track_number)`.

`Search` is implemented as a thin alias over `Browse` (it ignores
`SearchCriteria` and just lists `ContainerID`'s children) rather than real
text search — nothing in Phase 2 needs it, and real search belongs on the
FTS5 index Phase 3's web app will actually use. `Filter` and `SortCriteria`
are accepted (required by the ContentDirectory:1 spec) but ignored: full
properties are always returned, and results are already sorted sensibly
server-side.

### Verifying this by hand

1. `uv run orvchestra serve` (defaults: DLNA on `:8200`, media on `:8347`).
   Watch for a line like
   `DLNA MediaServer listening at http://192.168.1.x:8200/upnp/device.xml`
   — that's the address the WiiM needs to be able to reach, i.e. same LAN /
   Wi-Fi as the WiiM Amp Pro, not a VPN or guest network.
2. Open the WiiM Home app → the source picker that lists DLNA/UPnP media
   servers on the network → "Orvchestra (MacBook)" should appear within a
   few seconds (SSDP advertisements repeat periodically, and WiiM Home also
   sends its own M-SEARCH on open).
3. Browse into Artists/Albums and play a 24-bit/96kHz FLAC album — it
   should start promptly and play through to the next track with no gap.
   The `<upnp:originalTrackNumber>`/gapless behavior comes from the WiiM's
   own DLNA client sequencing `Browse` results, not anything Orvchestra
   does explicitly.
4. `curl http://<mac-ip>:8200/upnp/device.xml` from another machine on the
   LAN as a quick reachability check if the WiiM doesn't see it — a
   `friendlyName` of "Orvchestra (MacBook)" confirms the description is
   being served correctly; if the curl itself fails, it's a network/firewall
   issue, not an Orvchestra one (macOS's firewall prompt for incoming
   connections is the most likely culprit the first time this runs).

## Data model

The full schema (`src/orvchestra/db/schema.py`) is created on first
connection, WAL-mode SQLite with an FTS5 index over track metadata for the
search screen coming in Phase 3. `albums` and `artists` are SQL views
(`v_albums`, `v_artists`) grouped from `tracks`, not separately maintained
tables — that keeps them impossible to desync, and a `GROUP BY` over an
indexed column stays fast well past 300k tracks. Compilations are grouped
under "Various Artists" regardless of what each track's own artist tag
says; multi-disc albums are one row (their per-disc tracks all share the
same `(album_artist, album, year)` grouping key).

`playlists`, `playlist_items`, `plays`, and `users` tables exist in the
schema now (per the target data model) but are unused until their
respective phases.

## Running the tests

```bash
uv run pytest
```

The test suite generates its own tiny FLAC/MP3/WAV fixtures (real, valid
audio files with real tags, using `soundfile` and `lameenc` — not
hand-crafted byte stubs) under a temp directory per test run; it never
touches real music. Coverage includes:

- tag extraction correctness (title/artist/album/track/disc/year/genre/
  ReplayGain/MusicBrainz IDs) for FLAC, MP3, and WAV
- compilation and multi-disc album grouping via `v_albums`
- embedded vs. sidecar artwork resolution and thumbnail generation
- incremental rescans: unchanged files are skipped, changed files are
  re-read, deleted files go offline without being deleted from the DB
- the drive-unplugged / drive-reconnected lifecycle
- **a byte-for-byte and mtime-for-mtime proof that scanning never mutates
  a music file**, run before and after both a full and an incremental scan
- the CLI end-to-end (`roots add` → `scan` → `stats`)
- the ContentDirectory browse tree (Artists/Albums/Genres/Years/Recent/
  Playlists) built directly against a scanned library, including
  compilation and multi-disc grouping in DIDL-Lite form
- a real socket-level test: `DlnaMediaServer` started for real, a genuine
  SOAP `Browse` request over HTTP, an unknown-ObjectID request correctly
  producing a `701` SOAP fault — this is what caught a real bug during
  development (see the DLNA trade-offs below) that a pure-logic unit test
  could not have
- the media/artwork FastAPI endpoints: full-file streaming byte-identical
  to the source file, `Range` requests, `HEAD`, offline/missing-file
  handling, unknown track/art 404s

## What to check by hand after Phase 1

1. `uv run orvchestra roots add ~/Music` against a real folder with a mix
   of FLAC/MP3/ALAC files, then `uv run orvchestra scan` and `uv run
   orvchestra stats` — sanity-check the counts and hi-res share against
   what you know is in there.
2. Unplug (or rename) an external drive you've added as a root, run
   `orvchestra scan` again, and confirm it reports the root as
   unreachable rather than erroring or hanging.
3. Spot-check that `find ~/Music -newer <timestamp-before-scan>` returns
   nothing after a scan — i.e. nothing in the music folder was touched.

## Trade-offs and open questions carried into later phases

- **No migration framework yet.** The schema is applied idempotently
  (`CREATE ... IF NOT EXISTS`), which is fine for a single-developer v1 but
  will need replacing with numbered migrations before the schema can change
  under a library that already has real data in it.
- **`v_albums.art_hash` isn't in the Phase-1 view.** Deciding "which
  track's art represents the album" (first track by disc/track number,
  vs. most common hash) is a Phase 3 concern once art is actually being
  served to a UI; the column was left out rather than guessed at.
- **Volume UUID is captured but not yet load-bearing.** `roots.volume_uuid`
  is recorded on `roots add` (macOS only, via `diskutil`) for a future
  "a different drive got mounted at this same path" warning, but Phase 1's
  online/offline logic is purely path-reachability-based. Revisit once
  there's real multi-drive hardware to test swap detection against.
- **Albums are grouped by `(album_artist, album, year)`, per the spec's data
  model** — which means a folder-album whose tracks disagree on the `DATE`
  tag (one track untagged, one saying `2022`) will fragment into two rows in
  `v_albums`. Well-tagged libraries (Picard, foobar2000) don't hit this in
  practice; a messy one will need its tags cleaned up, or this grouping
  key revisited, before Phase 3's Album screen looks right.
- **DSD and ALAC support is best-effort.** `.dsf`/`.dff` and `.m4a` (ALAC)
  are recognized and their tag-extraction code paths exist, but there's no
  generated-fixture test for either — no pure-Python DSD or ALAC encoder was
  available to build one without a system `ffmpeg` (deliberately not
  installed in the dev sandbox this was built in). Worth a manual check
  against real files of both formats before relying on them; FLAC/MP3/WAV
  are fixture-tested against real codec bitstreams and are solid.
- **Genre and ReplayGain tag coverage is strongest for FLAC/Vorbis
  comments** (the format the library is overwhelmingly in); MP3/ID3 and
  MP4/ALAC extraction covers the common taggers (Picard, foobar2000, iTunes)
  but hasn't been exhaustively tested against every tagger's quirks.
- **DLNA runs on two ports in one process** (control-plane on aiohttp via
  `async_upnp_client`, media on FastAPI/uvicorn) rather than one — see
  "Phase 2: the DLNA MediaServer" above for why. If this ever becomes
  annoying (firewall rules, port management), the alternative is
  reimplementing SSDP/SOAP/SCPD by hand purely to get everything under one
  ASGI app, which trades a minor operational inconvenience for a much
  larger amount of fragile protocol code — not worth it unless it actually
  causes a problem.
- **Genres and time-based seeking are simplified.** `Genres` groups by the
  exact raw tag string, not by splitting multi-genre tags like
  `"Rock; Pop"` into two browsable genres — most libraries tag one genre
  per track, and doing this properly wants the FTS index Phase 3 builds
  anyway. Every `<res>` only advertises `DLNA.ORG_OP=01` (byte-range seek);
  time-based seeking within a track would need parsing each codec's frame
  layout to map a timestamp to a byte offset, which no phase currently
  needs (WiiM's own transport position/seek during playback is
  Phase 3's AVTransport control problem, not a property of the file itself).
- **`Search` doesn't search.** It's a required ContentDirectory:1 action, so
  it's implemented as an alias for `Browse` on the given container
  (ignoring the actual search text) rather than left out or erroring —
  matching what several minimal real-world DLNA servers do. WiiM Home's own
  UI doesn't appear to use `Search` for basic library navigation, only
  `Browse`.
- **A real reflection-based framework bug only showed up under a live
  socket, not in pure-logic tests.** `async_upnp_client.server` validates
  that each action method's Python type annotations exactly match its
  declared UPnP argument types, but only when the service class is actually
  instantiated — and `from __future__ import annotations` (used elsewhere
  in this codebase) turns annotations into strings, which fails that check
  silently until you try to start the server. `content_directory.py` and
  `connection_manager.py` deliberately don't use that import for this
  reason, with a test (`test_dlna_server_integration.py`) that starts a
  real server precisely to catch a regression here.
