"""Owns the play queue and pushes it to whichever output is selected.

"this-device" playback (the browser/phone itself) is not a UPnP renderer at
all -- there is nothing to control here, the frontend's own `<audio>`
element does the playing, and it tells us about it via
`PlaybackService.set_browser_playing`, purely so keep-awake knows something
is streaming. Everything else in this module is about DLNA renderers: an
album is: SetAVTransportURI, Play, and -- key for gapless playback --
immediately queueing the *next* track with SetNextAVTransportURI so the
renderer can advance to it on its own with no gap. A background poll loop
(there is no event-subscription callback server in Phase 3 -- see the
README) watches for that auto-advance, and re-queues the track after it.
"""

from __future__ import annotations

import asyncio
import logging
import random
import sqlite3
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from async_upnp_client.profiles.dlna import DmrDevice, TransportState

from orvchestra.db import repository as repo
from orvchestra.dlna import didl, ids
from orvchestra.playback.keepawake import KeepAwakeController
from orvchestra.renderers.discovery import discover_renderers

logger = logging.getLogger("orvchestra.playback")

THIS_DEVICE = "this-device"
_POLL_INTERVAL_SECONDS = 1.0

# "Count a play after 50% or 4 minutes, whichever comes first" -- so the
# threshold is whichever of those two is *smaller*: a 3-minute track counts
# at 90s (50%), a 20-minute one counts at 4 minutes, not 10.
_MAX_PLAY_THRESHOLD_SECONDS = 240.0


def _radio_track_summary(station: dict[str, Any]) -> dict[str, Any]:
    """Shaped to match `_track_summary` closely enough that the frontend's
    Now Playing / mini-player / queue views, which only read fields off
    this dict, don't need to know radio is a different kind of thing."""
    return {
        "id": f"radio:{station['id']}",
        "title": station["name"],
        "artist": "Internet radio",
        "album_artist": None,
        "album": None,
        "year": None,
        "track_number": None,
        "disc_number": None,
        "duration_seconds": None,
        "codec": None,
        "sample_rate": None,
        "bit_depth": None,
        "art_hash": None,
        "rating": None,
        "is_radio": True,
        "stream_url": station["stream_url"],
        "art_url_large": station.get("favicon") or None,
        "art_url_small": station.get("favicon") or None,
    }


def _track_summary(row: sqlite3.Row, media_base_url: str) -> dict[str, Any]:
    art_hash = row["art_hash"]
    return {
        "id": row["id"],
        "title": row["title"] or row["rel_path"].rsplit("/", 1)[-1],
        "artist": row["artist"],
        "album_artist": row["album_artist"],
        "album": row["album"],
        "year": row["year"],
        "track_number": row["track_number"],
        "disc_number": row["disc_number"],
        "duration_seconds": row["duration_seconds"],
        "codec": row["codec"],
        "sample_rate": row["sample_rate"],
        "bit_depth": row["bit_depth"],
        "art_hash": art_hash,
        "rating": row["rating"],
        "art_url_small": f"{media_base_url}/art/{art_hash}/300.jpg" if art_hash else None,
        "art_url_large": f"{media_base_url}/art/{art_hash}/1000.jpg" if art_hash else None,
    }


@dataclass
class _PlaySession:
    """Tracks progress toward the play-counting threshold for whichever
    track is currently current, regardless of output -- fed by the DLNA poll
    loop's position updates or by the browser's own progress reports
    (`PlaybackService.report_browser_position`)."""

    track_id: int
    threshold_seconds: float
    started_at: str
    max_position_seen: float = 0.0
    recorded: bool = False


class PlaybackService:
    def __init__(self, conn: sqlite3.Connection, media_base_url: str, keep_awake: KeepAwakeController):
        self.conn = conn
        self.media_base_url = media_base_url
        self.keep_awake = keep_awake

        self.renderers: dict[str, DmrDevice] = {}
        self.active_output: str = THIS_DEVICE

        self.queue: list[int] = []
        self.queue_position: int = 0
        self._current_radio: dict[str, Any] | None = None

        # The queue as actually set (album/playlist/search order), kept
        # around so shuffle can be turned off again without losing it --
        # `self.queue` is what's actually played, and is a shuffled copy of
        # this whenever shuffle is on.
        self._unshuffled_queue: list[int] = []
        self.shuffle_enabled: bool = False
        self.repeat_mode: str = "off"  # "off" | "all" | "one"

        self._pushed_next_track_id: int | None = None
        self._poll_task: asyncio.Task | None = None
        self._play_session: _PlaySession | None = None

    # --- outputs ------------------------------------------------------

    async def refresh_renderers(self) -> None:
        devices = await discover_renderers()
        self.renderers = {d.udn: d for d in devices}
        if self.active_output != THIS_DEVICE and self.active_output not in self.renderers:
            # The previously selected renderer is gone (powered off, moved
            # networks); fall back rather than silently controlling nothing.
            self._cancel_poll_task()
            self.active_output = THIS_DEVICE

    def list_outputs(self) -> list[dict[str, Any]]:
        outputs: list[dict[str, Any]] = [
            {"id": THIS_DEVICE, "name": "This device", "kind": "browser", "selected": self.active_output == THIS_DEVICE}
        ]
        for udn, renderer in self.renderers.items():
            outputs.append(
                {
                    "id": udn,
                    "name": renderer.name,
                    "kind": "dlna",
                    "manufacturer": renderer.manufacturer,
                    "model": renderer.model_name,
                    "selected": self.active_output == udn,
                }
            )
        return outputs

    def select_output(self, output_id: str) -> None:
        if output_id != THIS_DEVICE and output_id not in self.renderers:
            raise KeyError(output_id)
        self._cancel_poll_task()
        self.active_output = output_id
        self._pushed_next_track_id = None

    @property
    def active_renderer(self) -> DmrDevice | None:
        return None if self.active_output == THIS_DEVICE else self.renderers.get(self.active_output)

    def _renderer_keepawake_id(self) -> str:
        return f"dlna:{self.active_output}"

    # --- queue ----------------------------------------------------------

    def set_queue(self, track_ids: list[int], start_index: int = 0) -> None:
        self._current_radio = None
        self._unshuffled_queue = list(track_ids)
        start_id = track_ids[start_index] if track_ids and 0 <= start_index < len(track_ids) else None
        if self.shuffle_enabled:
            self.queue = self._shuffled(self._unshuffled_queue, keep_first=start_id)
        else:
            self.queue = list(self._unshuffled_queue)
        self.queue_position = self.queue.index(start_id) if start_id is not None else 0
        self._pushed_next_track_id = None

    @staticmethod
    def _shuffled(track_ids: list[int], keep_first: int | None) -> list[int]:
        """A random order for the given tracks, with `keep_first` (if given
        and present) pinned at the front -- shuffling the *upcoming* queue
        around whatever's currently playing, rather than jumping to a
        random track the moment shuffle is turned on."""
        remaining = list(track_ids)
        if keep_first is not None and keep_first in remaining:
            remaining.remove(keep_first)
        random.shuffle(remaining)
        return ([keep_first] if keep_first is not None else []) + remaining

    def set_shuffle(self, enabled: bool) -> None:
        if enabled == self.shuffle_enabled:
            return
        self.shuffle_enabled = enabled
        current_id = self.current_track_id()
        self.queue = self._shuffled(self._unshuffled_queue, keep_first=current_id) if enabled else list(self._unshuffled_queue)
        self.queue_position = self.queue.index(current_id) if current_id is not None and current_id in self.queue else 0
        self._pushed_next_track_id = None

    def set_repeat_mode(self, mode: str) -> None:
        if mode not in ("off", "all", "one"):
            raise ValueError(f"invalid repeat mode: {mode!r}")
        self.repeat_mode = mode
        self._pushed_next_track_id = None

    def current_track_id(self) -> int | None:
        if not self.queue or not (0 <= self.queue_position < len(self.queue)):
            return None
        return self.queue[self.queue_position]

    def next_track_id(self) -> int | None:
        """What should play after the current track -- used both to decide
        what `next()` moves to and what to gapless-pre-queue on a renderer,
        so repeat/shuffle only need to be handled in one place for both."""
        if self.repeat_mode == "one":
            return self.current_track_id()
        idx = self.queue_position + 1
        if idx < len(self.queue):
            return self.queue[idx]
        if self.repeat_mode == "all" and self.queue:
            return self.queue[0]
        return None

    def _advance_queue_position(self) -> None:
        """Moves `queue_position` to wherever `next_track_id()` just said was
        next -- repeat-one stays put (same track replaying), repeat-all
        wraps to the start, otherwise a plain increment."""
        if self.repeat_mode == "one":
            return
        idx = self.queue_position + 1
        if idx < len(self.queue):
            self.queue_position = idx
        elif self.repeat_mode == "all" and self.queue:
            self.queue_position = 0

    # --- transport control (DLNA renderers only) -------------------------

    def _track_url_and_metadata(self, track_id: int) -> tuple[str, str, str]:
        row = repo.get_track(self.conn, track_id)
        url = didl.stream_uri(self.media_base_url, row)
        parent_id = ids.album_id(*didl.canonical_album_key(row))
        metadata = didl.serialize([didl.build_track_element(row, parent_id, self.media_base_url)])
        return url, row["title"] or "", metadata

    async def play_current(self) -> None:
        track_id = self.current_track_id()
        if track_id is None:
            return
        self._start_play_session(track_id)

        renderer = self.active_renderer
        if renderer is None:
            return
        url, title, metadata = self._track_url_and_metadata(track_id)
        await renderer.async_set_transport_uri(url, title, meta_data=metadata)
        await renderer.async_wait_for_can_play()
        await renderer.async_play()
        self._pushed_next_track_id = None
        await self._push_next_if_needed()
        self._ensure_poll_task()

    async def play_radio(self, station: dict[str, Any]) -> None:
        """A station is not a queue of one -- no gapless next-track push, no
        play-counting session (there's no meaningful "finished" for a live
        stream), just point whichever output is active at the raw URL."""
        self.queue = []
        self.queue_position = 0
        self._pushed_next_track_id = None
        self._play_session = None
        self._current_radio = station

        renderer = self.active_renderer
        if renderer is None:
            return
        await renderer.async_set_transport_uri(station["stream_url"], station["name"], meta_data="")
        await renderer.async_wait_for_can_play()
        await renderer.async_play()
        self._ensure_poll_task()

    async def _push_next_if_needed(self) -> None:
        renderer = self.active_renderer
        next_id = self.next_track_id()
        if renderer is None or next_id is None or next_id == self._pushed_next_track_id:
            return
        if not renderer.has_next_transport_uri:
            return
        url, title, metadata = self._track_url_and_metadata(next_id)
        await renderer.async_set_next_transport_uri(url, title, meta_data=metadata)
        self._pushed_next_track_id = next_id

    async def pause(self) -> None:
        if self.active_renderer is not None:
            await self.active_renderer.async_pause()

    async def resume(self) -> None:
        if self.active_renderer is not None:
            await self.active_renderer.async_play()
            self._ensure_poll_task()

    async def stop(self) -> None:
        if self.active_renderer is not None:
            await self.active_renderer.async_stop()
        self._cancel_poll_task()
        self.keep_awake.set_active(self._renderer_keepawake_id(), False)

    async def next(self, *, auto: bool = False) -> None:
        """Advances to the next track. `auto=True` means this is the track
        finishing on its own (this-device's `<audio>` "ended" event) rather
        than a deliberate skip -- only then does repeat-one replay the same
        track, same as a real player's skip button overriding repeat-one for
        one press. The WiiM's own gapless auto-advance doesn't go through
        this method at all (see `_poll_once`), but applies the same rule via
        `next_track_id()`."""
        if auto and self.repeat_mode == "one":
            await self.play_current()
            return
        idx = self.queue_position + 1
        if idx < len(self.queue):
            self.queue_position = idx
            await self.play_current()
        elif self.repeat_mode == "all" and self.queue:
            self.queue_position = 0
            await self.play_current()

    async def previous(self) -> None:
        if self.queue_position > 0:
            self.queue_position -= 1
            await self.play_current()
        elif self.repeat_mode == "all" and self.queue:
            self.queue_position = len(self.queue) - 1
            await self.play_current()

    async def seek(self, position_seconds: float) -> None:
        if self.active_renderer is not None:
            await self.active_renderer.async_seek_abs_time(timedelta(seconds=max(0, position_seconds)))

    async def set_volume(self, level: float) -> None:
        if self.active_renderer is not None:
            await self.active_renderer.async_set_volume_level(max(0.0, min(1.0, level)))

    # --- this-device (browser) playback ----------------------------------

    def set_browser_playing(self, playing: bool) -> None:
        self.keep_awake.set_active("browser", playing)

    def report_browser_position(self, position_seconds: float) -> None:
        """Called by the frontend's <audio> element (throttled) so a
        this-device play gets recorded the same way a WiiM one does, via
        the same threshold logic."""
        self._note_position(position_seconds)

    # --- listening history (plays) ---------------------------------------

    def _start_play_session(self, track_id: int) -> None:
        row = repo.get_track(self.conn, track_id)
        duration = row["duration_seconds"] if row else None
        threshold = min(duration * 0.5, _MAX_PLAY_THRESHOLD_SECONDS) if duration else _MAX_PLAY_THRESHOLD_SECONDS
        self._play_session = _PlaySession(
            track_id=track_id,
            threshold_seconds=threshold,
            started_at=repo.iso_now_minus_days(0),
        )

    def _note_position(self, position_seconds: float | None) -> None:
        session = self._play_session
        if session is None or position_seconds is None:
            return
        session.max_position_seen = max(session.max_position_seen, position_seconds)
        if not session.recorded and session.max_position_seen >= session.threshold_seconds:
            device = "browser" if self.active_output == THIS_DEVICE else "wiim"
            repo.record_play(self.conn, session.track_id, session.started_at, session.max_position_seen, device)
            session.recorded = True

    # --- now playing ------------------------------------------------------

    def now_playing(self) -> dict[str, Any]:
        if self._current_radio is not None:
            result: dict[str, Any] = {
                "output": self.active_output,
                "track": _radio_track_summary(self._current_radio),
                "queue_position": 0,
                "queue_length": 0,
                "shuffle": self.shuffle_enabled,
                "repeat_mode": self.repeat_mode,
            }
        else:
            track_id = self.current_track_id()
            track_row = repo.get_track(self.conn, track_id) if track_id is not None else None
            result = {
                "output": self.active_output,
                "track": _track_summary(track_row, self.media_base_url) if track_row is not None else None,
                "queue_position": self.queue_position,
                "queue_length": len(self.queue),
                "shuffle": self.shuffle_enabled,
                "repeat_mode": self.repeat_mode,
            }
        renderer = self.active_renderer
        if renderer is not None:
            state = renderer.transport_state
            result.update(
                {
                    "transport_state": state.name if state is not None else None,
                    "position_seconds": renderer.media_position,
                    "duration_seconds": renderer.media_duration,
                    "volume": renderer.volume_level,
                }
            )
        return result

    # --- background polling: gapless auto-advance + keep-awake -----------

    def _ensure_poll_task(self) -> None:
        if self._poll_task is None or self._poll_task.done():
            self._poll_task = asyncio.ensure_future(self._poll_loop())

    def _cancel_poll_task(self) -> None:
        if self._poll_task is not None:
            self._poll_task.cancel()
            self._poll_task = None

    async def _poll_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(_POLL_INTERVAL_SECONDS)
                await self._poll_once()
        except asyncio.CancelledError:
            raise

    async def _poll_once(self) -> None:
        renderer = self.active_renderer
        if renderer is None:
            return
        try:
            await renderer.async_update()
        except Exception as exc:  # noqa: BLE001 - a flaky renderer must not kill the poll loop
            logger.warning("renderer poll failed: %s", exc)
            return

        if self._pushed_next_track_id is not None:
            expected_url, _, _ = self._track_url_and_metadata(self._pushed_next_track_id)
            if renderer.av_transport_uri == expected_url:
                # The renderer consumed NextAVTransportURI on its own: the
                # queue has silently, gaplessly advanced. Start tracking a
                # fresh play session for the new track *before* noting
                # position below, so this tick's position isn't attributed
                # to the track that just finished.
                self._advance_queue_position()
                self._pushed_next_track_id = None
                new_track_id = self.current_track_id()
                if new_track_id is not None:
                    self._start_play_session(new_track_id)
                await self._push_next_if_needed()

        self._note_position(renderer.media_position)

        state = renderer.transport_state
        self.keep_awake.set_active(self._renderer_keepawake_id(), state == TransportState.PLAYING)

        if state == TransportState.STOPPED and self.next_track_id() is None:
            self._cancel_poll_task()
            return

        # Cheap no-op when already correct (see its own guard) -- catches
        # shuffle/repeat being toggled mid-playback, which invalidates
        # whatever was gapless-pre-queued, within one poll tick rather than
        # waiting for the track to actually change.
        await self._push_next_if_needed()

    async def shutdown(self) -> None:
        self._cancel_poll_task()
        self.keep_awake.shutdown()
