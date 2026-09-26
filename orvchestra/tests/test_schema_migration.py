"""Proves the Phase 4 `_ensure_column` migration actually works against a
database that predates it -- not just a freshly-created one, which would
never exercise the ALTER TABLE path at all.

The stand-in for "a real user's Phase 1-3 database" is built from the
current `schema.DDL` directly (bypassing `apply_schema`, which is the thing
under test): `DDL` itself never mentions `rating`/`is_smart`/`rules_json` --
those three columns only ever get added by `_ensure_column` -- so running
just `DDL` reproduces exactly the pre-Phase-4 shape without hand-maintaining
a second copy of the schema that would drift out of sync with the real one.
"""

from __future__ import annotations

import sqlite3

from orvchestra.db.connection import connect
from orvchestra.db.schema import DDL


def _pre_phase4_database(path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(DDL)
    conn.execute("INSERT INTO roots (id, path, online) VALUES (1, '/music', 1)")
    conn.execute(
        "INSERT INTO tracks (id, root_id, rel_path, size, mtime, title) VALUES (1, 1, 'a.flac', 100, 0, 'Existing Track')"
    )
    conn.execute("INSERT INTO playlists (id, name) VALUES (1, 'Existing Playlist')")
    conn.commit()
    conn.close()


def test_connect_adds_phase4_columns_to_a_pre_existing_database(tmp_path):
    db_path = tmp_path / "library.db"
    _pre_phase4_database(db_path)

    conn = connect(db_path)

    # The migration must not have touched pre-existing rows.
    row = conn.execute("SELECT * FROM tracks WHERE id = 1").fetchone()
    assert row["title"] == "Existing Track"
    assert row["rating"] is None

    playlist = conn.execute("SELECT * FROM playlists WHERE id = 1").fetchone()
    assert playlist["name"] == "Existing Playlist"
    assert playlist["is_smart"] == 0
    assert playlist["rules_json"] is None

    # And the columns are actually usable afterward, not just present.
    conn.execute("UPDATE tracks SET rating = 5 WHERE id = 1")
    conn.execute("UPDATE playlists SET is_smart = 1, rules_json = '{}' WHERE id = 1")
    conn.commit()
    assert conn.execute("SELECT rating FROM tracks WHERE id = 1").fetchone()["rating"] == 5


def test_connect_twice_is_idempotent(tmp_path):
    db_path = tmp_path / "library.db"
    _pre_phase4_database(db_path)

    connect(db_path).close()
    conn = connect(db_path)  # must not raise "duplicate column name"
    rows = conn.execute("SELECT rating FROM tracks").fetchall()
    assert len(rows) == 1 and rows[0]["rating"] is None
