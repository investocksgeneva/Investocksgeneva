"""The Stats screen's API: top artists/albums/tracks by period, overall
listening hours and format mix, a per-year "Wrapped" summary, and "Encore"
(albums not played in 12+ months). All of it reads `plays` rows recorded by
`PlaybackService` (see playback/service.py's 50%-or-4-minutes rule) joined
back through the same repository functions and album-grouping key the rest
of the app uses, via `orvchestra.webapp.api`'s shared JSON shapers.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException

from orvchestra.db import repository as repo
from orvchestra.webapp.api import albums_with_extra, make_album_json_fn, make_track_json_fn

_VALID_PERIODS = {"7", "30", "90", "365", "all"}


def _since_for_period(period: str) -> str | None:
    if period not in _VALID_PERIODS:
        raise HTTPException(400, f"period must be one of {sorted(_VALID_PERIODS)}")
    return None if period == "all" else repo.iso_now_minus_days(int(period))


def build_stats_router(conn: sqlite3.Connection, media_base_url: str) -> APIRouter:
    router = APIRouter(prefix="/api/stats")

    album_json = make_album_json_fn(conn, media_base_url)
    track_json = make_track_json_fn(media_base_url)

    @router.get("/summary")
    async def summary(period: str = "30") -> dict[str, Any]:
        since = _since_for_period(period)
        totals = repo.listening_summary(conn, since)
        format_mix = repo.format_mix_played(conn, since)
        return {
            "period": period,
            "play_count": totals["play_count"],
            "total_seconds": totals["total_seconds"],
            "format_mix": [{"codec": row["codec"], "play_count": row["play_count"]} for row in format_mix],
        }

    @router.get("/top")
    async def top(kind: str = "tracks", period: str = "30", limit: int = 20) -> list[dict[str, Any]]:
        since = _since_for_period(period)
        limit = max(1, min(limit, 100))

        if kind == "tracks":
            return [track_json(row) for row in repo.top_tracks(conn, since, limit=limit)]
        if kind == "artists":
            return [
                {"artist": row["artist"], "play_count": row["play_count"]}
                for row in repo.top_artists(conn, since, limit=limit)
            ]
        if kind == "albums":
            return albums_with_extra(conn, album_json, repo.top_albums(conn, since, limit=limit), "play_count")
        raise HTTPException(400, "kind must be one of: tracks, artists, albums")

    @router.get("/encore")
    async def encore(months: int = 12, limit: int = 40) -> list[dict[str, Any]]:
        cutoff = repo.iso_now_minus_days(max(1, months) * 30)
        return albums_with_extra(conn, album_json, repo.encore_albums(conn, cutoff, limit=limit), "last_played")

    @router.get("/wrapped/{year}")
    async def wrapped(year: int) -> dict[str, Any]:
        since = f"{year}-01-01T00:00:00.000Z"
        until = f"{year + 1}-01-01T00:00:00.000Z"

        totals = repo.listening_summary(conn, since, until)
        format_mix = repo.format_mix_played(conn, since, until)
        top_album_rows = repo.top_albums(conn, since, until, limit=10)

        return {
            "year": year,
            "play_count": totals["play_count"],
            "total_seconds": totals["total_seconds"],
            "top_tracks": [track_json(row) for row in repo.top_tracks(conn, since, until, limit=10)],
            "top_artists": [
                {"artist": row["artist"], "play_count": row["play_count"]}
                for row in repo.top_artists(conn, since, until, limit=10)
            ],
            "top_albums": albums_with_extra(conn, album_json, top_album_rows, "play_count"),
            "format_mix": [{"codec": row["codec"], "play_count": row["play_count"]} for row in format_mix],
        }

    return router
