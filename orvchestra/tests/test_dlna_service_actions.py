"""Exercises the ContentDirectory/ConnectionManager action methods directly
(bypassing SOAP entirely) using async_upnp_client's NopRequester -- covers
the small fixed-answer actions the HTTP-level tests don't happen to hit.

Service construction (not just the action calls) has to happen inside a
running event loop: `SystemUpdateID` is an eventable state variable, and
setting its default value schedules a coroutine via `asyncio.create_task`
at construction time.
"""

from __future__ import annotations

import asyncio

from async_upnp_client.server import NopRequester

from orvchestra.db import repository as repo
from orvchestra.dlna.connection_manager import ConnectionManagerService
from orvchestra.dlna.content_directory import ContentDirectoryService
from orvchestra.scanner.scan import scan_root
from orvchestra import paths as orv_paths

from conftest import make_flac

MEDIA_BASE = "http://192.168.1.50:8347"


def _content_directory(db_conn) -> ContentDirectoryService:
    ContentDirectoryService.conn = db_conn
    ContentDirectoryService.media_base_url = MEDIA_BASE
    return ContentDirectoryService(NopRequester())


def test_fixed_capability_actions_are_empty(db_conn):
    async def run():
        service = _content_directory(db_conn)
        assert await service.get_search_capabilities() == {"SearchCaps": ""}
        assert await service.get_sort_capabilities() == {"SortCaps": ""}

    asyncio.run(run())


def test_system_update_id_reflects_scans(db_conn, tmp_path):
    music = tmp_path / "music"

    async def run():
        service = _content_directory(db_conn)
        assert await service.get_system_update_id() == {"Id": 0}

        make_flac(music / "a.flac", tags={"TITLE": "A"})
        repo.add_root(db_conn, str(music), None, None)
        root = repo.get_root_by_path(db_conn, str(music))
        scan_root(db_conn, root, orv_paths.artwork_dir())

        assert await service.get_system_update_id() == {"Id": 1}

    asyncio.run(run())


def test_search_delegates_to_browse(db_conn, tmp_path):
    music = tmp_path / "music"

    async def run():
        make_flac(music / "a.flac", tags={"TITLE": "Findable", "ARTIST": "Someone"})
        repo.add_root(db_conn, str(music), None, None)
        root = repo.get_root_by_path(db_conn, str(music))
        scan_root(db_conn, root, orv_paths.artwork_dir())

        service = _content_directory(db_conn)
        result = await service.search("artists", "irrelevant search text", "*", 0, 0, "")
        assert result["NumberReturned"] == 1
        assert "Someone" in result["Result"]

    asyncio.run(run())


def test_playlists_container_is_empty_until_phase_4(db_conn):
    async def run():
        service = _content_directory(db_conn)
        result = await service.browse("playlists", "BrowseDirectChildren", "*", 0, 0, "")
        assert result["NumberReturned"] == 0
        assert result["TotalMatches"] == 0

    asyncio.run(run())


def test_connection_manager_fixed_answers(db_conn):
    async def run():
        service = ConnectionManagerService(NopRequester())
        info = await service.get_protocol_info()
        assert "audio/flac" in info["Source"]
        assert info["Sink"] == ""

        assert await service.get_current_connection_ids() == {"ConnectionIDs": "0"}

        current = await service.get_current_connection_info(0)
        assert current["Status"] == "OK"
        assert current["Direction"] == "Output"

    asyncio.run(run())
