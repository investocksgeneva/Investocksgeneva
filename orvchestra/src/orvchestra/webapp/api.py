"""The JSON API the web app (and, eventually, only the web app) talks to:
library browsing, search, renderer selection, and playback control. Browse
data is read straight off the same repository functions and `(album_artist,
album, year)` grouping key that Phase 2's DLNA ContentDirectory uses, so the
web app's idea of "an album" and the WiiM's idea of "an album" can never
drift apart.

Track ids in this API are the plain integer primary key -- unlike DLNA
ObjectIDs, a JSON API has no reason to obscure them. Album/artist/genre/year
ids reuse `orvchestra.dlna.ids`'s base64 scheme rather than inventing a
second encoding for the same problem (arbitrary tag text -> a safe opaque
string).
"""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from orvchestra.db import repository as repo
from orvchestra.dlna import didl, ids
from orvchestra.playback.service import PlaybackService

_SEARCH_LIMIT = 25
_RECENT_ALBUMS_LIMIT = 40


class QueuePlayRequest(BaseModel):
    track_ids: list[int]
    start_index: int = 0


class SeekRequest(BaseModel):
    position_seconds: float


class VolumeRequest(BaseModel):
    level: float


class BrowserStateRequest(BaseModel):
    playing: bool


def _art_urls(media_base_url: str, art_hash: str | None) -> dict[str, str | None]:
    if not art_hash:
        return {"art_url_small": None, "art_url_large": None}
    return {
        "art_url_small": f"{media_base_url}/art/{art_hash}/300.jpg",
        "art_url_large": f"{media_base_url}/art/{art_hash}/1000.jpg",
    }


def _track_json(row: sqlite3.Row, media_base_url: str) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"] or row["rel_path"].rsplit("/", 1)[-1],
        "artist": row["artist"],
        "album_artist": row["album_artist"],
        "album": row["album"],
        "album_id": ids.album_id(*didl.canonical_album_key(row)),
        "year": row["year"],
        "genre": row["genre"],
        "track_number": row["track_number"],
        "disc_number": row["disc_number"],
        "duration_seconds": row["duration_seconds"],
        "codec": row["codec"],
        "sample_rate": row["sample_rate"],
        "bit_depth": row["bit_depth"],
        "channels": row["channels"],
        "online": bool(row["online"]),
        **_art_urls(media_base_url, row["art_hash"]),
    }


def _album_json(row: sqlite3.Row, media_base_url: str, art_hash: str | None) -> dict[str, Any]:
    return {
        "id": ids.album_id(row["album_artist"], row["album"], row["year"]),
        "album": row["album"],
        "album_artist": row["album_artist"],
        # Included so the frontend can link "by <album_artist>" back to the
        # artist page without reimplementing the ids.py base64 scheme in JS.
        "artist_id": None if row["album_artist"] == "Various Artists" else ids.artist_id(row["album_artist"]),
        "year": row["year"],
        "track_count": row["track_count"],
        "disc_count": row["disc_count"],
        "total_duration_seconds": row["total_duration_seconds"],
        "added_at": row["added_at"],
        "offline_track_count": row["offline_track_count"],
        **_art_urls(media_base_url, art_hash),
    }


def _artist_json(row: sqlite3.Row) -> dict[str, Any]:
    return {"id": ids.artist_id(row["artist"]), "artist": row["artist"], "album_count": row["album_count"], "track_count": row["track_count"]}


def build_api_router(conn: sqlite3.Connection, media_base_url: str, playback: PlaybackService) -> APIRouter:
    router = APIRouter(prefix="/api")

    def album_art(row: sqlite3.Row) -> str | None:
        return repo.get_album_art_hash(conn, row["album_artist"], row["album"], row["year"])

    def album_json(row: sqlite3.Row) -> dict[str, Any]:
        return _album_json(row, media_base_url, album_art(row))

    def track_json(row: sqlite3.Row) -> dict[str, Any]:
        return _track_json(row, media_base_url)

    # --- browsing -----------------------------------------------------

    @router.get("/home")
    async def home() -> dict[str, Any]:
        return {
            "recently_added": [album_json(r) for r in repo.list_recent_albums(conn, _RECENT_ALBUMS_LIMIT)],
            # Listening history doesn't exist until Phase 4's `plays` table
            # is populated; these are intentionally empty, not broken.
            "recently_played": [],
            "rediscover": [],
        }

    @router.get("/search")
    async def search(q: str = "") -> dict[str, Any]:
        if not q.strip():
            return {"artists": [], "albums": [], "tracks": []}
        return {
            "artists": [_artist_json(r) for r in repo.search_artists(conn, q, _SEARCH_LIMIT)],
            "albums": [album_json(r) for r in repo.search_albums(conn, q, _SEARCH_LIMIT)],
            "tracks": [track_json(r) for r in repo.search_tracks(conn, q, _SEARCH_LIMIT)],
        }

    @router.get("/artists")
    async def list_artists() -> list[dict[str, Any]]:
        return [_artist_json(r) for r in repo.list_artists(conn)]

    @router.get("/artists/{artist_id}")
    async def get_artist(artist_id: str) -> dict[str, Any]:
        name = ids.decode_artist_id(artist_id)
        row = repo.get_artist(conn, name)
        if row is None:
            raise HTTPException(404, "No such artist")
        albums = [album_json(r) for r in repo.list_albums_by_artist(conn, name)]
        return {**_artist_json(row), "albums": albums}

    @router.get("/albums")
    async def list_albums() -> list[dict[str, Any]]:
        return [album_json(r) for r in repo.list_albums(conn)]

    @router.get("/albums/{album_id}")
    async def get_album(album_id: str) -> dict[str, Any]:
        album_artist, album, year = ids.decode_album_id(album_id)
        row = repo.get_album(conn, album_artist, album, year)
        if row is None:
            raise HTTPException(404, "No such album")
        tracks = [track_json(r) for r in repo.list_tracks_for_album(conn, album_artist, album, year)]
        return {**album_json(row), "tracks": tracks}

    @router.get("/genres")
    async def list_genres() -> list[dict[str, Any]]:
        return [{"id": ids.genre_id(name), "name": name} for name in repo.list_genres(conn)]

    @router.get("/genres/{genre_id}")
    async def get_genre(genre_id: str) -> dict[str, Any]:
        name = ids.decode_genre_id(genre_id)
        tracks = [track_json(r) for r in repo.list_tracks_for_genre(conn, name)]
        return {"id": genre_id, "name": name, "tracks": tracks}

    @router.get("/years")
    async def list_years() -> list[dict[str, Any]]:
        return [{"id": ids.year_id(y), "year": y} for y in repo.list_years(conn)]

    @router.get("/years/{year}")
    async def get_year(year: int) -> dict[str, Any]:
        albums = [album_json(r) for r in repo.list_albums_for_year(conn, year)]
        return {"id": ids.year_id(year), "year": year, "albums": albums}

    @router.get("/playlists")
    async def list_playlists() -> list[dict[str, Any]]:
        # Empty until Phase 4 adds playlist creation; the endpoint exists now
        # so the frontend's Playlists screen has something real to call.
        return [
            {"id": row["id"], "name": row["name"], "description": row["description"]}
            for row in repo.list_playlists(conn)
        ]

    # --- outputs (renderer selection) -------------------------------------

    @router.get("/outputs")
    async def list_outputs() -> list[dict[str, Any]]:
        return playback.list_outputs()

    @router.post("/outputs/refresh")
    async def refresh_outputs() -> list[dict[str, Any]]:
        await playback.refresh_renderers()
        return playback.list_outputs()

    @router.post("/outputs/{output_id}/select")
    async def select_output(output_id: str) -> dict[str, Any]:
        try:
            playback.select_output(output_id)
        except KeyError:
            raise HTTPException(404, "No such output") from None
        return {"selected": output_id}

    # --- now playing / queue / transport control --------------------------

    @router.get("/now-playing")
    async def now_playing() -> dict[str, Any]:
        return playback.now_playing()

    @router.get("/queue")
    async def get_queue() -> dict[str, Any]:
        tracks = []
        for track_id in playback.queue:
            row = repo.get_track(conn, track_id)
            if row is not None:
                tracks.append(track_json(row))
        return {"tracks": tracks, "position": playback.queue_position}

    @router.post("/queue/play")
    async def play_queue(body: QueuePlayRequest) -> dict[str, Any]:
        if not body.track_ids:
            raise HTTPException(400, "track_ids must not be empty")
        playback.set_queue(body.track_ids, body.start_index)
        await playback.play_current()
        return playback.now_playing()

    @router.post("/playback/resume")
    async def resume() -> dict[str, Any]:
        await playback.resume()
        return playback.now_playing()

    @router.post("/playback/pause")
    async def pause() -> dict[str, Any]:
        await playback.pause()
        return playback.now_playing()

    @router.post("/playback/stop")
    async def stop() -> dict[str, Any]:
        await playback.stop()
        return playback.now_playing()

    @router.post("/playback/next")
    async def next_track() -> dict[str, Any]:
        await playback.next()
        return playback.now_playing()

    @router.post("/playback/previous")
    async def previous_track() -> dict[str, Any]:
        await playback.previous()
        return playback.now_playing()

    @router.post("/playback/seek")
    async def seek(body: SeekRequest) -> dict[str, Any]:
        await playback.seek(body.position_seconds)
        return playback.now_playing()

    @router.post("/playback/volume")
    async def set_volume(body: VolumeRequest) -> dict[str, Any]:
        await playback.set_volume(body.level)
        return playback.now_playing()

    @router.post("/playback/browser-state")
    async def browser_state(body: BrowserStateRequest) -> dict[str, str]:
        # The frontend's <audio> element calls this on play/pause/ended, so
        # keep-awake knows a browser is actively streaming even though
        # Orvchestra has no other visibility into "this device" playback.
        playback.set_browser_playing(body.playing)
        return {"ok": "true"}

    return router
