from __future__ import annotations

import os
import time
from pathlib import Path

from orvchestra.db import repository as repo
from orvchestra.scanner.scan import scan_root
from orvchestra import paths as orv_paths

from conftest import make_flac


def _scan(db_conn, music_dir: Path):
    root = repo.get_root_by_path(db_conn, str(music_dir))
    if root is None:
        repo.add_root(db_conn, str(music_dir), None, None)
        root = repo.get_root_by_path(db_conn, str(music_dir))
    return scan_root(db_conn, root, orv_paths.artwork_dir())


def test_rescan_unchanged_library_touches_nothing(db_conn, tmp_path):
    music = tmp_path / "music"
    make_flac(music / "a.flac", tags={"TITLE": "A"})
    make_flac(music / "b.flac", tags={"TITLE": "B"})

    first = _scan(db_conn, music)
    assert first.added == 2

    second = _scan(db_conn, music)
    assert second.added == 0
    assert second.updated == 0
    assert second.unchanged == 2


def test_changed_file_is_reread_others_left_alone(db_conn, tmp_path):
    music = tmp_path / "music"
    a = make_flac(music / "a.flac", tags={"TITLE": "A original"})
    make_flac(music / "b.flac", tags={"TITLE": "B"})
    _scan(db_conn, music)

    # Simulate a real re-tag: mutagen rewrites the file, changing size/mtime.
    import mutagen.flac

    audio = mutagen.flac.FLAC(str(a))
    audio["TITLE"] = "A retagged"
    audio.save()

    stats = _scan(db_conn, music)
    assert stats.updated == 1
    assert stats.unchanged == 1

    row = db_conn.execute("SELECT title FROM tracks WHERE rel_path = 'a.flac'").fetchone()
    assert row["title"] == "A retagged"


def test_deleted_file_marked_offline_not_removed(db_conn, tmp_path):
    music = tmp_path / "music"
    a = make_flac(music / "a.flac", tags={"TITLE": "A"})
    _scan(db_conn, music)

    track_id = db_conn.execute("SELECT id FROM tracks WHERE rel_path = 'a.flac'").fetchone()["id"]

    os.remove(a)
    stats = _scan(db_conn, music)

    assert stats.marked_offline == 1
    row = db_conn.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()
    assert row is not None
    assert row["online"] == 0


def test_restored_file_comes_back_online_without_duplicate_row(db_conn, tmp_path):
    music = tmp_path / "music"
    a = make_flac(music / "a.flac", tags={"TITLE": "A"})
    _scan(db_conn, music)
    track_id = db_conn.execute("SELECT id FROM tracks").fetchone()["id"]

    data = a.read_bytes()
    os.remove(a)
    _scan(db_conn, music)

    a.write_bytes(data)
    # Ensure the recreated file's mtime clearly differs so it's treated as "new to us again".
    os.utime(a, None)
    stats = _scan(db_conn, music)

    assert db_conn.execute("SELECT COUNT(*) AS n FROM tracks").fetchone()["n"] == 1
    row = db_conn.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()
    assert row["online"] == 1
    assert stats.updated + stats.unchanged >= 1
