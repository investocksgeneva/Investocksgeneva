"""Tests the queue/gapless-advance state machine against a fake renderer --
a real UPnP device isn't available in CI, but the state machine itself
(what gets pushed, when, and how the queue advances) doesn't need one: it
only needs something that behaves like `DmrDevice` for the handful of
methods `PlaybackService` calls.
"""

from __future__ import annotations

import asyncio

from async_upnp_client.profiles.dlna import TransportState

from orvchestra.db import repository as repo
from orvchestra.playback.keepawake import KeepAwakeController
from orvchestra.playback.service import THIS_DEVICE, PlaybackService
from orvchestra.scanner.scan import scan_root
from orvchestra import paths as orv_paths

from conftest import make_flac


class FakeRenderer:
    def __init__(self, udn: str = "uuid:fake", name: str = "Fake WiiM"):
        self.udn = udn
        self.name = name
        self.manufacturer = "Test Co"
        self.model_name = "FakeModel"
        self.has_next_transport_uri = True
        self.transport_state: TransportState | None = None
        self.av_transport_uri: str | None = None
        self.media_position = 0
        self.media_duration = 100
        self.volume_level = 0.5
        self.calls: list[tuple] = []
        self._next_uri: str | None = None

    async def async_set_transport_uri(self, url, title, meta_data=None):
        self.calls.append(("set_transport_uri", url))
        self.av_transport_uri = url
        self.transport_state = TransportState.STOPPED

    async def async_set_next_transport_uri(self, url, title, meta_data=None):
        self.calls.append(("set_next_transport_uri", url))
        self._next_uri = url

    async def async_wait_for_can_play(self, max_wait_time: float = 5):
        pass

    async def async_play(self):
        self.calls.append(("play",))
        self.transport_state = TransportState.PLAYING

    async def async_pause(self):
        self.calls.append(("pause",))
        self.transport_state = TransportState.PAUSED_PLAYBACK

    async def async_stop(self):
        self.calls.append(("stop",))
        self.transport_state = TransportState.STOPPED

    async def async_seek_abs_time(self, time):
        self.calls.append(("seek", time))

    async def async_set_volume_level(self, level):
        self.volume_level = level

    async def async_update(self):
        self.calls.append(("update",))

    def simulate_auto_advance(self):
        """Pretend the renderer finished the current track and moved on to
        whatever URI was queued via SetNextAVTransportURI, entirely on its
        own -- exactly what a real gapless DLNA renderer does."""
        assert self._next_uri is not None
        self.av_transport_uri = self._next_uri


def _seed_three_tracks(db_conn, tmp_path) -> list[int]:
    music = tmp_path / "music"
    for i in range(1, 4):
        make_flac(music / f"{i:02d}.flac", tags={"TITLE": f"Track {i}", "ARTIST": "A", "ALBUM": "Al", "TRACKNUMBER": str(i)})
    repo.add_root(db_conn, str(music), None, None)
    root = repo.get_root_by_path(db_conn, str(music))
    scan_root(db_conn, root, orv_paths.artwork_dir())
    rows = db_conn.execute("SELECT id FROM tracks ORDER BY rel_path").fetchall()
    return [r["id"] for r in rows]


def _service(db_conn) -> PlaybackService:
    return PlaybackService(db_conn, "http://192.168.1.50:8347", KeepAwakeController())


def test_default_output_is_this_device(db_conn):
    service = _service(db_conn)
    outputs = service.list_outputs()
    assert outputs == [{"id": THIS_DEVICE, "name": "This device", "kind": "browser", "selected": True}]


def test_select_unknown_output_raises(db_conn):
    service = _service(db_conn)
    try:
        service.select_output("uuid:does-not-exist")
        assert False, "expected KeyError"
    except KeyError:
        pass


def test_play_current_pushes_uri_and_plays_and_queues_next(db_conn, tmp_path):
    track_ids = _seed_three_tracks(db_conn, tmp_path)
    service = _service(db_conn)
    renderer = FakeRenderer()
    service.renderers = {renderer.udn: renderer}
    service.select_output(renderer.udn)
    service.set_queue(track_ids)

    asyncio.run(service.play_current())

    assert ("play",) in renderer.calls
    track1_url, _, _ = service._track_url_and_metadata(track_ids[0])
    track2_url, _, _ = service._track_url_and_metadata(track_ids[1])
    assert renderer.av_transport_uri == track1_url
    assert renderer._next_uri == track2_url
    assert service._pushed_next_track_id == track_ids[1]


def test_poll_detects_gapless_auto_advance_and_requeues(db_conn, tmp_path):
    track_ids = _seed_three_tracks(db_conn, tmp_path)
    service = _service(db_conn)
    renderer = FakeRenderer()
    service.renderers = {renderer.udn: renderer}
    service.select_output(renderer.udn)
    service.set_queue(track_ids)

    asyncio.run(service.play_current())
    assert service.queue_position == 0

    renderer.simulate_auto_advance()  # renderer moved itself onto track 2
    asyncio.run(service._poll_once())

    assert service.queue_position == 1
    track3_url, _, _ = service._track_url_and_metadata(track_ids[2])
    assert renderer._next_uri == track3_url  # track 3 is now queued as next
    assert service._pushed_next_track_id == track_ids[2]


def test_poll_marks_keepawake_active_only_while_playing(db_conn, tmp_path):
    track_ids = _seed_three_tracks(db_conn, tmp_path)
    service = _service(db_conn)
    renderer = FakeRenderer()
    service.renderers = {renderer.udn: renderer}
    service.select_output(renderer.udn)
    service.set_queue(track_ids)

    asyncio.run(service.play_current())
    asyncio.run(service._poll_once())
    assert service.keep_awake.is_running is False  # test env has no real caffeinate binding effect either way
    assert "dlna:uuid:fake" in service.keep_awake._active_sources

    renderer.transport_state = TransportState.PAUSED_PLAYBACK
    asyncio.run(service._poll_once())
    assert "dlna:uuid:fake" not in service.keep_awake._active_sources


def test_next_and_previous_navigate_queue(db_conn, tmp_path):
    track_ids = _seed_three_tracks(db_conn, tmp_path)
    service = _service(db_conn)
    renderer = FakeRenderer()
    service.renderers = {renderer.udn: renderer}
    service.select_output(renderer.udn)
    service.set_queue(track_ids)

    asyncio.run(service.play_current())
    asyncio.run(service.next())
    assert service.queue_position == 1
    asyncio.run(service.next())
    assert service.queue_position == 2
    asyncio.run(service.next())  # already at the end, no-op
    assert service.queue_position == 2

    asyncio.run(service.previous())
    assert service.queue_position == 1


def test_this_device_output_never_touches_a_renderer(db_conn, tmp_path):
    track_ids = _seed_three_tracks(db_conn, tmp_path)
    service = _service(db_conn)
    service.set_queue(track_ids)

    asyncio.run(service.play_current())  # should be a safe no-op

    now_playing = service.now_playing()
    assert now_playing["output"] == THIS_DEVICE
    assert now_playing["track"]["title"] == "Track 1"
    assert "transport_state" not in now_playing


def test_now_playing_includes_renderer_state(db_conn, tmp_path):
    track_ids = _seed_three_tracks(db_conn, tmp_path)
    service = _service(db_conn)
    renderer = FakeRenderer()
    service.renderers = {renderer.udn: renderer}
    service.select_output(renderer.udn)
    service.set_queue(track_ids)
    asyncio.run(service.play_current())

    now_playing = service.now_playing()
    assert now_playing["transport_state"] == "PLAYING"
    assert now_playing["duration_seconds"] == 100
    assert now_playing["volume"] == 0.5


def test_refresh_renderers_falls_back_when_selected_renderer_vanishes(db_conn, tmp_path, monkeypatch):
    track_ids = _seed_three_tracks(db_conn, tmp_path)
    service = _service(db_conn)
    renderer = FakeRenderer()
    service.renderers = {renderer.udn: renderer}
    service.select_output(renderer.udn)
    service.set_queue(track_ids)

    async def empty_discovery():
        return []

    import orvchestra.playback.service as service_module

    monkeypatch.setattr(service_module, "discover_renderers", lambda: empty_discovery())
    asyncio.run(service.refresh_renderers())

    assert service.active_output == THIS_DEVICE
