"""Where Orvchestra keeps its own state.

Everything Orvchestra writes (database, artwork cache, logs) lives under a
single app-data directory, never inside a music folder. `ORVCHESTRA_DATA_DIR`
overrides the default and exists mainly so tests never touch the real
`~/Library/Application Support/Orvchestra` on a developer's machine.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def app_data_dir() -> Path:
    override = os.environ.get("ORVCHESTRA_DATA_DIR")
    if override:
        base = Path(override).expanduser()
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "Orvchestra"
    else:
        # XDG layout so the same code runs unchanged on a future Linux box
        # (constraint: portable to Linux with no code changes).
        xdg = os.environ.get("XDG_DATA_HOME")
        base = Path(xdg).expanduser() / "orvchestra" if xdg else Path.home() / ".local" / "share" / "orvchestra"
    base.mkdir(parents=True, exist_ok=True)
    return base


def db_path() -> Path:
    return app_data_dir() / "library.db"


def artwork_dir() -> Path:
    path = app_data_dir() / "artwork"
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    path = app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path
