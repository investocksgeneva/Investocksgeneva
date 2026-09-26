from __future__ import annotations

from pathlib import Path

from PIL import Image

from orvchestra.db import repository as repo
from orvchestra.scanner.scan import scan_root
from orvchestra import paths as orv_paths

from conftest import make_flac, _tiny_png


def test_embedded_artwork_is_cached_and_thumbnailed(db_conn, tmp_path):
    music = tmp_path / "music"
    make_flac(music / "a.flac", tags={"TITLE": "A"}, picture_bytes=_tiny_png())

    repo.add_root(db_conn, str(music), None, None)
    root = repo.get_root_by_path(db_conn, str(music))
    scan_root(db_conn, root, orv_paths.artwork_dir())

    row = db_conn.execute("SELECT * FROM tracks").fetchone()
    assert row["has_embedded_art"] == 1
    assert row["art_hash"] is not None

    art_row = db_conn.execute("SELECT * FROM artwork WHERE hash = ?", (row["art_hash"],)).fetchone()
    assert art_row is not None
    thumb_300 = Path(art_row["thumb_300_path"])
    thumb_1000 = Path(art_row["thumb_1000_path"])
    assert thumb_300.is_file()
    assert thumb_1000.is_file()
    with Image.open(thumb_300) as img:
        assert max(img.size) <= 300
    with Image.open(thumb_1000) as img:
        assert max(img.size) <= 1000


def test_sidecar_artwork_shared_across_album_tracks(db_conn, tmp_path):
    music = tmp_path / "music"
    album_dir = music / "Artist" / "Album"
    make_flac(album_dir / "01.flac", tags={"TITLE": "One"})
    make_flac(album_dir / "02.flac", tags={"TITLE": "Two"})
    (album_dir / "cover.jpg").write_bytes(_tiny_png())  # extension doesn't need to match encoding for this check

    repo.add_root(db_conn, str(music), None, None)
    root = repo.get_root_by_path(db_conn, str(music))
    scan_root(db_conn, root, orv_paths.artwork_dir())

    rows = db_conn.execute("SELECT art_hash, has_embedded_art FROM tracks ORDER BY rel_path").fetchall()
    assert len(rows) == 2
    assert rows[0]["has_embedded_art"] == 0
    assert rows[1]["has_embedded_art"] == 0
    assert rows[0]["art_hash"] is not None
    assert rows[0]["art_hash"] == rows[1]["art_hash"]  # same sidecar, hashed once

    assert db_conn.execute("SELECT COUNT(*) AS n FROM artwork").fetchone()["n"] == 1


def test_corrupt_embedded_art_does_not_break_scan(db_conn, tmp_path):
    music = tmp_path / "music"
    make_flac(music / "a.flac", tags={"TITLE": "A"}, picture_bytes=b"not a real image")

    repo.add_root(db_conn, str(music), None, None)
    root = repo.get_root_by_path(db_conn, str(music))
    stats = scan_root(db_conn, root, orv_paths.artwork_dir())

    assert stats.added == 1
    row = db_conn.execute("SELECT * FROM tracks").fetchone()
    assert row["art_hash"] is None
