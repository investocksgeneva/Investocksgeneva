from __future__ import annotations

from orvchestra.dlna import ids


def test_artist_id_roundtrip():
    for name in ("Artist A", "Sigur Rós", "AC/DC", "Emerson, Lake & Palmer"):
        encoded = ids.artist_id(name)
        assert ids.kind_of(encoded) == "artist"
        assert ids.decode_artist_id(encoded) == name


def test_album_id_roundtrip_with_and_without_year():
    encoded = ids.album_id("Artist A", "Album/With Slash", 2020)
    assert ids.decode_album_id(encoded) == ("Artist A", "Album/With Slash", 2020)

    encoded_no_year = ids.album_id("Artist A", "Undated Album", None)
    assert ids.decode_album_id(encoded_no_year) == ("Artist A", "Undated Album", None)


def test_top_level_and_track_ids_are_plain():
    assert ids.kind_of("0") == "0"
    assert ids.kind_of("artists") == "artists"
    assert ids.decode_track_id(ids.track_id(42)) == 42
    assert ids.decode_year_id(ids.year_id(1999)) == 1999
