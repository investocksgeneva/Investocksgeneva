"""Internet radio: search Radio Browser for stations, save favorites
locally, and play one through whichever output is active. Playing and
saving are independent -- a search result can be played once without ever
being saved, same as how you'd try a station before keeping it.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from orvchestra.db import repository as repo
from orvchestra.playback.service import PlaybackService
from orvchestra.radio import browser_api


class SaveStationRequest(BaseModel):
    id: str
    name: str
    stream_url: str
    favicon: str | None = None
    tags: str | None = None
    country: str | None = None


class PlayStationRequest(BaseModel):
    id: str
    name: str
    stream_url: str
    favicon: str | None = None


def _station_json(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "stream_url": row["stream_url"],
        "favicon": row["favicon"],
        "tags": row["tags"],
        "country": row["country"],
    }


def build_radio_router(conn: sqlite3.Connection, playback: PlaybackService) -> APIRouter:
    router = APIRouter(prefix="/api/radio")

    @router.get("/search")
    async def search(q: str = "") -> list[dict[str, Any]]:
        try:
            return await browser_api.search_stations(q)
        except Exception as exc:  # noqa: BLE001 - Radio Browser being unreachable isn't a 500-worthy bug here
            raise HTTPException(502, f"Couldn't reach Radio Browser: {exc}") from None

    @router.get("/stations")
    async def list_stations() -> list[dict[str, Any]]:
        return [_station_json(r) for r in repo.list_radio_stations(conn)]

    @router.post("/stations")
    async def save_station(body: SaveStationRequest) -> dict[str, Any]:
        repo.save_radio_station(conn, body.id, body.name, body.stream_url, body.favicon, body.tags, body.country)
        return _station_json(repo.get_radio_station(conn, body.id))

    @router.delete("/stations/{station_id}", status_code=204)
    async def delete_station(station_id: str) -> None:
        repo.delete_radio_station(conn, station_id)

    @router.post("/play")
    async def play(body: PlayStationRequest) -> dict[str, Any]:
        await playback.play_radio(body.model_dump())
        return playback.now_playing()

    return router
