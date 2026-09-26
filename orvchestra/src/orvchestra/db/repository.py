"""All SQL for roots/tracks/artwork lives here, so the scanner deals only in
plain Python values and never writes a query itself."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from orvchestra.models import TrackTags

_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


def iso_now_minus_days(days: float) -> str:
    """An ISO8601 UTC timestamp in the exact `YYYY-MM-DDTHH:MM:SS.mmmZ` shape
    `_NOW` produces, so Python-computed cutoffs and SQLite-computed
    timestamps compare correctly as plain strings -- no SQLite date/time
    functions or timezone handling needed anywhere else in this module."""
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


# --- roots -------------------------------------------------------------

def add_root(conn: sqlite3.Connection, path: str, label: str | None, volume_uuid: str | None) -> int:
    cur = conn.execute(
        "INSERT INTO roots (path, label, volume_uuid, online, last_seen_at) "
        f"VALUES (?, ?, ?, 1, {_NOW})",
        (path, label, volume_uuid),
    )
    conn.commit()
    return cur.lastrowid


def remove_root(conn: sqlite3.Connection, path: str) -> bool:
    cur = conn.execute("DELETE FROM roots WHERE path = ?", (path,))
    conn.commit()
    return cur.rowcount > 0


def list_roots(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM roots ORDER BY id").fetchall()


def get_root_by_path(conn: sqlite3.Connection, path: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM roots WHERE path = ?", (path,)).fetchone()


def mark_root_online(conn: sqlite3.Connection, root_id: int) -> None:
    conn.execute(f"UPDATE roots SET online = 1, last_seen_at = {_NOW} WHERE id = ?", (root_id,))


def mark_root_offline(conn: sqlite3.Connection, root_id: int) -> None:
    conn.execute("UPDATE roots SET online = 0 WHERE id = ?", (root_id,))
    conn.execute("UPDATE tracks SET online = 0 WHERE root_id = ? AND online = 1", (root_id,))


# --- tracks --------------------------------------------------------------

def load_existing_tracks(conn: sqlite3.Connection, root_id: int) -> dict[str, sqlite3.Row]:
    rows = conn.execute(
        "SELECT id, rel_path, size, mtime, online FROM tracks WHERE root_id = ?",
        (root_id,),
    ).fetchall()
    return {row["rel_path"]: row for row in rows}


def insert_track(
    conn: sqlite3.Connection,
    root_id: int,
    rel_path: str,
    size: int,
    mtime: float,
    tags: TrackTags,
    art_hash: str | None,
    has_embedded_art: bool,
) -> int:
    cur = conn.execute(
        f"""
        INSERT INTO tracks (
            root_id, rel_path, size, mtime, online,
            duration_seconds, codec, sample_rate, bit_depth, channels, bitrate,
            title, artist, album_artist, album, disc_number, disc_total,
            track_number, track_total, year, genre, compilation,
            musicbrainz_track_id, musicbrainz_album_id, musicbrainz_artist_id,
            replaygain_track_gain, replaygain_track_peak,
            replaygain_album_gain, replaygain_album_peak,
            has_embedded_art, art_hash, lyrics, added_at, updated_at
        ) VALUES (
            ?, ?, ?, ?, 1,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?,
            ?, ?,
            ?, ?, ?, {_NOW}, {_NOW}
        )
        """,
        (
            root_id, rel_path, size, mtime,
            tags.duration_seconds, tags.codec, tags.sample_rate, tags.bit_depth,
            tags.channels, tags.bitrate,
            tags.title, tags.artist, tags.album_artist, tags.album,
            tags.disc_number, tags.disc_total, tags.track_number, tags.track_total,
            tags.year, tags.genre, int(tags.compilation),
            tags.musicbrainz_track_id, tags.musicbrainz_album_id, tags.musicbrainz_artist_id,
            tags.replaygain_track_gain, tags.replaygain_track_peak,
            tags.replaygain_album_gain, tags.replaygain_album_peak,
            int(has_embedded_art), art_hash, tags.lyrics,
        ),
    )
    return cur.lastrowid


def update_track(
    conn: sqlite3.Connection,
    track_id: int,
    size: int,
    mtime: float,
    tags: TrackTags,
    art_hash: str | None,
    has_embedded_art: bool,
) -> None:
    conn.execute(
        f"""
        UPDATE tracks SET
            size = ?, mtime = ?, online = 1,
            duration_seconds = ?, codec = ?, sample_rate = ?, bit_depth = ?,
            channels = ?, bitrate = ?,
            title = ?, artist = ?, album_artist = ?, album = ?,
            disc_number = ?, disc_total = ?, track_number = ?, track_total = ?,
            year = ?, genre = ?, compilation = ?,
            musicbrainz_track_id = ?, musicbrainz_album_id = ?, musicbrainz_artist_id = ?,
            replaygain_track_gain = ?, replaygain_track_peak = ?,
            replaygain_album_gain = ?, replaygain_album_peak = ?,
            has_embedded_art = ?, art_hash = ?, lyrics = ?, updated_at = {_NOW}
        WHERE id = ?
        """,
        (
            size, mtime,
            tags.duration_seconds, tags.codec, tags.sample_rate, tags.bit_depth,
            tags.channels, tags.bitrate,
            tags.title, tags.artist, tags.album_artist, tags.album,
            tags.disc_number, tags.disc_total, tags.track_number, tags.track_total,
            tags.year, tags.genre, int(tags.compilation),
            tags.musicbrainz_track_id, tags.musicbrainz_album_id, tags.musicbrainz_artist_id,
            tags.replaygain_track_gain, tags.replaygain_track_peak,
            tags.replaygain_album_gain, tags.replaygain_album_peak,
            int(has_embedded_art), art_hash, tags.lyrics,
            track_id,
        ),
    )


def mark_tracks_online_unchanged(conn: sqlite3.Connection, track_ids: Iterable[int]) -> None:
    """Flip previously-offline tracks back online without touching their tags.

    Used on the fast path where (size, mtime) match what's on disk, so we
    never re-open the file, but a track that was offline (e.g. its drive was
    unplugged) needs its online flag restored now that the file is visible
    again.
    """
    ids = list(track_ids)
    if not ids:
        return
    conn.executemany(f"UPDATE tracks SET online = 1, updated_at = {_NOW} WHERE id = ?", [(i,) for i in ids])


def mark_tracks_offline(conn: sqlite3.Connection, track_ids: Iterable[int]) -> None:
    ids = list(track_ids)
    if not ids:
        return
    conn.executemany("UPDATE tracks SET online = 0 WHERE id = ?", [(i,) for i in ids])


# --- system update id (DLNA ContentDirectory change notification) -------

def get_system_update_id(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT value FROM schema_meta WHERE key = 'system_update_id'").fetchone()
    return int(row["value"]) if row else 0


def bump_system_update_id(conn: sqlite3.Connection) -> int:
    new_id = get_system_update_id(conn) + 1
    conn.execute(
        "INSERT INTO schema_meta(key, value) VALUES ('system_update_id', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(new_id),),
    )
    return new_id


def get_or_create_device_udn(conn: sqlite3.Connection) -> str:
    """A UDN that stays stable across restarts, so DLNA control points and the
    WiiM app don't see a "new" device (and re-favorite it) every time
    Orvchestra starts."""
    row = conn.execute("SELECT value FROM schema_meta WHERE key = 'device_udn'").fetchone()
    if row:
        return row["value"]
    udn = f"uuid:{uuid.uuid4()}"
    conn.execute("INSERT INTO schema_meta(key, value) VALUES ('device_udn', ?)", (udn,))
    conn.commit()
    return udn


# --- browsing (DLNA ContentDirectory, and later the web app) -------------

def list_artists(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM v_artists ORDER BY artist COLLATE NOCASE").fetchall()


def get_artist(conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM v_artists WHERE artist = ?", (name,)).fetchone()


def list_albums(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM v_albums ORDER BY album COLLATE NOCASE, year").fetchall()


def list_albums_by_artist(conn: sqlite3.Connection, artist: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM v_albums WHERE album_artist = ? ORDER BY year, album COLLATE NOCASE", (artist,)
    ).fetchall()


def get_album(conn: sqlite3.Connection, album_artist: str, album: str, year: int | None) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM v_albums WHERE album_artist = ? AND album = ? AND year IS ?", (album_artist, album, year)
    ).fetchone()


def list_albums_for_year(conn: sqlite3.Connection, year: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM v_albums WHERE year = ? ORDER BY album_artist COLLATE NOCASE, album COLLATE NOCASE", (year,)
    ).fetchall()


def list_recent_albums(conn: sqlite3.Connection, limit: int = 100) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM v_albums ORDER BY added_at DESC LIMIT ?", (limit,)).fetchall()


def list_years(conn: sqlite3.Connection) -> list[int]:
    rows = conn.execute(
        "SELECT DISTINCT year FROM tracks WHERE year IS NOT NULL ORDER BY year DESC"
    ).fetchall()
    return [row["year"] for row in rows]


def list_genres(conn: sqlite3.Connection) -> list[str]:
    # One row per distinct raw genre *string* as tagged (not split on "; "
    # for multi-genre tracks) -- see README for why that's a Phase 2
    # simplification rather than a real normalized genre list.
    rows = conn.execute(
        "SELECT DISTINCT genre FROM tracks WHERE genre IS NOT NULL AND genre != '' ORDER BY genre COLLATE NOCASE"
    ).fetchall()
    return [row["genre"] for row in rows]


def list_tracks_for_album(
    conn: sqlite3.Connection, album_artist: str, album: str, year: int | None
) -> list[sqlite3.Row]:
    compilation_artist = album_artist == "Various Artists"
    if compilation_artist:
        # A compilation's per-track album_artist tag is whatever the
        # original tagger wrote (often the track's own artist), not
        # "Various Artists" -- v_albums only renames it for display. Match
        # on the album/year/compilation flag instead of album_artist here.
        query = (
            "SELECT * FROM tracks WHERE compilation = 1 "
            "AND COALESCE(NULLIF(album, ''), 'Unknown Album') = ? AND year IS ? "
            "ORDER BY COALESCE(disc_number, 1), COALESCE(track_number, 999999), rel_path"
        )
        return conn.execute(query, (album, year)).fetchall()

    query = (
        "SELECT * FROM tracks WHERE compilation = 0 "
        "AND COALESCE(NULLIF(album_artist, ''), NULLIF(artist, ''), 'Unknown Artist') = ? "
        "AND COALESCE(NULLIF(album, ''), 'Unknown Album') = ? AND year IS ? "
        "ORDER BY COALESCE(disc_number, 1), COALESCE(track_number, 999999), rel_path"
    )
    return conn.execute(query, (album_artist, album, year)).fetchall()


def list_tracks_for_genre(conn: sqlite3.Connection, genre: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM tracks WHERE genre = ? ORDER BY artist COLLATE NOCASE, album COLLATE NOCASE, "
        "COALESCE(disc_number, 1), COALESCE(track_number, 999999), rel_path",
        (genre,),
    ).fetchall()


def get_track(conn: sqlite3.Connection, track_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT tracks.*, roots.path AS root_path, roots.online AS root_online
        FROM tracks JOIN roots ON roots.id = tracks.root_id
        WHERE tracks.id = ?
        """,
        (track_id,),
    ).fetchone()


def get_album_art_hash(conn: sqlite3.Connection, album_artist: str, album: str, year: int | None) -> str | None:
    row = conn.execute(
        "SELECT art_hash FROM v_album_art WHERE album_artist = ? AND album = ? AND year IS ?",
        (album_artist, album, year),
    ).fetchone()
    return row["art_hash"] if row else None


def list_playlists(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM playlists ORDER BY name COLLATE NOCASE").fetchall()


def get_artwork(conn: sqlite3.Connection, art_hash: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM artwork WHERE hash = ?", (art_hash,)).fetchone()


# --- search ----------------------------------------------------------------
#
# Prefix matching via FTS5 gives instant, as-you-type results, but it is not
# typo-tolerant (a genuine misspelling like "beetles" won't find "Beatles").
# Real fuzzy matching would want a trigram index or an edit-distance rerank
# on top of this; not built here since it's a real chunk of extra work for a
# personal library where you mostly know what you're typing. Revisit if it
# turns out to matter in practice.

def _fts_prefix_query(text: str) -> str | None:
    tokens = [t.replace('"', '""') for t in text.strip().split() if t]
    if not tokens:
        return None
    return " ".join(f'"{t}"*' for t in tokens)


def search_tracks(conn: sqlite3.Connection, query: str, limit: int = 50) -> list[sqlite3.Row]:
    match = _fts_prefix_query(query)
    if match is None:
        return []
    return conn.execute(
        """
        SELECT tracks.* FROM tracks_fts
        JOIN tracks ON tracks.id = tracks_fts.rowid
        WHERE tracks_fts MATCH ?
        ORDER BY bm25(tracks_fts)
        LIMIT ?
        """,
        (match, limit),
    ).fetchall()


def _like_pattern(text: str) -> str:
    escaped = text.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def search_artists(conn: sqlite3.Connection, query: str, limit: int = 20) -> list[sqlite3.Row]:
    pattern = _like_pattern(query)
    return conn.execute(
        "SELECT * FROM v_artists WHERE artist LIKE ? ESCAPE '\\' COLLATE NOCASE ORDER BY artist LIMIT ?",
        (pattern, limit),
    ).fetchall()


def search_albums(conn: sqlite3.Connection, query: str, limit: int = 20) -> list[sqlite3.Row]:
    pattern = _like_pattern(query)
    return conn.execute(
        "SELECT * FROM v_albums WHERE (album LIKE ? ESCAPE '\\' OR album_artist LIKE ? ESCAPE '\\') COLLATE NOCASE "
        "ORDER BY album LIMIT ?",
        (pattern, pattern, limit),
    ).fetchall()


def library_stats(conn: sqlite3.Connection) -> dict:
    total = conn.execute("SELECT COUNT(*) AS n FROM tracks").fetchone()["n"]
    online = conn.execute("SELECT COUNT(*) AS n FROM tracks WHERE online = 1").fetchone()["n"]
    by_codec = conn.execute(
        "SELECT COALESCE(codec, 'unknown') AS codec, COUNT(*) AS n FROM tracks GROUP BY codec ORDER BY n DESC"
    ).fetchall()
    hires = conn.execute(
        "SELECT COUNT(*) AS n FROM tracks WHERE bit_depth > 16 OR sample_rate > 44100"
    ).fetchone()["n"]
    total_duration = conn.execute(
        "SELECT COALESCE(SUM(duration_seconds), 0) AS s FROM tracks WHERE online = 1"
    ).fetchone()["s"]
    total_size = conn.execute("SELECT COALESCE(SUM(size), 0) AS s FROM tracks").fetchone()["s"]
    albums = conn.execute("SELECT COUNT(*) AS n FROM v_albums").fetchone()["n"]
    artists = conn.execute("SELECT COUNT(*) AS n FROM v_artists").fetchone()["n"]
    return {
        "total_tracks": total,
        "online_tracks": online,
        "offline_tracks": total - online,
        "albums": albums,
        "artists": artists,
        "by_codec": {row["codec"]: row["n"] for row in by_codec},
        "hires_tracks": hires,
        "hires_share": (hires / total) if total else 0.0,
        "total_duration_seconds": total_duration,
        "total_size_bytes": total_size,
    }


# --- listening history (plays) ---------------------------------------------
#
# A play is recorded once by PlaybackService (see playback/service.py) when
# a track has been listened to past the 50%-or-4-minutes threshold; this
# module only stores what it's given and answers queries over it.

def record_play(conn: sqlite3.Connection, track_id: int, started_at: str, seconds_played: float, device: str) -> None:
    conn.execute(
        "INSERT INTO plays (track_id, user_id, started_at, seconds_played, device) VALUES (?, NULL, ?, ?, ?)",
        (track_id, started_at, seconds_played, device),
    )
    conn.commit()


# Two different "who does this belong to" rules, used for different stats:
# album grouping treats a compilation as "Various Artists" (matching
# v_albums, so a compilation is one browsable album, not one per
# contributor); artist-attribution stats care about who you actually
# listened to, so a compilation track counts for its own (real) artist.
_ALBUM_GROUP_ARTIST_EXPR = (
    "CASE WHEN tracks.compilation THEN 'Various Artists' "
    "ELSE COALESCE(NULLIF(tracks.album_artist, ''), NULLIF(tracks.artist, ''), 'Unknown Artist') END"
)
_ALBUM_GROUP_ALBUM_EXPR = "COALESCE(NULLIF(tracks.album, ''), 'Unknown Album')"
_ARTIST_ATTRIBUTION_EXPR = "COALESCE(NULLIF(tracks.artist, ''), NULLIF(tracks.album_artist, ''), 'Unknown Artist')"


def _period_where(since_iso: str | None, until_iso: str | None, params: list[Any]) -> str:
    clauses = []
    if since_iso is not None:
        clauses.append("plays.started_at >= ?")
        params.append(since_iso)
    if until_iso is not None:
        clauses.append("plays.started_at < ?")
        params.append(until_iso)
    return f" WHERE {' AND '.join(clauses)}" if clauses else ""


def top_tracks(
    conn: sqlite3.Connection, since_iso: str | None, until_iso: str | None = None, limit: int = 20
) -> list[sqlite3.Row]:
    params: list[Any] = []
    query = (
        "SELECT tracks.*, COUNT(*) AS play_count, SUM(plays.seconds_played) AS total_seconds_played "
        "FROM plays JOIN tracks ON tracks.id = plays.track_id"
    )
    query += _period_where(since_iso, until_iso, params)
    query += " GROUP BY tracks.id ORDER BY play_count DESC, total_seconds_played DESC LIMIT ?"
    params.append(limit)
    return conn.execute(query, params).fetchall()


def top_artists(
    conn: sqlite3.Connection, since_iso: str | None, until_iso: str | None = None, limit: int = 20
) -> list[sqlite3.Row]:
    params: list[Any] = []
    query = f"SELECT {_ARTIST_ATTRIBUTION_EXPR} AS artist, COUNT(*) AS play_count FROM plays JOIN tracks ON tracks.id = plays.track_id"
    query += _period_where(since_iso, until_iso, params)
    query += " GROUP BY artist ORDER BY play_count DESC LIMIT ?"
    params.append(limit)
    return conn.execute(query, params).fetchall()


def top_albums(
    conn: sqlite3.Connection, since_iso: str | None, until_iso: str | None = None, limit: int = 20
) -> list[sqlite3.Row]:
    params: list[Any] = []
    query = (
        f"SELECT {_ALBUM_GROUP_ARTIST_EXPR} AS album_artist, {_ALBUM_GROUP_ALBUM_EXPR} AS album, tracks.year AS year, "
        "COUNT(*) AS play_count FROM plays JOIN tracks ON tracks.id = plays.track_id"
    )
    query += _period_where(since_iso, until_iso, params)
    query += " GROUP BY album_artist, album, year ORDER BY play_count DESC LIMIT ?"
    params.append(limit)
    return conn.execute(query, params).fetchall()


def listening_summary(conn: sqlite3.Connection, since_iso: str | None, until_iso: str | None = None) -> dict[str, Any]:
    params: list[Any] = []
    query = "SELECT COUNT(*) AS play_count, COALESCE(SUM(seconds_played), 0) AS total_seconds FROM plays"
    query += _period_where(since_iso, until_iso, params)
    row = conn.execute(query, params).fetchone()
    return {"play_count": row["play_count"], "total_seconds": row["total_seconds"]}


def format_mix_played(conn: sqlite3.Connection, since_iso: str | None, until_iso: str | None = None) -> list[sqlite3.Row]:
    params: list[Any] = []
    query = (
        "SELECT COALESCE(tracks.codec, 'unknown') AS codec, COUNT(*) AS play_count "
        "FROM plays JOIN tracks ON tracks.id = plays.track_id"
    )
    query += _period_where(since_iso, until_iso, params)
    query += " GROUP BY codec ORDER BY play_count DESC"
    return conn.execute(query, params).fetchall()


def recently_played_albums(conn: sqlite3.Connection, limit: int = 40) -> list[sqlite3.Row]:
    query = (
        f"SELECT {_ALBUM_GROUP_ARTIST_EXPR} AS album_artist, {_ALBUM_GROUP_ALBUM_EXPR} AS album, tracks.year AS year, "
        "MAX(plays.started_at) AS last_played FROM plays JOIN tracks ON tracks.id = plays.track_id "
        "GROUP BY album_artist, album, year ORDER BY last_played DESC LIMIT ?"
    )
    return conn.execute(query, (limit,)).fetchall()


def encore_albums(conn: sqlite3.Connection, cutoff_iso: str, limit: int = 40) -> list[sqlite3.Row]:
    """Albums that have been played before but not in the last `cutoff_iso`
    stretch -- "you used to listen to this" rather than "you never have"."""
    query = (
        f"SELECT {_ALBUM_GROUP_ARTIST_EXPR} AS album_artist, {_ALBUM_GROUP_ALBUM_EXPR} AS album, tracks.year AS year, "
        "MAX(plays.started_at) AS last_played FROM plays JOIN tracks ON tracks.id = plays.track_id "
        "GROUP BY album_artist, album, year HAVING last_played < ? ORDER BY last_played ASC LIMIT ?"
    )
    return conn.execute(query, (cutoff_iso, limit)).fetchall()


# --- ratings -----------------------------------------------------------

def set_track_rating(conn: sqlite3.Connection, track_id: int, rating: int | None) -> None:
    conn.execute("UPDATE tracks SET rating = ? WHERE id = ?", (rating, track_id))
    conn.commit()


# --- internet radio -------------------------------------------------------

def list_radio_stations(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM radio_stations ORDER BY added_at DESC").fetchall()


def get_radio_station(conn: sqlite3.Connection, station_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM radio_stations WHERE id = ?", (station_id,)).fetchone()


def save_radio_station(
    conn: sqlite3.Connection,
    station_id: str,
    name: str,
    stream_url: str,
    favicon: str | None,
    tags: str | None,
    country: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO radio_stations (id, name, stream_url, favicon, tags, country)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name, stream_url = excluded.stream_url,
            favicon = excluded.favicon, tags = excluded.tags, country = excluded.country
        """,
        (station_id, name, stream_url, favicon, tags, country),
    )
    conn.commit()


def delete_radio_station(conn: sqlite3.Connection, station_id: str) -> bool:
    cur = conn.execute("DELETE FROM radio_stations WHERE id = ?", (station_id,))
    conn.commit()
    return cur.rowcount > 0


# --- smart playlists -----------------------------------------------------
#
# A smart playlist is a `playlists` row with is_smart=1 and its rule set
# serialized as JSON; there's no separate rules table since the rule shape
# is small, fully owned by this app (never hand-edited), and evaluated
# fresh on every view rather than stored as a materialized track list.

def create_smart_playlist(conn: sqlite3.Connection, name: str, description: str | None, rules: dict[str, Any]) -> int:
    cur = conn.execute(
        f"INSERT INTO playlists (name, description, is_smart, rules_json, created_at, updated_at) "
        f"VALUES (?, ?, 1, ?, {_NOW}, {_NOW})",
        (name, description, json.dumps(rules)),
    )
    conn.commit()
    return cur.lastrowid


def delete_playlist(conn: sqlite3.Connection, playlist_id: int) -> bool:
    cur = conn.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
    conn.commit()
    return cur.rowcount > 0


def get_playlist(conn: sqlite3.Connection, playlist_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM playlists WHERE id = ?", (playlist_id,)).fetchone()


def evaluate_smart_playlist(conn: sqlite3.Connection, rules: dict[str, Any]) -> list[sqlite3.Row]:
    clauses = ["tracks.online = 1"]
    params: list[Any] = []

    if rules.get("genre"):
        clauses.append("tracks.genre = ?")
        params.append(rules["genre"])
    if rules.get("year_min") is not None:
        clauses.append("tracks.year >= ?")
        params.append(rules["year_min"])
    if rules.get("year_max") is not None:
        clauses.append("tracks.year <= ?")
        params.append(rules["year_max"])
    if rules.get("min_rating") is not None:
        clauses.append("tracks.rating >= ?")
        params.append(rules["min_rating"])
    if rules.get("min_play_count") is not None:
        clauses.append("(SELECT COUNT(*) FROM plays WHERE plays.track_id = tracks.id) >= ?")
        params.append(rules["min_play_count"])
    if rules.get("last_played_before_days") is not None:
        clauses.append(
            "COALESCE((SELECT MAX(started_at) FROM plays WHERE plays.track_id = tracks.id), '') < ?"
        )
        params.append(iso_now_minus_days(rules["last_played_before_days"]))
    if rules.get("last_played_after_days") is not None:
        clauses.append(
            "(SELECT MAX(started_at) FROM plays WHERE plays.track_id = tracks.id) >= ?"
        )
        params.append(iso_now_minus_days(rules["last_played_after_days"]))

    order_by = {
        "title": "tracks.title COLLATE NOCASE",
        "artist": "tracks.artist COLLATE NOCASE, tracks.album COLLATE NOCASE",
        "recently_added": "tracks.added_at DESC",
        "random": "RANDOM()",
    }.get(rules.get("sort", "title"), "tracks.title COLLATE NOCASE")

    limit = max(1, min(int(rules.get("limit", 200)), 1000))
    query = f"SELECT tracks.* FROM tracks WHERE {' AND '.join(clauses)} ORDER BY {order_by} LIMIT ?"
    params.append(limit)
    return conn.execute(query, params).fetchall()
