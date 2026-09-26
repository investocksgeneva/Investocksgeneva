"""ObjectID encoding for the ContentDirectory browse tree.

DLNA ObjectIDs are opaque strings from the client's point of view, but ours
need to round-trip real (often unicode, slash-containing, arbitrary) tag
values -- an artist or album name -- through a SOAP/XML request. Each kind
of node gets a `<kind>:<payload>` id, where payload is a URL-safe-base64
encoding of the underlying key so no tag value can ever break the ObjectID
syntax or collide with our own ":" separator.

Album keys are (album_artist, album, year) tuples -- the same composite key
`v_albums`/`v_album_art` group on -- packed with the ASCII unit separator
(0x1F), a byte essentially never present in real tag text.
"""

from __future__ import annotations

import base64

ROOT_ID = "0"

_SEP = "\x1f"


def _encode(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def _decode(payload: str) -> str:
    padding = "=" * (-len(payload) % 4)
    return base64.urlsafe_b64decode(payload + padding).decode("utf-8")


def artist_id(name: str) -> str:
    return f"artist:{_encode(name)}"


def decode_artist_id(object_id: str) -> str:
    return _decode(object_id.split(":", 1)[1])


def album_id(album_artist: str, album: str, year: int | None) -> str:
    year_part = str(year) if year is not None else ""
    return f"album:{_encode(_SEP.join((album_artist, album, year_part)))}"


def decode_album_id(object_id: str) -> tuple[str, str, int | None]:
    album_artist, album, year_part = _decode(object_id.split(":", 1)[1]).split(_SEP)
    return album_artist, album, (int(year_part) if year_part else None)


def genre_id(name: str) -> str:
    return f"genre:{_encode(name)}"


def decode_genre_id(object_id: str) -> str:
    return _decode(object_id.split(":", 1)[1])


def year_id(year: int) -> str:
    return f"year:{year}"


def decode_year_id(object_id: str) -> int:
    return int(object_id.split(":", 1)[1])


def track_id(db_id: int) -> str:
    return f"track:{db_id}"


def decode_track_id(object_id: str) -> int:
    return int(object_id.split(":", 1)[1])


def kind_of(object_id: str) -> str:
    """The node "kind" (artist/album/genre/year/track/or a fixed top-level id)."""
    if ":" not in object_id:
        return object_id  # "0", "artists", "albums", "genres", "years", "recent", "playlists"
    return object_id.split(":", 1)[0]
