"""Keeps the Mac from idle-sleeping while something is actively streaming
from it, via `caffeinate -i`.

This does NOT stop the Mac sleeping when its lid is closed -- that's a
hardware-level decision macOS makes (clamshell sleep) regardless of any
running process's power assertions. There's no software workaround short of
running with the lid open or in a clamshell-with-external-display setup;
see the README.
"""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger("orvchestra.keepawake")


class KeepAwakeController:
    def __init__(self) -> None:
        self._active_sources: set[str] = set()
        self._process: subprocess.Popen | None = None

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def set_active(self, source_id: str, active: bool) -> None:
        """`source_id` names *why* something wants the Mac awake (a renderer's
        UDN, or "browser" for this-device playback) so independent playback
        sources don't clobber each other's on/off state."""
        if active:
            self._active_sources.add(source_id)
        else:
            self._active_sources.discard(source_id)
        self._sync()

    def _sync(self) -> None:
        should_run = bool(self._active_sources)
        if should_run and not self.is_running:
            self._start()
        elif not should_run and self._process is not None:
            self._stop()

    def _start(self) -> None:
        try:
            self._process = subprocess.Popen(["caffeinate", "-i"])
            logger.info("caffeinate started: keeping the Mac awake while playing")
        except FileNotFoundError:
            logger.warning("caffeinate not found (not macOS?) -- the Mac may sleep during playback")
            self._process = None

    def _stop(self) -> None:
        if self._process is not None:
            self._process.terminate()
            self._process = None
            logger.info("caffeinate stopped")

    def shutdown(self) -> None:
        self._active_sources.clear()
        self._stop()
