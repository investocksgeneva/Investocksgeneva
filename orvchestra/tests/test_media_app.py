from __future__ import annotations

from starlette.testclient import TestClient

from orvchestra.db import repository as repo
from orvchestra.media.app import create_media_app
from orvchestra.scanner.scan import scan_root
from orvchestra import paths as orv_paths

from conftest import make_flac, _tiny_png


def _seed(db_conn, tmp_path):
    music = tmp_path / "music"
    make_flac(music / "a.flac", tags={"TITLE": "A"}, picture_bytes=_tiny_png())
    repo.add_root(db_conn, str(music), None, None)
    root = repo.get_root_by_path(db_conn, str(music))
    scan_root(db_conn, root, orv_paths.artwork_dir())
    track = db_conn.execute("SELECT * FROM tracks").fetchone()
    return music, track


def test_stream_full_file_byte_identical(db_conn, tmp_path):
    music, track = _seed(db_conn, tmp_path)
    client = TestClient(create_media_app(db_conn))

    resp = client.get(f"/track/{track['id']}.flac")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/flac"
    assert resp.headers["contentfeatures.dlna.org"].startswith("DLNA.ORG_OP=01")
    assert resp.headers["transfermode.dlna.org"] == "Streaming"
    assert resp.content == (music / "a.flac").read_bytes()


def test_stream_range_request(db_conn, tmp_path):
    music, track = _seed(db_conn, tmp_path)
    client = TestClient(create_media_app(db_conn))

    full = (music / "a.flac").read_bytes()
    resp = client.get(f"/track/{track['id']}.flac", headers={"Range": "bytes=0-9"})
    assert resp.status_code == 206
    assert resp.content == full[:10]
    assert resp.headers["content-range"] == f"bytes 0-9/{len(full)}"


def test_head_request_matches_get_headers(db_conn, tmp_path):
    _seed(db_conn, tmp_path)
    track = db_conn.execute("SELECT * FROM tracks").fetchone()
    client = TestClient(create_media_app(db_conn))

    resp = client.request("HEAD", f"/track/{track['id']}.flac")
    assert resp.status_code == 200
    assert resp.content == b""
    assert "content-length" in resp.headers


def test_offline_track_returns_503(db_conn, tmp_path):
    music, track = _seed(db_conn, tmp_path)
    db_conn.execute("UPDATE tracks SET online = 0 WHERE id = ?", (track["id"],))
    db_conn.commit()
    client = TestClient(create_media_app(db_conn))

    resp = client.get(f"/track/{track['id']}.flac")
    assert resp.status_code == 503


def test_unknown_track_returns_404(db_conn, tmp_path):
    _seed(db_conn, tmp_path)
    client = TestClient(create_media_app(db_conn))
    resp = client.get("/track/999999.flac")
    assert resp.status_code == 404


def test_artwork_thumbnail_served(db_conn, tmp_path):
    _seed(db_conn, tmp_path)
    art_hash = db_conn.execute("SELECT art_hash FROM tracks").fetchone()["art_hash"]
    client = TestClient(create_media_app(db_conn))

    resp = client.get(f"/art/{art_hash}/300.jpg")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"

    assert client.get(f"/art/{art_hash}/42.jpg").status_code == 404
    assert client.get("/art/doesnotexist/300.jpg").status_code == 404
