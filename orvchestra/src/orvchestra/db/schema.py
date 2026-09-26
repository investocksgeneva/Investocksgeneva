"""The full SQLite schema, applied idempotently on every connection.

Most of this is still CREATE ... IF NOT EXISTS, a no-op against an existing
database. Phase 4 is the first time a column needed adding to a table that
might already hold real data (`tracks.rating`, `playlists.is_smart`,
`playlists.rules_json`), so `_ensure_column` below does the smallest thing
that could work: check `PRAGMA table_info` and `ALTER TABLE ... ADD COLUMN`
if it's missing. That's still short of a real numbered-migrations
framework (there's no way to *remove* or *rename* a column this way, and no
ordering across multiple such changes) -- fine for purely-additive nullable
columns, not fine once a change needs more than that. Replace this with a
proper migrations approach keyed off `schema_meta` before that day comes.

`albums` and `artists` are intentionally SQL views, not tables: at 300k
tracks a GROUP BY over an indexed column is still a few milliseconds, and a
view can never drift out of sync with `tracks` the way a materialized copy
maintained by hand could. Revisit only if profiling on the real library
shows it matters.
"""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 2

DDL = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS roots (
    id           INTEGER PRIMARY KEY,
    path         TEXT NOT NULL UNIQUE,
    label        TEXT,
    volume_uuid  TEXT,
    online       INTEGER NOT NULL DEFAULT 1,
    last_seen_at TEXT,
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS tracks (
    id       INTEGER PRIMARY KEY,
    root_id  INTEGER NOT NULL REFERENCES roots(id) ON DELETE CASCADE,
    rel_path TEXT NOT NULL,

    -- Identity used for incremental rescans: unchanged (size, mtime) means
    -- the file is skipped entirely, without ever being opened.
    size  INTEGER NOT NULL,
    mtime REAL NOT NULL,

    -- False while the file's root is unreachable (drive unplugged) or the
    -- file itself has vanished from a reachable root. Rows are never
    -- deleted on disappearance, only marked offline, so play history and
    -- playlist membership survive a temporarily missing drive.
    online INTEGER NOT NULL DEFAULT 1,

    duration_seconds REAL,
    codec            TEXT,
    sample_rate      INTEGER,
    bit_depth        INTEGER,
    channels         INTEGER,
    bitrate          INTEGER,

    title        TEXT,
    artist       TEXT,
    album_artist TEXT,
    album        TEXT,
    disc_number  INTEGER,
    disc_total   INTEGER,
    track_number INTEGER,
    track_total  INTEGER,
    year         INTEGER,
    genre        TEXT,
    compilation  INTEGER NOT NULL DEFAULT 0,

    musicbrainz_track_id  TEXT,
    musicbrainz_album_id  TEXT,
    musicbrainz_artist_id TEXT,

    replaygain_track_gain REAL,
    replaygain_track_peak REAL,
    replaygain_album_gain REAL,
    replaygain_album_peak REAL,

    has_embedded_art INTEGER NOT NULL DEFAULT 0,
    art_hash         TEXT REFERENCES artwork(hash),

    added_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    UNIQUE (root_id, rel_path)
);

CREATE INDEX IF NOT EXISTS idx_tracks_album  ON tracks(album_artist, album, disc_number, track_number);
CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks(artist);
CREATE INDEX IF NOT EXISTS idx_tracks_root   ON tracks(root_id);
CREATE INDEX IF NOT EXISTS idx_tracks_online ON tracks(online);
CREATE INDEX IF NOT EXISTS idx_tracks_added  ON tracks(added_at);

CREATE TABLE IF NOT EXISTS artwork (
    hash            TEXT PRIMARY KEY,
    thumb_300_path  TEXT,
    thumb_1000_path TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT,
    is_admin      INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS playlists (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER REFERENCES users(id),
    name        TEXT NOT NULL,
    description TEXT,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS playlist_items (
    id          INTEGER PRIMARY KEY,
    playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
    track_id    INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL,
    added_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- Internet radio stations the user has saved. Distinct from `tracks`: these
-- have no file on disk, no duration, nothing to scan -- just a name and a
-- stream URL, sourced from Radio Browser (radio-browser.info) or typed in
-- by hand.
CREATE TABLE IF NOT EXISTS radio_stations (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    stream_url TEXT NOT NULL,
    favicon    TEXT,
    tags       TEXT,
    country    TEXT,
    added_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS plays (
    id             INTEGER PRIMARY KEY,
    track_id       INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    user_id        INTEGER REFERENCES users(id),
    started_at     TEXT NOT NULL,
    seconds_played REAL NOT NULL DEFAULT 0,
    device         TEXT
);

-- Search (Phase 3 feature, wired up now so tag data is indexed from day one).
CREATE VIRTUAL TABLE IF NOT EXISTS tracks_fts USING fts5(
    title, artist, album_artist, album, genre,
    content='tracks',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS tracks_fts_ai AFTER INSERT ON tracks BEGIN
    INSERT INTO tracks_fts(rowid, title, artist, album_artist, album, genre)
    VALUES (new.id, new.title, new.artist, new.album_artist, new.album, new.genre);
END;

CREATE TRIGGER IF NOT EXISTS tracks_fts_ad AFTER DELETE ON tracks BEGIN
    INSERT INTO tracks_fts(tracks_fts, rowid, title, artist, album_artist, album, genre)
    VALUES ('delete', old.id, old.title, old.artist, old.album_artist, old.album, old.genre);
END;

CREATE TRIGGER IF NOT EXISTS tracks_fts_au AFTER UPDATE ON tracks BEGIN
    INSERT INTO tracks_fts(tracks_fts, rowid, title, artist, album_artist, album, genre)
    VALUES ('delete', old.id, old.title, old.artist, old.album_artist, old.album, old.genre);
    INSERT INTO tracks_fts(rowid, title, artist, album_artist, album, genre)
    VALUES (new.id, new.title, new.artist, new.album_artist, new.album, new.genre);
END;

-- Grouping rule: a compilation's "album artist" is always Various Artists,
-- even if the tag is missing or inconsistent per track, so a compilation
-- never gets split into one fake album per contributing artist. A
-- multi-disc album is one row here (COUNT/SUM across all its discs) because
-- it is grouped by (album_artist, album, year) rather than by disc.
CREATE VIEW IF NOT EXISTS v_albums AS
SELECT
    CASE WHEN compilation THEN 'Various Artists'
         ELSE COALESCE(NULLIF(album_artist, ''), NULLIF(artist, ''), 'Unknown Artist')
    END                                    AS album_artist,
    COALESCE(NULLIF(album, ''), 'Unknown Album') AS album,
    year,
    MAX(compilation)                       AS compilation,
    COUNT(*)                               AS track_count,
    COUNT(DISTINCT COALESCE(disc_number, 1)) AS disc_count,
    SUM(duration_seconds)                  AS total_duration_seconds,
    MIN(added_at)                          AS added_at,
    SUM(CASE WHEN online THEN 0 ELSE 1 END) AS offline_track_count
FROM tracks
GROUP BY 1, 2, 3;

CREATE VIEW IF NOT EXISTS v_artists AS
SELECT
    COALESCE(NULLIF(album_artist, ''), NULLIF(artist, ''), 'Unknown Artist') AS artist,
    COUNT(DISTINCT COALESCE(NULLIF(album, ''), 'Unknown Album')) AS album_count,
    COUNT(*) AS track_count
FROM tracks
WHERE compilation = 0
GROUP BY 1;

-- Picks one representative art_hash per album: whichever track sorts first
-- by (disc, track) among those that actually have art, per album. This is
-- the piece Phase 1's README explicitly deferred ("art_hash isn't in the
-- Phase-1 view") until something needed to actually serve album art.
CREATE VIEW IF NOT EXISTS v_album_art AS
SELECT album_artist, album, year, art_hash
FROM (
    SELECT
        CASE WHEN compilation THEN 'Various Artists'
             ELSE COALESCE(NULLIF(album_artist, ''), NULLIF(artist, ''), 'Unknown Artist')
        END AS album_artist,
        COALESCE(NULLIF(album, ''), 'Unknown Album') AS album,
        year,
        art_hash,
        ROW_NUMBER() OVER (
            PARTITION BY
                CASE WHEN compilation THEN 'Various Artists'
                     ELSE COALESCE(NULLIF(album_artist, ''), NULLIF(artist, ''), 'Unknown Artist')
                END,
                COALESCE(NULLIF(album, ''), 'Unknown Album'),
                year
            ORDER BY (art_hash IS NULL), COALESCE(disc_number, 1), COALESCE(track_number, 999999)
        ) AS rn
    FROM tracks
)
WHERE rn = 1;
"""


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, column_def: str) -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")


def apply_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(DDL)

    # Phase 4 additions to tables that predate it -- see the module
    # docstring for why this is a hand-rolled ALTER rather than DDL above.
    _ensure_column(conn, "tracks", "rating", "rating INTEGER")
    _ensure_column(conn, "playlists", "is_smart", "is_smart INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "playlists", "rules_json", "rules_json TEXT")
    _ensure_column(conn, "tracks", "lyrics", "lyrics TEXT")

    conn.execute(
        "INSERT INTO schema_meta(key, value) VALUES ('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()
