from __future__ import annotations

from pathlib import Path

from orvchestra.db import repository as repo
from orvchestra.scanner.scan import scan_root
from orvchestra import paths as orv_paths

from conftest import make_flac, make_mp3, make_wav


def _add_and_scan(db_conn, music_dir: Path):
    root_id = repo.add_root(db_conn, str(music_dir), None, None)
    root = repo.get_root_by_path(db_conn, str(music_dir))
    stats = scan_root(db_conn, root, orv_paths.artwork_dir())
    return root_id, stats


def test_scan_discovers_tracks_and_reads_tags(db_conn, tmp_path):
    music = tmp_path / "music"
    make_flac(
        music / "Artist A" / "Album A" / "01 - Song One.flac",
        tags={
            "TITLE": "Song One",
            "ARTIST": "Artist A",
            "ALBUMARTIST": "Artist A",
            "ALBUM": "Album A",
            "TRACKNUMBER": "1/3",
            "DISCNUMBER": "1/1",
            "DATE": "2019-03-01",
            "GENRE": "Jazz",
        },
    )

    _, stats = _add_and_scan(db_conn, music)

    assert stats.scanned == 1
    assert stats.added == 1
    assert stats.updated == 0

    row = db_conn.execute("SELECT * FROM tracks").fetchone()
    assert row["title"] == "Song One"
    assert row["artist"] == "Artist A"
    assert row["album"] == "Album A"
    assert row["track_number"] == 1
    assert row["track_total"] == 3
    assert row["disc_number"] == 1
    assert row["year"] == 2019
    assert row["genre"] == "Jazz"
    assert row["codec"] == "FLAC"
    assert row["sample_rate"] == 44100
    assert row["bit_depth"] == 16
    assert row["channels"] == 2
    assert row["online"] == 1


def test_scan_reads_mp3_and_wav(db_conn, tmp_path):
    music = tmp_path / "music"
    make_mp3(music / "b.mp3", tags={"title": "B Song", "artist": "B Artist"})
    make_wav(music / "c.wav")

    _, stats = _add_and_scan(db_conn, music)

    assert stats.scanned == 2
    assert stats.added == 2
    codecs = {r["codec"] for r in db_conn.execute("SELECT codec FROM tracks")}
    assert codecs == {"MP3", "WAV"}


def test_skips_hidden_and_system_files(db_conn, tmp_path):
    music = tmp_path / "music"
    make_flac(music / "Artist" / "Album" / "01 - Real.flac", tags={"TITLE": "Real"})

    # AppleDouble resource fork sidecar mutagen would choke on.
    (music / "Artist" / "Album" / "._01 - Real.flac").parent.mkdir(parents=True, exist_ok=True)
    (music / "Artist" / "Album" / "._01 - Real.flac").write_bytes(b"\x00\x05junk")
    (music / "Artist" / "Album" / ".DS_Store").write_bytes(b"junk")
    (music / ".Trashes").mkdir(parents=True, exist_ok=True)
    make_flac(music / ".Trashes" / "deleted.flac", tags={"TITLE": "Should not appear"})

    _, stats = _add_and_scan(db_conn, music)

    assert stats.scanned == 1
    titles = [r["title"] for r in db_conn.execute("SELECT title FROM tracks")]
    assert titles == ["Real"]


def test_compilation_groups_under_various_artists(db_conn, tmp_path):
    music = tmp_path / "music"
    make_flac(
        music / "Compilation" / "01.flac",
        tags={"TITLE": "T1", "ARTIST": "Artist X", "ALBUM": "Now That's What I Call Tests", "COMPILATION": "1"},
    )
    make_flac(
        music / "Compilation" / "02.flac",
        tags={"TITLE": "T2", "ARTIST": "Artist Y", "ALBUM": "Now That's What I Call Tests", "COMPILATION": "1"},
    )

    _add_and_scan(db_conn, music)

    albums = db_conn.execute("SELECT * FROM v_albums").fetchall()
    assert len(albums) == 1
    assert albums[0]["album_artist"] == "Various Artists"
    assert albums[0]["track_count"] == 2


def test_multidisc_album_counts_as_one_album(db_conn, tmp_path):
    music = tmp_path / "music"
    for disc, track, title in [(1, 1, "D1T1"), (1, 2, "D1T2"), (2, 1, "D2T1")]:
        make_flac(
            music / "Artist" / "Big Album" / f"{disc}-{track:02d}.flac",
            tags={
                "TITLE": title,
                "ARTIST": "Artist",
                "ALBUMARTIST": "Artist",
                "ALBUM": "Big Album",
                "DISCNUMBER": str(disc),
                "TRACKNUMBER": str(track),
            },
        )

    _add_and_scan(db_conn, music)

    albums = db_conn.execute("SELECT * FROM v_albums WHERE album = 'Big Album'").fetchall()
    assert len(albums) == 1
    assert albums[0]["track_count"] == 3
    assert albums[0]["disc_count"] == 2


def test_dataless_file_is_skipped(db_conn, tmp_path, monkeypatch):
    music = tmp_path / "music"
    make_flac(music / "cloud.flac", tags={"TITLE": "Cloud Only"})

    import orvchestra.scanner.scan as scan_module

    monkeypatch.setattr(scan_module, "is_dataless", lambda path: True)

    _, stats = _add_and_scan(db_conn, music)

    assert stats.skipped_dataless == 1
    assert db_conn.execute("SELECT COUNT(*) AS n FROM tracks").fetchone()["n"] == 0


def test_corrupt_file_does_not_abort_scan(db_conn, tmp_path):
    music = tmp_path / "music"
    (music).mkdir(parents=True, exist_ok=True)
    (music / "corrupt.flac").write_bytes(b"not actually a flac file")
    make_flac(music / "good.flac", tags={"TITLE": "Good"})

    _, stats = _add_and_scan(db_conn, music)

    assert stats.scanned == 2
    assert stats.added == 1
    assert stats.skipped_unreadable == 1
    titles = [r["title"] for r in db_conn.execute("SELECT title FROM tracks")]
    assert titles == ["Good"]
