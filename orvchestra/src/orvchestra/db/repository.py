"""All SQL for roots/tracks/artwork lives here, so the scanner deals only in
plain Python values and never writes a query itself."""

from __future__ import annotations

import sqlite3
from typing import Iterable

from orvchestra.models import TrackTags

_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


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
            has_embedded_art, art_hash, added_at, updated_at
        ) VALUES (
            ?, ?, ?, ?, 1,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?,
            ?, ?,
            ?, ?, {_NOW}, {_NOW}
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
            int(has_embedded_art), art_hash,
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
            has_embedded_art = ?, art_hash = ?, updated_at = {_NOW}
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
            int(has_embedded_art), art_hash,
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
