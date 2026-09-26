"""Smart playlists: create/list/delete a named rule set, and evaluate one
into a track list on demand. There is no manual/static playlist creation
yet (`playlist_items` sits unused in the schema, same as Phase 1 left it)
-- only what the phase plan explicitly asked for ("smart playlists defined
by rules") is built here.

Rules are stored as JSON (`playlists.rules_json`) rather than a rules
table: the shape is small, entirely owned by this app, and evaluated fresh
against the library on every view rather than materialized, so there is
nothing relational about it that would benefit from its own table.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from orvchestra.db import repository as repo
from orvchestra.webapp.api import make_track_json_fn


class SmartPlaylistRules(BaseModel):
    genre: str | None = None
    year_min: int | None = None
    year_max: int | None = None
    min_rating: int | None = Field(default=None, ge=1, le=5)
    min_play_count: int | None = Field(default=None, ge=0)
    last_played_before_days: int | None = Field(default=None, ge=0)
    last_played_after_days: int | None = Field(default=None, ge=0)
    sort: str = "title"
    limit: int = Field(default=200, ge=1, le=1000)


class CreateSmartPlaylistRequest(BaseModel):
    name: str
    description: str | None = None
    rules: SmartPlaylistRules


def _playlist_json(row: sqlite3.Row) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "is_smart": bool(row["is_smart"]),
    }
    if row["is_smart"] and row["rules_json"]:
        result["rules"] = json.loads(row["rules_json"])
    return result


def build_playlists_router(conn: sqlite3.Connection, media_base_url: str) -> APIRouter:
    router = APIRouter(prefix="/api/playlists")
    track_json = make_track_json_fn(media_base_url)

    @router.get("")
    async def list_playlists() -> list[dict[str, Any]]:
        return [_playlist_json(row) for row in repo.list_playlists(conn)]

    @router.post("")
    async def create_playlist(body: CreateSmartPlaylistRequest) -> dict[str, Any]:
        rules = body.rules.model_dump(exclude_none=True)
        playlist_id = repo.create_smart_playlist(conn, body.name, body.description, rules)
        return _playlist_json(repo.get_playlist(conn, playlist_id))

    @router.get("/{playlist_id}")
    async def get_playlist(playlist_id: int) -> dict[str, Any]:
        row = repo.get_playlist(conn, playlist_id)
        if row is None:
            raise HTTPException(404, "No such playlist")
        result = _playlist_json(row)
        if row["is_smart"]:
            rules = json.loads(row["rules_json"]) if row["rules_json"] else {}
            result["tracks"] = [track_json(t) for t in repo.evaluate_smart_playlist(conn, rules)]
        return result

    @router.delete("/{playlist_id}")
    async def delete_playlist(playlist_id: int) -> dict[str, bool]:
        deleted = repo.delete_playlist(conn, playlist_id)
        if not deleted:
            raise HTTPException(404, "No such playlist")
        return {"deleted": True}

    return router
