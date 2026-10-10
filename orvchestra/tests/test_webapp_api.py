from __future__ import annotations

from starlette.testclient import TestClient

from orvchestra.db import repository as repo
from orvchestra.dlna import ids
from orvchestra.playback.keepawake import KeepAwakeController
from orvchestra.playback.service import PlaybackService
from orvchestra.scanner.scan import scan_root
from orvchestra.webapp.app import create_app
from orvchestra import paths as orv_paths

from conftest import make_flac, _tiny_png

BASE = "http://192.168.1.50:8347"


def _seed(db_conn, tmp_path):
    music = tmp_path / "music"
    make_flac(
        music / "Artist A" / "Album A" / "01.flac",
        tags={
            "TITLE": "Song One", "ARTIST": "Artist A", "ALBUMARTIST": "Artist A", "ALBUM": "Album A",
            "TRACKNUMBER": "1", "DATE": "2020", "GENRE": "Rock",
        },
        picture_bytes=_tiny_png(),
    )
    make_flac(
        music / "Artist A" / "Album A" / "02.flac",
        tags={
            "TITLE": "Song Two", "ARTIST": "Artist A", "ALBUMARTIST": "Artist A", "ALBUM": "Album A",
            "TRACKNUMBER": "2", "DATE": "2020", "GENRE": "Rock",
        },
    )
    repo.add_root(db_conn, str(music), None, None)
    root = repo.get_root_by_path(db_conn, str(music))
    scan_root(db_conn, root, orv_paths.artwork_dir())


def _client(db_conn) -> TestClient:
    playback = PlaybackService(db_conn, BASE, KeepAwakeController())
    app = create_app(db_conn, BASE, playback)
    return TestClient(app)


def test_home_lists_recently_added(db_conn, tmp_path):
    _seed(db_conn, tmp_path)
    client = _client(db_conn)
    resp = client.get("/api/home")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["recently_added"]) == 1
    assert body["recently_added"][0]["album"] == "Album A"
    assert body["recently_played"] == []
    assert body["rediscover"] == []


def test_search_finds_track_album_and_artist(db_conn, tmp_path):
    _seed(db_conn, tmp_path)
    client = _client(db_conn)

    resp = client.get("/api/search", params={"q": "Song One"})
    assert resp.status_code == 200
    body = resp.json()
    assert any(t["title"] == "Song One" for t in body["tracks"])

    resp = client.get("/api/search", params={"q": "Artist"})
    assert any(a["artist"] == "Artist A" for a in resp.json()["artists"])

    resp = client.get("/api/search", params={"q": "Album A"})
    assert any(a["album"] == "Album A" for a in resp.json()["albums"])

    assert client.get("/api/search", params={"q": ""}).json() == {"artists": [], "albums": [], "tracks": []}


def test_artist_and_album_detail(db_conn, tmp_path):
    _seed(db_conn, tmp_path)
    client = _client(db_conn)

    artist_id = ids.artist_id("Artist A")
    resp = client.get(f"/api/artists/{artist_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["artist"] == "Artist A"
    assert len(body["albums"]) == 1

    album_id = body["albums"][0]["id"]
    resp = client.get(f"/api/albums/{album_id}")
    assert resp.status_code == 200
    album = resp.json()
    assert [t["title"] for t in album["tracks"]] == ["Song One", "Song Two"]
    assert album["tracks"][0]["art_url_large"].startswith(BASE)

    assert client.get(f"/api/artists/{ids.artist_id('Nobody')}").status_code == 404


def test_genres_and_years(db_conn, tmp_path):
    _seed(db_conn, tmp_path)
    client = _client(db_conn)

    genres = client.get("/api/genres").json()
    assert genres == [{"id": ids.genre_id("Rock"), "name": "Rock"}]
    genre_detail = client.get(f"/api/genres/{ids.genre_id('Rock')}").json()
    assert len(genre_detail["tracks"]) == 2

    years = client.get("/api/years").json()
    assert years == [{"id": ids.year_id(2020), "year": 2020}]
    year_detail = client.get("/api/years/2020").json()
    assert len(year_detail["albums"]) == 1


def test_playlists_endpoint_is_empty_shape(db_conn, tmp_path):
    _seed(db_conn, tmp_path)
    client = _client(db_conn)
    assert client.get("/api/playlists").json() == []


def test_outputs_always_include_this_device(db_conn, tmp_path):
    _seed(db_conn, tmp_path)
    client = _client(db_conn)
    outputs = client.get("/api/outputs").json()
    assert outputs == [{"id": "this-device", "name": "This device", "kind": "browser", "selected": True}]

    assert client.post("/api/outputs/bogus/select").status_code == 404


def test_queue_and_playback_endpoints_against_this_device(db_conn, tmp_path):
    _seed(db_conn, tmp_path)
    client = _client(db_conn)
    track_ids = [r["id"] for r in db_conn.execute("SELECT id FROM tracks ORDER BY rel_path")]

    resp = client.post("/api/queue/play", json={"track_ids": track_ids, "start_index": 0})
    assert resp.status_code == 200
    assert resp.json()["track"]["title"] == "Song One"

    resp = client.get("/api/queue")
    assert [t["title"] for t in resp.json()["tracks"]] == ["Song One", "Song Two"]
    assert resp.json()["position"] == 0

    resp = client.post("/api/playback/next")
    assert resp.json()["track"]["title"] == "Song Two"

    resp = client.post("/api/playback/browser-state", json={"playing": True})
    assert resp.status_code == 200

    assert client.post("/api/queue/play", json={"track_ids": []}).status_code == 400


def test_shuffle_and_repeat_endpoints(db_conn, tmp_path):
    _seed(db_conn, tmp_path)
    client = _client(db_conn)
    track_ids = [r["id"] for r in db_conn.execute("SELECT id FROM tracks ORDER BY rel_path")]
    client.post("/api/queue/play", json={"track_ids": track_ids, "start_index": 0})

    resp = client.get("/api/queue")
    assert resp.json()["shuffle"] is False
    assert resp.json()["repeat_mode"] == "off"

    resp = client.post("/api/playback/shuffle", json={"enabled": True})
    assert resp.status_code == 200
    assert resp.json()["shuffle"] is True
    assert client.get("/api/queue").json()["shuffle"] is True

    resp = client.post("/api/playback/repeat", json={"mode": "all"})
    assert resp.status_code == 200
    assert resp.json()["repeat_mode"] == "all"
    assert client.get("/api/queue").json()["repeat_mode"] == "all"

    assert client.post("/api/playback/repeat", json={"mode": "bogus"}).status_code == 400


def test_stream_and_art_still_reachable_on_the_combined_app(db_conn, tmp_path):
    _seed(db_conn, tmp_path)
    client = _client(db_conn)
    track = db_conn.execute("SELECT * FROM tracks WHERE title = 'Song One'").fetchone()

    resp = client.get(f"/track/{track['id']}.flac")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/flac"


def test_spa_fallback_serves_index_or_a_clear_error(db_conn, tmp_path, monkeypatch):
    _seed(db_conn, tmp_path)
    monkeypatch.setenv("ORVCHESTRA_WEB_DIST", str(tmp_path / "no-such-dist"))
    client = _client(db_conn)

    resp = client.get("/some/client/route")
    assert resp.status_code == 404
    assert "hasn't been built" in resp.text


def test_app_lifespan_starts_and_stops_background_discovery(db_conn, tmp_path, monkeypatch):
    _seed(db_conn, tmp_path)

    async def no_renderers():
        return []

    import orvchestra.playback.service as service_module

    monkeypatch.setattr(service_module, "discover_renderers", lambda: no_renderers())

    playback = PlaybackService(db_conn, BASE, KeepAwakeController())
    app = create_app(db_conn, BASE, playback)

    with TestClient(app) as client:
        resp = client.get("/api/home")
        assert resp.status_code == 200
    # Exiting the `with` block runs the lifespan's shutdown path (cancels
    # the discovery task, calls playback.shutdown()) with no error raised.


def test_spa_fallback_rejects_path_traversal(db_conn, tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>ok</html>")
    secret = tmp_path / "secret.txt"
    secret.write_text("do not serve me")
    monkeypatch.setenv("ORVCHESTRA_WEB_DIST", str(dist))

    _seed(db_conn, tmp_path)
    client = _client(db_conn)

    resp = client.get("/../secret.txt")
    # Either blocked outright or resolved harmlessly back within dist and
    # falls through to index.html -- either way, the secret must never be served.
    assert "do not serve me" not in resp.text
