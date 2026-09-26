"""SQLite connection setup: WAL mode, FTS5, and sane defaults for a
single-process app that many HTTP requests will eventually hit concurrently
(Phase 2+)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from orvchestra.db.schema import apply_schema


def connect(path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    apply_schema(conn)
    return conn
