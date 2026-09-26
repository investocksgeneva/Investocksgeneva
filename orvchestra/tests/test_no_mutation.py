"""The one non-negotiable acceptance test: scanning must never change a
single byte or the mtime of any file in the music library, on a full scan
or an incremental one."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from orvchestra.db import repository as repo
from orvchestra.scanner.scan import scan_root
from orvchestra import paths as orv_paths

from conftest import make_flac, make_mp3, make_wav, _tiny_png


def _fingerprint(root: Path) -> dict[str, tuple[str, float, int]]:
    out = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            p = Path(dirpath) / name
            st = p.stat()
            out[str(p)] = (hashlib.sha256(p.read_bytes()).hexdigest(), st.st_mtime, st.st_size)
    return out


def test_scan_never_mutates_music_files(db_conn, tmp_path):
    music = tmp_path / "music"
    make_flac(
        music / "Artist" / "Album" / "01.flac",
        tags={"TITLE": "One", "ALBUM": "Album", "ARTIST": "Artist"},
        picture_bytes=_tiny_png(),
    )
    make_mp3(music / "Artist2" / "02.mp3", tags={"title": "Two"}, picture_bytes=_tiny_png())
    make_wav(music / "Artist3" / "03.wav")

    before = _fingerprint(music)
    assert len(before) == 3

    repo.add_root(db_conn, str(music), None, None)
    root = repo.get_root_by_path(db_conn, str(music))

    # Full scan (everything new).
    scan_root(db_conn, root, orv_paths.artwork_dir())
    after_full = _fingerprint(music)
    assert after_full == before

    # Incremental rescan (everything unchanged) — the fast path that must
    # never open the files at all.
    scan_root(db_conn, root, orv_paths.artwork_dir())
    after_incremental = _fingerprint(music)
    assert after_incremental == before
