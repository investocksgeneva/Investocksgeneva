"""Volume identification and reachability checks.

Phase 1 only needs "is this root's path currently a directory we can list"
to implement the unplug/reconnect behaviour. The volume UUID is captured and
stored for later (e.g. warning if a different drive gets mounted at the same
path) but is not load-bearing yet — keeping that logic out of Phase 1 avoids
guessing at drive-swap heuristics before we have real hardware to test
against.
"""

from __future__ import annotations

import plistlib
import subprocess
import sys
from pathlib import Path


def get_volume_uuid(path: Path) -> str | None:
    if sys.platform != "darwin":
        return None
    try:
        result = subprocess.run(
            ["diskutil", "info", "-plist", str(path)],
            capture_output=True,
            timeout=5,
            check=True,
        )
        info = plistlib.loads(result.stdout)
        return info.get("VolumeUUID")
    except (OSError, subprocess.SubprocessError, plistlib.InvalidFileException, ValueError):
        return None


def is_root_reachable(path: str) -> bool:
    try:
        return Path(path).is_dir()
    except OSError:
        return False
