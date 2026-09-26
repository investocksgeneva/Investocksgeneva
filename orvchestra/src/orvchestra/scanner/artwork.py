"""Cover art extraction, hashing, and thumbnail caching.

Art is looked up embedded-first, then via a same-folder sidecar file, hashed
by content so identical artwork shared by an entire album (or reused across
albums) is only stored and thumbnailed once, and cached as JPEG thumbnails
under the app-data directory — never written back into the music folder.
"""

from __future__ import annotations

import hashlib
import io
import sqlite3
from pathlib import Path

from PIL import Image, UnidentifiedImageError

_SIDECAR_NAMES = (
    "cover.jpg", "cover.jpeg", "cover.png",
    "folder.jpg", "folder.jpeg", "folder.png",
    "Cover.jpg", "Cover.jpeg", "Cover.png",
    "Folder.jpg", "Folder.jpeg", "Folder.png",
)

THUMBNAIL_SIZES = (300, 1000)


def extract_embedded_bytes(picture) -> bytes | None:
    """Normalize the different shapes `scanner.tags.read_tags` can hand back."""
    if picture is None:
        return None
    if isinstance(picture, (bytes, bytearray)):
        return bytes(picture)
    data = getattr(picture, "data", None)
    return bytes(data) if data else None


def find_sidecar_art(directory: Path) -> Path | None:
    for name in _SIDECAR_NAMES:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def get_art_bytes(track_path: Path, picture) -> bytes | None:
    embedded = extract_embedded_bytes(picture)
    if embedded:
        return embedded
    sidecar = find_sidecar_art(track_path.parent)
    if sidecar is not None:
        try:
            return sidecar.read_bytes()
        except OSError:
            return None
    return None


def _thumb_paths(artwork_dir: Path, art_hash: str) -> dict[int, Path]:
    shard = artwork_dir / art_hash[:2] / art_hash
    return {size: shard / f"{size}.jpg" for size in THUMBNAIL_SIZES}


def cache_artwork(conn: sqlite3.Connection, artwork_dir: Path, data: bytes) -> str | None:
    """Ensure `data` is hashed, thumbnailed, and recorded in `artwork`.

    Returns the content hash, or None if `data` isn't a decodable image
    (corrupt embedded art shows up occasionally; it should never abort a scan).
    """
    art_hash = hashlib.sha256(data).hexdigest()

    row = conn.execute("SELECT hash FROM artwork WHERE hash = ?", (art_hash,)).fetchone()
    if row is not None:
        return art_hash

    paths = _thumb_paths(artwork_dir, art_hash)
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
    except (UnidentifiedImageError, OSError):
        return None

    shard_dir = paths[THUMBNAIL_SIZES[0]].parent
    shard_dir.mkdir(parents=True, exist_ok=True)
    for size in THUMBNAIL_SIZES:
        thumb = image.copy()
        thumb.thumbnail((size, size), Image.LANCZOS)
        thumb.save(paths[size], format="JPEG", quality=85)

    conn.execute(
        "INSERT OR IGNORE INTO artwork (hash, thumb_300_path, thumb_1000_path) VALUES (?, ?, ?)",
        (art_hash, str(paths[300]), str(paths[1000])),
    )
    return art_hash
