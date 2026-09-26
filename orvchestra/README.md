# Orvchestra

A private, streaming-style player for a local FLAC/lossless library, running
entirely on hardware you already own: your Mac as the server, a WiiM Amp Pro
(DLNA/UPnP renderer) as the hi-fi output, and your phone or laptop browser as
the remote. Zero subscriptions, zero cloud, your files never move.

This repository is built one phase at a time; see the project's phase plan
for the full roadmap (DLNA server, "Play on WiiM", listening history,
in-browser playback, family sharing). **This README currently documents
Phase 1: the library engine** — the scanner and SQLite database everything
else is built on.

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

## Data model (Phase 1 subset)

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

## What to check by hand after this phase

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
