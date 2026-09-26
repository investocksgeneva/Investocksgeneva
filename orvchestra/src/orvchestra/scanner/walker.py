"""Walks a music root, yielding candidate audio files while pruning
everything the library has no business touching."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

AUDIO_EXTENSIONS = {".flac", ".m4a", ".alac", ".mp3", ".wav", ".wave", ".dsf", ".dff"}

# Folders that show up on real drives (macOS metadata, Windows/exFAT
# leftovers from an external drive that's been on both) but never contain
# music worth indexing.
SKIP_DIR_NAMES = {
    ".Trashes", ".Spotlight-V100", ".fseventsd", ".TemporaryItems",
    ".DocumentRevisions-V100", ".apdisk", "$RECYCLE.BIN", "System Volume Information",
}

# macOS's dataless-file flag (SF_DATALESS in <sys/stat.h>). Not exposed as a
# named constant in Python's `stat` module, so we hardcode the bit value.
# `st_flags` only exists on BSD-family platforms (macOS); on Linux
# `os.stat_result` simply has no such attribute, so this check is a no-op
# there — which is exactly the portability behaviour we want.
_SF_DATALESS = 0x40000000


def is_hidden(name: str) -> bool:
    # Catches both plain dotfiles (.DS_Store) and AppleDouble sidecars
    # (._SomeTrack.flac) that macOS writes next to every file on
    # non-HFS/APFS volumes (exFAT external drives, network shares).
    return name.startswith(".")


def is_dataless(path: Path) -> bool:
    """True for an iCloud/cloud-storage placeholder that has no local bytes.

    We must never trigger a download by opening one of these, so this check
    has to work from stat() metadata alone.
    """
    try:
        st = path.stat()
    except OSError:
        return False
    flags = getattr(st, "st_flags", 0)
    return bool(flags & _SF_DATALESS)


def walk_audio_files(root: Path) -> Iterator[tuple[Path, str]]:
    """Yield (absolute_path, rel_path) for every candidate audio file under root.

    rel_path uses forward slashes regardless of OS, so it's a stable,
    portable key for (root_id, rel_path) uniqueness in the database.
    """
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if not is_hidden(d) and d not in SKIP_DIR_NAMES
        ]
        for filename in filenames:
            if is_hidden(filename):
                continue
            ext = os.path.splitext(filename)[1].lower()
            if ext not in AUDIO_EXTENSIONS:
                continue
            abs_path = Path(dirpath) / filename
            rel_path = abs_path.relative_to(root).as_posix()
            yield abs_path, rel_path
