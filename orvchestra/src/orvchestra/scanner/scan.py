"""Orchestrates one scan of one root: walk, diff against the DB, read tags
only for what actually changed, write, and reconcile offline files.

The single most important property here is that an unchanged file is never
opened: the (size, mtime) comparison against the DB is enough to skip it
entirely, which is what makes a rescan of an untouched 1 TB library fast and
guarantees we never touch bytes or mtimes we don't need to.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path

from orvchestra.db import repository as repo
from orvchestra.models import ScanStats
from orvchestra.scanner.artwork import cache_artwork, get_art_bytes
from orvchestra.scanner.lyrics import get_lyrics
from orvchestra.scanner.tags import read_tags
from orvchestra.scanner.volume import is_root_reachable
from orvchestra.scanner.walker import is_dataless, walk_audio_files

logger = logging.getLogger("orvchestra.scanner")


def scan_root(conn: sqlite3.Connection, root_row: sqlite3.Row, artwork_dir: Path) -> ScanStats:
    stats = ScanStats(root_path=root_row["path"])
    started = time.monotonic()

    if not is_root_reachable(root_row["path"]):
        stats.reachable = False
        if root_row["online"]:
            repo.mark_root_offline(conn, root_row["id"])
            conn.commit()
        stats.duration_seconds = time.monotonic() - started
        return stats

    if not root_row["online"]:
        repo.mark_root_online(conn, root_row["id"])

    root_path = Path(root_row["path"])
    existing = repo.load_existing_tracks(conn, root_row["id"])
    seen: set[str] = set()
    reactivate_ids: list[int] = []

    for abs_path, rel_path in walk_audio_files(root_path):
        stats.scanned += 1
        seen.add(rel_path)

        try:
            st = abs_path.stat()
        except OSError:
            stats.skipped_unreadable += 1
            continue

        prior = existing.get(rel_path)

        # Fast path: file identical to what's already recorded. Do not open
        # it, do not touch it, just note it's still here.
        if prior is not None and prior["size"] == st.st_size and prior["mtime"] == st.st_mtime:
            stats.unchanged += 1
            if not prior["online"]:
                reactivate_ids.append(prior["id"])
                stats.marked_online += 1
            continue

        if is_dataless(abs_path):
            stats.skipped_dataless += 1
            continue

        try:
            tags, picture = read_tags(abs_path)
        except Exception as exc:  # noqa: BLE001 - one bad/corrupt file must never abort the whole scan
            logger.warning("skipping unreadable file %s: %s", abs_path, exc)
            stats.skipped_unreadable += 1
            continue

        has_embedded_art = picture is not None
        art_bytes = get_art_bytes(abs_path, picture)
        art_hash = cache_artwork(conn, artwork_dir, art_bytes) if art_bytes else None
        tags.lyrics = get_lyrics(abs_path, tags.lyrics)

        if prior is None:
            repo.insert_track(conn, root_row["id"], rel_path, st.st_size, st.st_mtime, tags, art_hash, has_embedded_art)
            stats.added += 1
        else:
            repo.update_track(conn, prior["id"], st.st_size, st.st_mtime, tags, art_hash, has_embedded_art)
            stats.updated += 1
            if not prior["online"]:
                stats.marked_online += 1

    repo.mark_tracks_online_unchanged(conn, reactivate_ids)

    missing_ids = [row["id"] for rel_path, row in existing.items() if rel_path not in seen and row["online"]]
    if missing_ids:
        repo.mark_tracks_offline(conn, missing_ids)
        stats.marked_offline = len(missing_ids)

    if stats.added or stats.updated or stats.marked_offline or stats.marked_online:
        # Lets a DLNA control point notice its cached ContentDirectory
        # listings are stale via the SystemUpdateID state variable.
        repo.bump_system_update_id(conn)

    conn.commit()
    stats.duration_seconds = time.monotonic() - started
    return stats


def scan_all_roots(conn: sqlite3.Connection, artwork_dir: Path, only_path: str | None = None) -> list[ScanStats]:
    roots = repo.list_roots(conn)
    if only_path is not None:
        roots = [r for r in roots if r["path"] == only_path]
    return [scan_root(conn, root, artwork_dir) for root in roots]
