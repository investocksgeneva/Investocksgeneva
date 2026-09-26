"""Builds DIDL-Lite XML for ContentDirectory Browse responses.

We lean on `python-didl-lite` for the object/property serialization (it
already knows, for instance, that WiiM/Linkplay renderers want `upnp:class`
handled a particular way -- see its own source comments), but its
`Resource.to_xml()` only ever emits the `uri` and `protocolInfo` -- every
other `<res>` attribute we care about (size, duration, sample rate, bit
depth, channel count) is silently dropped. So tracks are built with an empty
`res=[]` and the fully-attributed `<res>` element is appended by hand
afterwards. Everything else (containers, dc:/upnp: properties) goes through
the library untouched.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Iterable

from didl_lite import didl_lite as dl
from didl_lite.utils import NAMESPACES

from orvchestra.dlna import ids
from orvchestra.dlna.protocol_info import protocol_info

_RESTRICTED = "1"


def _art_uri(media_base_url: str, art_hash: str | None) -> str | None:
    if not art_hash:
        return None
    return f"{media_base_url}/art/{art_hash}/1000.jpg"


def _format_duration(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    total_ms = round(seconds * 1000)
    hours, rem_ms = divmod(total_ms, 3_600_000)
    minutes, rem_ms = divmod(rem_ms, 60_000)
    secs, ms = divmod(rem_ms, 1000)
    return f"{hours}:{minutes:02d}:{secs:02d}.{ms:03d}"


def _stream_uri(media_base_url: str, track_row) -> str:
    # A file extension on the URL is cosmetic (some renderers sniff by
    # extension as a fallback when protocolInfo parsing is flaky), so we
    # add the real one even though the endpoint itself only cares about the
    # numeric id.
    ext = {"FLAC": "flac", "MP3": "mp3", "WAV": "wav", "AAC": "m4a", "ALAC": "m4a"}.get(track_row["codec"], "bin")
    return f"{media_base_url}/track/{track_row['id']}.{ext}"


def build_track_element(track_row, parent_id: str, media_base_url: str) -> ET.Element:
    title = track_row["title"] or track_row["rel_path"].rsplit("/", 1)[-1]
    year = track_row["year"]

    track_obj = dl.MusicTrack(
        id=ids.track_id(track_row["id"]),
        parent_id=parent_id,
        restricted=_RESTRICTED,
        title=title,
        artist=track_row["artist"],
        album=track_row["album"],
        genre=track_row["genre"],
        original_track_number=str(track_row["track_number"]) if track_row["track_number"] is not None else None,
        date=f"{year}-01-01" if year else None,
        album_art_uri=_art_uri(media_base_url, track_row["art_hash"]),
        res=[],
    )
    element = track_obj.to_xml()

    res_attrib = {"protocolInfo": protocol_info(track_row["codec"])}
    duration = _format_duration(track_row["duration_seconds"])
    if duration:
        res_attrib["duration"] = duration
    if track_row["size"] is not None:
        res_attrib["size"] = str(track_row["size"])
    if track_row["sample_rate"]:
        res_attrib["sampleFrequency"] = str(track_row["sample_rate"])
    if track_row["bit_depth"]:
        res_attrib["bitsPerSample"] = str(track_row["bit_depth"])
    if track_row["channels"]:
        res_attrib["nrAudioChannels"] = str(track_row["channels"])
    if track_row["bitrate"]:
        # DIDL-Lite's res@bitrate is bytes/second; we store kbps (see
        # scanner/tags.py), hence the *1000/8 unit conversion.
        res_attrib["bitrate"] = str(int(track_row["bitrate"] * 1000 / 8))

    res_el = ET.SubElement(element, "res", res_attrib)
    res_el.text = _stream_uri(media_base_url, track_row)
    return element


def build_album_element(album_row, parent_id: str, media_base_url: str, art_hash: str | None) -> ET.Element:
    obj = dl.MusicAlbum(
        id=ids.album_id(album_row["album_artist"], album_row["album"], album_row["year"]),
        parent_id=parent_id,
        restricted=_RESTRICTED,
        title=album_row["album"],
        artist=album_row["album_artist"],
        date=f"{album_row['year']}-01-01" if album_row["year"] else None,
        album_art_uri=_art_uri(media_base_url, art_hash),
        child_count=str(album_row["track_count"]),
        children=[],
    )
    return obj.to_xml()


def build_artist_element(artist_row, parent_id: str) -> ET.Element:
    obj = dl.MusicArtist(
        id=ids.artist_id(artist_row["artist"]),
        parent_id=parent_id,
        restricted=_RESTRICTED,
        title=artist_row["artist"],
        child_count=str(artist_row["album_count"]),
        children=[],
    )
    return obj.to_xml()


def build_genre_element(genre_name: str, parent_id: str) -> ET.Element:
    obj = dl.MusicGenre(
        id=ids.genre_id(genre_name), parent_id=parent_id, restricted=_RESTRICTED, title=genre_name, children=[]
    )
    return obj.to_xml()


def build_year_element(year: int, parent_id: str) -> ET.Element:
    obj = dl.StorageFolder(
        id=ids.year_id(year),
        parent_id=parent_id,
        restricted=_RESTRICTED,
        title=str(year),
        storage_used="-1",
        children=[],
    )
    return obj.to_xml()


def build_folder_element(object_id: str, parent_id: str, title: str) -> ET.Element:
    """A fixed top-level container: Artists, Albums, Genres, Years, Recently
    Added, Playlists, or the root itself."""
    obj = dl.StorageFolder(
        id=object_id, parent_id=parent_id, restricted=_RESTRICTED, title=title, storage_used="-1", children=[]
    )
    return obj.to_xml()


def build_playlist_element(playlist_row, parent_id: str) -> ET.Element:
    obj = dl.PlaylistContainer(
        id=f"playlist:{playlist_row['id']}",
        parent_id=parent_id,
        restricted=_RESTRICTED,
        title=playlist_row["name"],
        children=[],
    )
    return obj.to_xml()


def serialize(elements: Iterable[ET.Element]) -> str:
    root = ET.Element("DIDL-Lite")
    root.attrib["xmlns"] = NAMESPACES["didl_lite"]
    root.attrib["xmlns:dc"] = NAMESPACES["dc"]
    root.attrib["xmlns:upnp"] = NAMESPACES["upnp"]
    root.attrib["xmlns:sec"] = NAMESPACES["sec"]
    for element in elements:
        root.append(element)
    return ET.tostring(root, encoding="unicode")
