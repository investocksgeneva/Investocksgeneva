"""Exercises the ContentDirectory Browse logic directly (no HTTP/SOAP), by
calling `content_directory._children`/`_metadata` against a real scanned
library. `test_dlna_http.py` covers the actual SOAP-over-HTTP wire format;
this file is about getting the browse tree and DIDL content right."""

from __future__ import annotations

import pytest
from async_upnp_client.exceptions import UpnpActionError
from didl_lite import didl_lite as dl

from orvchestra.db import repository as repo
from orvchestra.dlna import content_directory as cd
from orvchestra.dlna import didl, ids
from orvchestra.scanner.scan import scan_root
from orvchestra import paths as orv_paths

from conftest import make_flac, make_mp3

MEDIA_BASE = "http://192.168.1.50:8347"


def _seed_library(db_conn, tmp_path):
    music = tmp_path / "music"
    make_flac(
        music / "Artist A" / "Album A" / "01.flac",
        tags={
            "TITLE": "Song One", "ARTIST": "Artist A", "ALBUMARTIST": "Artist A", "ALBUM": "Album A",
            "TRACKNUMBER": "1", "DISCNUMBER": "1", "DATE": "2020", "GENRE": "Rock",
        },
    )
    make_flac(
        music / "Artist A" / "Album A" / "02.flac",
        tags={
            "TITLE": "Song Two", "ARTIST": "Artist A", "ALBUMARTIST": "Artist A", "ALBUM": "Album A",
            "TRACKNUMBER": "2", "DISCNUMBER": "1", "DATE": "2020", "GENRE": "Rock",
        },
        bit_depth=24, samplerate=96000,
    )
    make_mp3(
        music / "Compilation" / "01.mp3",
        tags={"title": "Comp One", "artist": "Someone", "album": "Big Compilation", "compilation": "1", "date": "2021"},
    )
    make_mp3(
        music / "Compilation" / "02.mp3",
        tags={"title": "Comp Two", "artist": "Someone Else", "album": "Big Compilation", "compilation": "1", "date": "2021"},
    )

    repo.add_root(db_conn, str(music), None, None)
    root = repo.get_root_by_path(db_conn, str(music))
    scan_root(db_conn, root, orv_paths.artwork_dir())


def _titles(elements) -> list[str]:
    objs = dl.from_xml_string(didl.serialize(elements))
    return [obj.title for obj in objs]


def test_root_lists_six_fixed_containers(db_conn, tmp_path):
    _seed_library(db_conn, tmp_path)
    children = cd._children(db_conn, ids.ROOT_ID, MEDIA_BASE)
    assert _titles(children) == ["Artists", "Albums (A–Z)", "Genres", "Years", "Recently Added", "Playlists"]


def test_artists_then_albums_then_tracks(db_conn, tmp_path):
    _seed_library(db_conn, tmp_path)

    artists = cd._children(db_conn, "artists", MEDIA_BASE)
    artist_titles = _titles(artists)
    assert "Artist A" in artist_titles
    assert "Various Artists" not in artist_titles  # compilations don't get their own artist node

    artist_a_id = ids.artist_id("Artist A")
    albums = cd._children(db_conn, artist_a_id, MEDIA_BASE)
    assert _titles(albums) == ["Album A"]

    album_id = ids.album_id("Artist A", "Album A", 2020)
    tracks = cd._children(db_conn, album_id, MEDIA_BASE)
    assert _titles(tracks) == ["Song One", "Song Two"]


def test_compilation_album_reachable_under_various_artists(db_conn, tmp_path):
    _seed_library(db_conn, tmp_path)

    albums = cd._children(db_conn, "albums", MEDIA_BASE)
    album_objs = dl.from_xml_string(didl.serialize(albums))
    comp = next(a for a in album_objs if a.title == "Big Compilation")
    assert comp.artist == "Various Artists"

    tracks = cd._children(db_conn, ids.album_id("Various Artists", "Big Compilation", 2021), MEDIA_BASE)
    assert _titles(tracks) == ["Comp One", "Comp Two"]


def test_genres_and_years(db_conn, tmp_path):
    _seed_library(db_conn, tmp_path)

    genres = cd._children(db_conn, "genres", MEDIA_BASE)
    assert _titles(genres) == ["Rock"]
    rock_tracks = cd._children(db_conn, ids.genre_id("Rock"), MEDIA_BASE)
    assert _titles(rock_tracks) == ["Song One", "Song Two"]

    years = cd._children(db_conn, "years", MEDIA_BASE)
    assert _titles(years) == ["2021", "2020"]
    albums_2020 = cd._children(db_conn, ids.year_id(2020), MEDIA_BASE)
    assert _titles(albums_2020) == ["Album A"]


def test_track_resource_has_stream_url_and_hires_attributes(db_conn, tmp_path):
    _seed_library(db_conn, tmp_path)

    album_id = ids.album_id("Artist A", "Album A", 2020)
    tracks = cd._children(db_conn, album_id, MEDIA_BASE)
    objs = dl.from_xml_string(didl.serialize(tracks))
    hires_track = next(o for o in objs if o.title == "Song Two")
    res = hires_track.resources[0]
    assert res.uri.startswith(MEDIA_BASE + "/track/")
    assert res.sample_frequency == "96000"
    assert res.bits_per_sample == "24"
    assert "audio/flac" in res.protocol_info


def test_browse_metadata_for_track_has_album_parent(db_conn, tmp_path):
    _seed_library(db_conn, tmp_path)
    track_row = db_conn.execute("SELECT id FROM tracks WHERE title = 'Song One'").fetchone()

    element = cd._metadata(db_conn, ids.track_id(track_row["id"]), MEDIA_BASE)
    (obj,) = dl.from_xml_string(didl.serialize([element]))
    assert obj.title == "Song One"
    assert obj.parent_id == ids.album_id("Artist A", "Album A", 2020)


def test_unknown_object_id_raises(db_conn, tmp_path):
    _seed_library(db_conn, tmp_path)
    with pytest.raises(UpnpActionError):
        cd._children(db_conn, "not-a-real-id", MEDIA_BASE)
