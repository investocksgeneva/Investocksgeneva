"""The combined FastAPI app: media streaming, the JSON API, and the built
PWA, all on one port. Renderer discovery runs automatically in the
background (per the phase requirement to discover the WiiM without the user
doing anything) in addition to the on-demand `/api/outputs/refresh` the
frontend calls right when someone opens the output picker.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from starlette.responses import FileResponse

from orvchestra import paths
from orvchestra.media.app import build_media_router
from orvchestra.playback.service import PlaybackService
from orvchestra.webapp.api import build_api_router
from orvchestra.webapp.playlists_api import build_playlists_router
from orvchestra.webapp.stats_api import build_stats_router

logger = logging.getLogger("orvchestra.webapp")

_RENDERER_DISCOVERY_INTERVAL_SECONDS = 30


async def _renderer_discovery_loop(playback: PlaybackService) -> None:
    while True:
        try:
            await playback.refresh_renderers()
        except Exception as exc:  # noqa: BLE001 - a flaky network must not kill the app
            logger.warning("renderer discovery failed: %s", exc)
        await asyncio.sleep(_RENDERER_DISCOVERY_INTERVAL_SECONDS)


def create_app(conn: sqlite3.Connection, media_base_url: str, playback: PlaybackService) -> FastAPI:
    frontend_dist = paths.web_dist_dir()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.ensure_future(_renderer_discovery_loop(playback))
        try:
            yield
        finally:
            task.cancel()
            await playback.shutdown()

    app = FastAPI(title="Orvchestra", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.include_router(build_media_router(conn))
    app.include_router(build_api_router(conn, media_base_url, playback))
    app.include_router(build_stats_router(conn, media_base_url))
    app.include_router(build_playlists_router(conn, media_base_url))

    @app.get("/{full_path:path}")
    async def spa(full_path: str) -> FileResponse:
        resolved_dist = frontend_dist.resolve()
        candidate = (frontend_dist / full_path).resolve()
        # Refuse anything that would escape the dist directory (path
        # traversal via "../" segments in full_path).
        if full_path and candidate.is_relative_to(resolved_dist) and candidate.is_file():
            return FileResponse(candidate)

        index = resolved_dist / "index.html"
        if not index.is_file():
            raise HTTPException(
                404,
                "The web app hasn't been built yet -- run `npm install && npm run build` in web/, "
                "or set ORVCHESTRA_WEB_DIST to point at an existing build.",
            )
        return FileResponse(index)

    return app
