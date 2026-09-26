"""The HTTP media layer: range-request file streaming and cached-artwork
serving. This is what the WiiM, and now the web app/browser, actually fetch
bytes from -- the DLNA server only ever hands out URLs into this router.

Range/206 support comes for free from Starlette's `FileResponse` -- no
hand-rolled byte-range parsing needed.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from starlette.responses import FileResponse

from orvchestra.db import repository as repo
from orvchestra.dlna.protocol_info import dlna_content_features, mime_type_for


def build_media_router(conn: sqlite3.Connection) -> APIRouter:
    router = APIRouter()

    # DLNA/UPnP renderers routinely HEAD a resource before GETting it, to read
    # Content-Type/Content-Length/Accept-Ranges up front -- this FastAPI/
    # Starlette version doesn't synthesize HEAD from GET automatically, so
    # both routes register it explicitly.
    @router.api_route("/track/{track_id}.{ext}", methods=["GET", "HEAD"])
    async def stream_track(track_id: int, ext: str) -> FileResponse:
        row = repo.get_track(conn, track_id)
        if row is None:
            raise HTTPException(404, "No such track")
        if not row["online"] or not row["root_online"]:
            raise HTTPException(503, "Track is currently offline (its drive may be unplugged)")

        path = Path(row["root_path"]) / row["rel_path"]
        if not path.is_file():
            raise HTTPException(503, "File missing on disk")

        codec = row["codec"]
        return FileResponse(
            path,
            media_type=mime_type_for(codec),
            headers={
                "contentFeatures.dlna.org": dlna_content_features(codec),
                "transferMode.dlna.org": "Streaming",
            },
        )

    @router.api_route("/art/{art_hash}/{size}.jpg", methods=["GET", "HEAD"])
    async def get_art(art_hash: str, size: int) -> FileResponse:
        if size not in (300, 1000):
            raise HTTPException(404, "No such thumbnail size (use 300 or 1000)")
        row = repo.get_artwork(conn, art_hash)
        if row is None:
            raise HTTPException(404, "No such artwork")
        column = "thumb_300_path" if size == 300 else "thumb_1000_path"
        thumb_path = Path(row[column])
        if not thumb_path.is_file():
            raise HTTPException(404, "Thumbnail missing from cache")
        return FileResponse(thumb_path, media_type="image/jpeg")

    return router


def create_media_app(conn: sqlite3.Connection) -> FastAPI:
    """A standalone app with just the media routes -- kept for the Phase 2
    test suite and for anyone who wants the media endpoint without the rest
    of the web app. `orvchestra serve` uses `build_media_router` directly,
    mounted alongside the JSON API and the PWA on one app."""
    app = FastAPI(title="Orvchestra media", docs_url=None, redoc_url=None)
    app.include_router(build_media_router(conn))
    return app
