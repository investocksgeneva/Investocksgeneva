from __future__ import annotations

import shutil
from pathlib import Path

from orvchestra.db import repository as repo
from orvchestra.scanner.scan import scan_root
from orvchestra import paths as orv_paths

from conftest import make_flac


def test_unplugged_drive_marks_everything_offline_then_resumes(db_conn, tmp_path):
    drive = tmp_path / "external_drive"
    make_flac(drive / "a.flac", tags={"TITLE": "A"})
    make_flac(drive / "b.flac", tags={"TITLE": "B"})

    repo.add_root(db_conn, str(drive), "External", None)
    root = repo.get_root_by_path(db_conn, str(drive))
    stats = scan_root(db_conn, root, orv_paths.artwork_dir())
    assert stats.added == 2
    assert stats.reachable is True

    # Simulate the drive being unplugged: its mount point simply stops existing.
    moved_aside = tmp_path / "external_drive_ejected"
    shutil.move(str(drive), str(moved_aside))

    root = repo.get_root_by_path(db_conn, str(drive))
    stats = scan_root(db_conn, root, orv_paths.artwork_dir())

    assert stats.reachable is False
    root_row = repo.get_root_by_path(db_conn, str(drive))
    assert root_row["online"] == 0
    tracks = db_conn.execute("SELECT online FROM tracks").fetchall()
    assert all(t["online"] == 0 for t in tracks)
    assert len(tracks) == 2  # nothing deleted

    # Plug it back in.
    shutil.move(str(moved_aside), str(drive))
    root = repo.get_root_by_path(db_conn, str(drive))
    stats = scan_root(db_conn, root, orv_paths.artwork_dir())

    assert stats.reachable is True
    root_row = repo.get_root_by_path(db_conn, str(drive))
    assert root_row["online"] == 1
    tracks = db_conn.execute("SELECT online FROM tracks").fetchall()
    assert all(t["online"] == 1 for t in tracks)
    assert len(tracks) == 2  # still no duplicates
