"""The HTTP media layer: range-request file streaming and cached-artwork
serving. This is what the WiiM (and, in later phases, a browser) actually
fetches bytes from -- the DLNA server only ever hands out URLs into this
app. Kept on its own FastAPI/uvicorn process port rather than folded into
the aiohttp app the DLNA control-plane runs on, since this is the piece
Phase 3 (browser playback) and Phase 5 (transcoding) build directly on top
of, per the architecture's "HTTP media endpoints" box.

Range/206 support comes for free from Starlette's `FileResponse` -- no
hand-rolled byte-range parsing needed.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException
from starlette.responses import FileResponse

from orvchestra.db import repository as repo
from orvchestra.dlna.protocol_info import dlna_content_features, mime_type_for


def create_media_app(conn: sqlite3.Connection) -> FastAPI:
    app = FastAPI(title="Orvchestra media", docs_url=None, redoc_url=None)

    # DLNA/UPnP renderers routinely HEAD a resource before GETting it, to read
    # Content-Type/Content-Length/Accept-Ranges up front -- this FastAPI/
    # Starlette version doesn't synthesize HEAD from GET automatically, so
    # both routes register it explicitly.
    @app.api_route("/track/{track_id}.{ext}", methods=["GET", "HEAD"])
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

    @app.api_route("/art/{art_hash}/{size}.jpg", methods=["GET", "HEAD"])
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

    return app
