"""The ContentDirectory:1 service: Browse is the action that actually
matters (it's how WiiM Home walks the Artists/Albums/Genres/Years/Recently
Added/Playlists tree); Search is implemented as a thin alias over Browse
rather than real text search (see README) since nothing in Phase 2 needs it
-- real search is a Phase 3 web-app feature built on the FTS5 index.
"""

import sqlite3
import xml.etree.ElementTree as ET

from async_upnp_client.const import ServiceInfo
from async_upnp_client.exceptions import UpnpActionError
from async_upnp_client.server import (
    UpnpServerService,
    callable_action,
    create_event_var,
    create_state_var,
)

from orvchestra.db import repository as repo
from orvchestra.dlna import didl, ids

_TOP_LEVEL_TITLES = {
    "artists": "Artists",
    "albums": "Albums (A–Z)",
    "genres": "Genres",
    "years": "Years",
    "recent": "Recently Added",
    "playlists": "Playlists",
}


def _album_art(conn: sqlite3.Connection, row: sqlite3.Row) -> str | None:
    return repo.get_album_art_hash(conn, row["album_artist"], row["album"], row["year"])


def _children(conn: sqlite3.Connection, object_id: str, media_base_url: str) -> list[ET.Element]:
    if object_id == ids.ROOT_ID:
        return [didl.build_folder_element(oid, ids.ROOT_ID, title) for oid, title in _TOP_LEVEL_TITLES.items()]

    if object_id in _TOP_LEVEL_TITLES:
        if object_id == "artists":
            return [didl.build_artist_element(row, object_id) for row in repo.list_artists(conn)]
        if object_id == "albums":
            return [
                didl.build_album_element(row, object_id, media_base_url, _album_art(conn, row))
                for row in repo.list_albums(conn)
            ]
        if object_id == "genres":
            return [didl.build_genre_element(name, object_id) for name in repo.list_genres(conn)]
        if object_id == "years":
            return [didl.build_year_element(year, object_id) for year in repo.list_years(conn)]
        if object_id == "recent":
            return [
                didl.build_album_element(row, object_id, media_base_url, _album_art(conn, row))
                for row in repo.list_recent_albums(conn)
            ]
        if object_id == "playlists":
            return [didl.build_playlist_element(row, object_id) for row in repo.list_playlists(conn)]

    kind = ids.kind_of(object_id)
    if kind == "artist":
        name = ids.decode_artist_id(object_id)
        return [
            didl.build_album_element(row, object_id, media_base_url, _album_art(conn, row))
            for row in repo.list_albums_by_artist(conn, name)
        ]
    if kind == "album":
        album_artist, album, year = ids.decode_album_id(object_id)
        return [
            didl.build_track_element(row, object_id, media_base_url)
            for row in repo.list_tracks_for_album(conn, album_artist, album, year)
        ]
    if kind == "genre":
        name = ids.decode_genre_id(object_id)
        return [
            didl.build_track_element(row, object_id, media_base_url)
            for row in repo.list_tracks_for_genre(conn, name)
        ]
    if kind == "year":
        year = ids.decode_year_id(object_id)
        return [
            didl.build_album_element(row, object_id, media_base_url, _album_art(conn, row))
            for row in repo.list_albums_for_year(conn, year)
        ]
    if kind == "playlist":
        return []  # Phase 4 fills these in; an empty, browsable container is correct for now.
    if kind == "track":
        return []  # a track is a leaf; DLNA clients shouldn't Browse into it, but answer emptily rather than error.

    raise UpnpActionError(error_code=701, error_desc="No such object")


def _metadata(conn: sqlite3.Connection, object_id: str, media_base_url: str) -> ET.Element:
    if object_id == ids.ROOT_ID:
        return didl.build_folder_element(ids.ROOT_ID, "-1", "Orvchestra")

    if object_id in _TOP_LEVEL_TITLES:
        return didl.build_folder_element(object_id, ids.ROOT_ID, _TOP_LEVEL_TITLES[object_id])

    kind = ids.kind_of(object_id)
    if kind == "artist":
        name = ids.decode_artist_id(object_id)
        row = repo.get_artist(conn, name)
        if row is None:
            raise UpnpActionError(error_code=701, error_desc="No such object")
        return didl.build_artist_element(row, "artists")
    if kind == "album":
        album_artist, album, year = ids.decode_album_id(object_id)
        row = repo.get_album(conn, album_artist, album, year)
        if row is None:
            raise UpnpActionError(error_code=701, error_desc="No such object")
        return didl.build_album_element(row, "albums", media_base_url, _album_art(conn, row))
    if kind == "genre":
        return didl.build_genre_element(ids.decode_genre_id(object_id), "genres")
    if kind == "year":
        return didl.build_year_element(ids.decode_year_id(object_id), "years")
    if kind == "track":
        row = repo.get_track(conn, ids.decode_track_id(object_id))
        if row is None:
            raise UpnpActionError(error_code=701, error_desc="No such object")
        album_artist = "Various Artists" if row["compilation"] else (row["album_artist"] or row["artist"] or "Unknown Artist")
        album = row["album"] or "Unknown Album"
        parent_id = ids.album_id(album_artist, album, row["year"])
        return didl.build_track_element(row, parent_id, media_base_url)

    raise UpnpActionError(error_code=701, error_desc="No such object")


class ContentDirectoryService(UpnpServerService):
    """Set `ContentDirectoryService.conn` and `.media_base_url` as class
    attributes before constructing the device: `UpnpServerDevice.__init__`
    instantiates each service as `service_type(requester=requester)`, with
    no way to pass extra constructor arguments through, so there's no
    instance-level hook to inject dependencies into. With exactly one
    device per process this is safe and far simpler than reshaping the
    framework's construction path."""

    conn: sqlite3.Connection
    media_base_url: str

    SERVICE_DEFINITION = ServiceInfo(
        service_id="urn:upnp-org:serviceId:ContentDirectory",
        service_type="urn:schemas-upnp-org:service:ContentDirectory:1",
        control_url="/upnp/content_directory/control",
        event_sub_url="/upnp/content_directory/event",
        scpd_url="/upnp/content_directory/scpd.xml",
        xml=ET.Element("service"),
    )
    STATE_VARIABLE_DEFINITIONS = {
        "A_ARG_TYPE_ObjectID": create_state_var("string"),
        "A_ARG_TYPE_Result": create_state_var("string"),
        "A_ARG_TYPE_BrowseFlag": create_state_var("string", allowed=["BrowseMetadata", "BrowseDirectChildren"]),
        "A_ARG_TYPE_Filter": create_state_var("string"),
        "A_ARG_TYPE_SortCriteria": create_state_var("string"),
        "A_ARG_TYPE_Index": create_state_var("ui4"),
        "A_ARG_TYPE_Count": create_state_var("ui4"),
        "A_ARG_TYPE_UpdateID": create_state_var("ui4"),
        "A_ARG_TYPE_SearchCriteria": create_state_var("string"),
        "SearchCapabilities": create_state_var("string", default=""),
        "SortCapabilities": create_state_var("string", default=""),
        "SystemUpdateID": create_event_var("ui4", default="0"),
    }

    @callable_action(
        "Browse",
        in_args={
            "ObjectID": "A_ARG_TYPE_ObjectID",
            "BrowseFlag": "A_ARG_TYPE_BrowseFlag",
            "Filter": "A_ARG_TYPE_Filter",
            "StartingIndex": "A_ARG_TYPE_Index",
            "RequestedCount": "A_ARG_TYPE_Count",
            "SortCriteria": "A_ARG_TYPE_SortCriteria",
        },
        out_args={
            "Result": "A_ARG_TYPE_Result",
            "NumberReturned": "A_ARG_TYPE_Count",
            "TotalMatches": "A_ARG_TYPE_Count",
            "UpdateID": "A_ARG_TYPE_UpdateID",
        },
    )
    async def browse(
        self,
        ObjectID: str,
        BrowseFlag: str,
        Filter: str,
        StartingIndex: int,
        RequestedCount: int,
        SortCriteria: str,
    ) -> dict:
        update_id = repo.get_system_update_id(self.conn)

        if BrowseFlag == "BrowseMetadata":
            element = _metadata(self.conn, ObjectID, self.media_base_url)
            return {
                "Result": didl.serialize([element]),
                "NumberReturned": 1,
                "TotalMatches": 1,
                "UpdateID": update_id,
            }

        all_children = _children(self.conn, ObjectID, self.media_base_url)
        total = len(all_children)
        start = min(StartingIndex, total)
        end = total if RequestedCount == 0 else min(start + RequestedCount, total)
        page = all_children[start:end]

        return {
            "Result": didl.serialize(page),
            "NumberReturned": len(page),
            "TotalMatches": total,
            "UpdateID": update_id,
        }

    @callable_action(
        "Search",
        in_args={
            "ContainerID": "A_ARG_TYPE_ObjectID",
            "SearchCriteria": "A_ARG_TYPE_SearchCriteria",
            "Filter": "A_ARG_TYPE_Filter",
            "StartingIndex": "A_ARG_TYPE_Index",
            "RequestedCount": "A_ARG_TYPE_Count",
            "SortCriteria": "A_ARG_TYPE_SortCriteria",
        },
        out_args={
            "Result": "A_ARG_TYPE_Result",
            "NumberReturned": "A_ARG_TYPE_Count",
            "TotalMatches": "A_ARG_TYPE_Count",
            "UpdateID": "A_ARG_TYPE_UpdateID",
        },
    )
    async def search(
        self,
        ContainerID: str,
        SearchCriteria: str,
        Filter: str,
        StartingIndex: int,
        RequestedCount: int,
        SortCriteria: str,
    ) -> dict:
        return await self.browse(ContainerID, "BrowseDirectChildren", Filter, StartingIndex, RequestedCount, SortCriteria)

    @callable_action("GetSearchCapabilities", in_args={}, out_args={"SearchCaps": "SearchCapabilities"})
    async def get_search_capabilities(self) -> dict:
        return {"SearchCaps": ""}

    @callable_action("GetSortCapabilities", in_args={}, out_args={"SortCaps": "SortCapabilities"})
    async def get_sort_capabilities(self) -> dict:
        return {"SortCaps": ""}

    @callable_action("GetSystemUpdateID", in_args={}, out_args={"Id": "SystemUpdateID"})
    async def get_system_update_id(self) -> dict:
        return {"Id": repo.get_system_update_id(self.conn)}
