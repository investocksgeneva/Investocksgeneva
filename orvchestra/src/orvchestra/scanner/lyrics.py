"""Sidecar lyrics lookup: an ``.lrc`` (time-synced) or ``.txt`` (plain) file
sitting next to a track, same base filename -- the same convention as
`scanner/artwork.py`'s cover-art sidecars, and just as read-only.

An .lrc file's raw text (timestamps and all) is passed straight through;
the web app detects and parses the "[mm:ss.xx]" prefixes itself rather than
this module understanding the format.
"""

from __future__ import annotations

from pathlib import Path

_SIDECAR_SUFFIXES = (".lrc", ".txt")


def find_sidecar_lyrics(track_path: Path) -> str | None:
    for suffix in _SIDECAR_SUFFIXES:
        candidate = track_path.with_suffix(suffix)
        if candidate.is_file():
            try:
                return candidate.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
    return None


def get_lyrics(track_path: Path, embedded_lyrics: str | None) -> str | None:
    if embedded_lyrics:
        return embedded_lyrics
    return find_sidecar_lyrics(track_path)
