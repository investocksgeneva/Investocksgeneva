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


def web_dist_dir() -> Path:
    """Where the built PWA (`web/dist`, from `npm run build`) lives.

    Defaults to the `web/dist` folder next to this checkout's `pyproject.toml`
    -- fine for running from a source checkout via `uv run`/`orvchestra
    serve`, which is the only way this is meant to be run in Phase 3. This
    is not resolved as installed package data, so it won't survive a `pip
    install` of a built wheel; revisit if Orvchestra ever needs to be
    distributed that way.
    """
    override = os.environ.get("ORVCHESTRA_WEB_DIST")
    if override:
        return Path(override).expanduser()
    # src/orvchestra/paths.py -> src/orvchestra -> src -> <project root>
    project_root = Path(__file__).resolve().parents[2]
    return project_root / "web" / "dist"
