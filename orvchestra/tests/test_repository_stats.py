from __future__ import annotations

from orvchestra.db import repository as repo
from orvchestra.scanner.scan import scan_root
from orvchestra import paths as orv_paths

from conftest import make_flac


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


def test_top_tracks_artists_albums_rank_by_play_count(db_conn, tmp_path):
    ids_by_title = _seed(db_conn, tmp_path)
    now = repo.iso_now_minus_days(0)

    repo.record_play(db_conn, ids_by_title["Song One"], now, 200, "wiim")
    repo.record_play(db_conn, ids_by_title["Song One"], now, 200, "wiim")
    repo.record_play(db_conn, ids_by_title["Song Two"], now, 200, "browser")
    repo.record_play(db_conn, ids_by_title["Other Song"], now, 200, "wiim")

    top_tracks = repo.top_tracks(db_conn, since_iso=None, limit=10)
    assert top_tracks[0]["title"] == "Song One"
    assert top_tracks[0]["play_count"] == 2

    top_artists = repo.top_artists(db_conn, since_iso=None, limit=10)
    assert top_artists[0]["artist"] == "Artist A"
    assert top_artists[0]["play_count"] == 3

    top_albums = repo.top_albums(db_conn, since_iso=None, limit=10)
    assert top_albums[0]["album"] == "Album A"
    assert top_albums[0]["play_count"] == 3


def test_period_filtering_excludes_old_plays(db_conn, tmp_path):
    ids_by_title = _seed(db_conn, tmp_path)
    old = "2001-01-01T00:00:00.000Z"
    recent = repo.iso_now_minus_days(0)

    repo.record_play(db_conn, ids_by_title["Song One"], old, 200, "wiim")
    repo.record_play(db_conn, ids_by_title["Song Two"], recent, 200, "wiim")

    since = repo.iso_now_minus_days(7)
    recent_tracks = repo.top_tracks(db_conn, since_iso=since, limit=10)
    assert [t["title"] for t in recent_tracks] == ["Song Two"]

    all_time = repo.top_tracks(db_conn, since_iso=None, limit=10)
    assert len(all_time) == 2


def test_listening_summary_and_format_mix(db_conn, tmp_path):
    ids_by_title = _seed(db_conn, tmp_path)
    now = repo.iso_now_minus_days(0)
    repo.record_play(db_conn, ids_by_title["Song One"], now, 120, "wiim")
    repo.record_play(db_conn, ids_by_title["Other Song"], now, 60, "browser")

    summary = repo.listening_summary(db_conn, since_iso=None)
    assert summary["play_count"] == 2
    assert summary["total_seconds"] == 180

    mix = repo.format_mix_played(db_conn, since_iso=None)
    assert {row["codec"] for row in mix} == {"FLAC"}


def test_recently_played_and_encore_albums(db_conn, tmp_path):
    ids_by_title = _seed(db_conn, tmp_path)
    old = "2001-01-01T00:00:00.000Z"
    recent = repo.iso_now_minus_days(0)

    repo.record_play(db_conn, ids_by_title["Song One"], old, 200, "wiim")  # Album A last played long ago
    repo.record_play(db_conn, ids_by_title["Other Song"], recent, 200, "wiim")  # Album B played recently

    recently_played = repo.recently_played_albums(db_conn, limit=10)
    assert recently_played[0]["album"] == "Album B"

    cutoff = repo.iso_now_minus_days(365)
    encore = repo.encore_albums(db_conn, cutoff, limit=10)
    assert [row["album"] for row in encore] == ["Album A"]


def test_set_track_rating(db_conn, tmp_path):
    ids_by_title = _seed(db_conn, tmp_path)
    track_id = ids_by_title["Song One"]
    assert db_conn.execute("SELECT rating FROM tracks WHERE id = ?", (track_id,)).fetchone()["rating"] is None

    repo.set_track_rating(db_conn, track_id, 4)
    assert db_conn.execute("SELECT rating FROM tracks WHERE id = ?", (track_id,)).fetchone()["rating"] == 4

    repo.set_track_rating(db_conn, track_id, None)
    assert db_conn.execute("SELECT rating FROM tracks WHERE id = ?", (track_id,)).fetchone()["rating"] is None


def test_smart_playlist_crud_and_evaluation(db_conn, tmp_path):
    ids_by_title = _seed(db_conn, tmp_path)
    repo.set_track_rating(db_conn, ids_by_title["Song One"], 5)
    repo.set_track_rating(db_conn, ids_by_title["Song Two"], 2)

    playlist_id = repo.create_smart_playlist(
        db_conn, "High-rated Rock", "auto", {"genre": "Rock", "min_rating": 4, "sort": "title"}
    )
    playlist = repo.get_playlist(db_conn, playlist_id)
    assert playlist["is_smart"] == 1
    assert playlist["name"] == "High-rated Rock"

    import json

    rules = json.loads(playlist["rules_json"])
    tracks = repo.evaluate_smart_playlist(db_conn, rules)
    assert [t["title"] for t in tracks] == ["Song One"]

    assert repo.delete_playlist(db_conn, playlist_id) is True
    assert repo.get_playlist(db_conn, playlist_id) is None
    assert repo.delete_playlist(db_conn, playlist_id) is False


def test_evaluate_smart_playlist_year_range_and_play_count(db_conn, tmp_path):
    ids_by_title = _seed(db_conn, tmp_path)
    now = repo.iso_now_minus_days(0)
    repo.record_play(db_conn, ids_by_title["Song One"], now, 200, "wiim")
    repo.record_play(db_conn, ids_by_title["Song One"], now, 200, "wiim")

    tracks = repo.evaluate_smart_playlist(db_conn, {"year_min": 2018, "year_max": 2022})
    assert {t["title"] for t in tracks} == {"Song One", "Song Two"}

    tracks = repo.evaluate_smart_playlist(db_conn, {"min_play_count": 2})
    assert [t["title"] for t in tracks] == ["Song One"]

    tracks = repo.evaluate_smart_playlist(db_conn, {"last_played_after_days": 7})
    assert [t["title"] for t in tracks] == ["Song One"]
