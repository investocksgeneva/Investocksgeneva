from __future__ import annotations

from starlette.testclient import TestClient

from orvchestra.db import repository as repo
from orvchestra.playback.keepawake import KeepAwakeController
from orvchestra.playback.service import PlaybackService
from orvchestra.scanner.scan import scan_root
from orvchestra.webapp.app import create_app
from orvchestra import paths as orv_paths

from conftest import make_flac

BASE = "http://192.168.1.50:8347"


def _seed(db_conn, tmp_path):
    music = tmp_path / "music"
    make_flac(
        music / "Artist A" / "Album A" / "01.flac",
        tags={"TITLE": "Song One", "ARTIST": "Artist A", "ALBUMARTIST": "Artist A", "ALBUM": "Album A", "GENRE": "Rock", "DATE": "2020"},
    )
    make_flac(
        music / "Artist A" / "Album A" / "02.flac",
        tags={"TITLE": "Song Two", "ARTIST": "Artist A", "ALBUMARTIST": "Artist A", "ALBUM": "Album A", "GENRE": "Rock", "DATE": "2020"},
    )
    make_flac(
        music / "Artist B" / "Album B" / "01.flac",
        tags={"TITLE": "Other Song", "ARTIST": "Artist B", "ALBUMARTIST": "Artist B", "ALBUM": "Album B", "GENRE": "Jazz", "DATE": "2015"},
    )
    repo.add_root(db_conn, str(music), None, None)
    root = repo.get_root_by_path(db_conn, str(music))
    scan_root(db_conn, root, orv_paths.artwork_dir())
    rows = db_conn.execute("SELECT id, title FROM tracks ORDER BY rel_path").fetchall()
    return {r["title"]: r["id"] for r in rows}


def _client(db_conn) -> TestClient:
    playback = PlaybackService(db_conn, BASE, KeepAwakeController())
    app = create_app(db_conn, BASE, playback)
    return TestClient(app)


def test_stats_summary_and_top_endpoints(db_conn, tmp_path):
    ids_by_title = _seed(db_conn, tmp_path)
    now = repo.iso_now_minus_days(0)
    repo.record_play(db_conn, ids_by_title["Song One"], now, 200, "wiim")
    repo.record_play(db_conn, ids_by_title["Song One"], now, 200, "wiim")
    repo.record_play(db_conn, ids_by_title["Other Song"], now, 100, "browser")

    client = _client(db_conn)

    resp = client.get("/api/stats/summary", params={"period": "all"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["play_count"] == 3
    assert body["total_seconds"] == 500
    assert {row["codec"] for row in body["format_mix"]} == {"FLAC"}

    resp = client.get("/api/stats/top", params={"kind": "tracks", "period": "all"})
    assert resp.json()[0]["title"] == "Song One"

    resp = client.get("/api/stats/top", params={"kind": "artists", "period": "all"})
    assert resp.json()[0]["artist"] == "Artist A"

    resp = client.get("/api/stats/top", params={"kind": "albums", "period": "all"})
    top_albums = resp.json()
    assert top_albums[0]["album"] == "Album A"
    assert top_albums[0]["play_count"] == 2
    assert "art_url_small" in top_albums[0]

    assert client.get("/api/stats/top", params={"kind": "bogus"}).status_code == 400
    assert client.get("/api/stats/summary", params={"period": "bogus"}).status_code == 400


def test_stats_encore_and_wrapped(db_conn, tmp_path):
    ids_by_title = _seed(db_conn, tmp_path)
    old = "2001-06-15T00:00:00.000Z"
    repo.record_play(db_conn, ids_by_title["Song One"], old, 200, "wiim")

    client = _client(db_conn)

    resp = client.get("/api/stats/encore", params={"months": 12})
    assert resp.status_code == 200
    assert resp.json()[0]["album"] == "Album A"

    resp = client.get("/api/stats/wrapped/2001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["year"] == 2001
    assert body["play_count"] == 1
    assert body["top_tracks"][0]["title"] == "Song One"

    resp = client.get("/api/stats/wrapped/1999")
    assert resp.json()["play_count"] == 0


def test_rating_endpoint(db_conn, tmp_path):
    ids_by_title = _seed(db_conn, tmp_path)
    track_id = ids_by_title["Song One"]
    client = _client(db_conn)

    resp = client.post(f"/api/tracks/{track_id}/rating", json={"rating": 4})
    assert resp.status_code == 200
    assert resp.json() == {"id": track_id, "rating": 4}

    album = client.get(
        f"/api/albums/{[t for t in client.get('/api/albums').json() if t['album'] == 'Album A'][0]['id']}"
    ).json()
    assert next(t["rating"] for t in album["tracks"] if t["id"] == track_id) == 4

    assert client.post(f"/api/tracks/{track_id}/rating", json={"rating": 6}).status_code == 422
    assert client.post("/api/tracks/999999/rating", json={"rating": 3}).status_code == 404

    resp = client.post(f"/api/tracks/{track_id}/rating", json={"rating": None})
    assert resp.json()["rating"] is None


def test_home_recently_played_and_rediscover(db_conn, tmp_path):
    ids_by_title = _seed(db_conn, tmp_path)
    old = "2001-01-01T00:00:00.000Z"
    recent = repo.iso_now_minus_days(0)
    repo.record_play(db_conn, ids_by_title["Song One"], old, 200, "wiim")  # Album A: stale
    repo.record_play(db_conn, ids_by_title["Other Song"], recent, 200, "wiim")  # Album B: fresh

    client = _client(db_conn)
    home = client.get("/api/home").json()

    assert home["recently_played"][0]["album"] == "Album B"
    assert home["rediscover"][0]["album"] == "Album A"


def test_smart_playlist_lifecycle(db_conn, tmp_path):
    ids_by_title = _seed(db_conn, tmp_path)
    repo.set_track_rating(db_conn, ids_by_title["Song One"], 5)
    repo.set_track_rating(db_conn, ids_by_title["Song Two"], 2)

    client = _client(db_conn)

    resp = client.post(
        "/api/playlists",
        json={"name": "High-rated Rock", "description": "auto", "rules": {"genre": "Rock", "min_rating": 4}},
    )
    assert resp.status_code == 200
    playlist = resp.json()
    assert playlist["is_smart"] is True
    assert playlist["rules"]["genre"] == "Rock"
    playlist_id = playlist["id"]

    resp = client.get("/api/playlists")
    assert any(p["id"] == playlist_id for p in resp.json())

    resp = client.get(f"/api/playlists/{playlist_id}")
    assert [t["title"] for t in resp.json()["tracks"]] == ["Song One"]

    resp = client.delete(f"/api/playlists/{playlist_id}")
    assert resp.status_code == 200
    assert client.get(f"/api/playlists/{playlist_id}").status_code == 404
    assert client.delete(f"/api/playlists/{playlist_id}").status_code == 404
