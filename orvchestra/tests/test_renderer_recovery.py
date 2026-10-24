"""Covers PlaybackService's recovery from a transient renderer failure (a
Wi-Fi reconnect, a VPN route change, the amp briefly dropping off) -- the
real-world case that surfaced as a raw 500 on `/api/playback/resume` with a
UPnP "704 play not allowed" fault once the renderer connection went stale.
See service.py's `_call_renderer` and its module docstring.
"""

from __future__ import annotations

import asyncio

from starlette.testclient import TestClient

from orvchestra.db import repository as repo
from orvchestra.playback.keepawake import KeepAwakeController
from orvchestra.playback.service import PlaybackService, RendererUnavailableError
from orvchestra.scanner.scan import scan_root
from orvchestra.webapp.app import create_app
from orvchestra import paths as orv_paths

from conftest import make_flac
from test_playback_service import FakeRenderer, _seed_three_tracks, _service

import orvchestra.playback.service as service_module

BASE = "http://192.168.1.50:8347"


def _patch_discovery_to_return(monkeypatch, renderers: list):
    async def fake_discovery(timeout: int = 3):
        return list(renderers)

    monkeypatch.setattr(service_module, "discover_renderers", fake_discovery)


def test_transient_failure_recovers_via_refresh_and_retry(db_conn, tmp_path, monkeypatch):
    track_ids = _seed_three_tracks(db_conn, tmp_path)
    service = _service(db_conn)
    renderer = FakeRenderer()
    service.renderers = {renderer.udn: renderer}
    service.select_output(renderer.udn)
    service.set_queue(track_ids)

    # The renderer is still out there (discovery finds it fine on refresh)
    # -- only the one call blipped, the classic transient case.
    _patch_discovery_to_return(monkeypatch, [renderer])
    renderer.fail_times["play"] = 1

    asyncio.run(service.play_current())  # must not raise

    assert renderer.fail_times["play"] == 0  # the one scripted failure got consumed
    assert ("play",) in renderer.calls  # and the retry actually succeeded


def test_persistent_failure_raises_renderer_unavailable(db_conn, tmp_path, monkeypatch):
    track_ids = _seed_three_tracks(db_conn, tmp_path)
    service = _service(db_conn)
    renderer = FakeRenderer()
    service.renderers = {renderer.udn: renderer}
    service.select_output(renderer.udn)
    service.set_queue(track_ids)
    asyncio.run(service.play_current())  # establish a working baseline first

    # Both the first attempt and the one retry fail -- a real outage, not a blip.
    _patch_discovery_to_return(monkeypatch, [renderer])
    renderer.fail_times["pause"] = 2

    try:
        asyncio.run(service.pause())
        assert False, "expected RendererUnavailableError"
    except RendererUnavailableError:
        pass


def test_renderer_vanishing_during_retry_raises_renderer_unavailable(db_conn, tmp_path, monkeypatch):
    track_ids = _seed_three_tracks(db_conn, tmp_path)
    service = _service(db_conn)
    renderer = FakeRenderer()
    service.renderers = {renderer.udn: renderer}
    service.select_output(renderer.udn)
    service.set_queue(track_ids)
    asyncio.run(service.play_current())

    # This time the renderer is genuinely gone -- discovery finds nothing.
    _patch_discovery_to_return(monkeypatch, [])
    renderer.fail_times["pause"] = 1

    try:
        asyncio.run(service.pause())
        assert False, "expected RendererUnavailableError"
    except RendererUnavailableError:
        pass


def test_stop_still_cleans_up_locally_when_renderer_unreachable(db_conn, tmp_path, monkeypatch):
    """Even when the remote stop fails outright, polling/keep-awake must
    still be released -- there's nothing else left worth doing that for."""
    track_ids = _seed_three_tracks(db_conn, tmp_path)
    service = _service(db_conn)
    renderer = FakeRenderer()
    service.renderers = {renderer.udn: renderer}
    service.select_output(renderer.udn)
    service.set_queue(track_ids)
    asyncio.run(service.play_current())
    asyncio.run(service._poll_once())
    assert service._poll_task is not None
    assert "dlna:uuid:fake" in service.keep_awake._active_sources

    _patch_discovery_to_return(monkeypatch, [])
    renderer.fail_times["stop"] = 1

    try:
        asyncio.run(service.stop())
        assert False, "expected RendererUnavailableError"
    except RendererUnavailableError:
        pass

    assert service._poll_task is None
    assert "dlna:uuid:fake" not in service.keep_awake._active_sources


def test_gapless_push_next_degrades_gracefully_instead_of_crashing_the_poll_loop(db_conn, tmp_path, monkeypatch):
    track_ids = _seed_three_tracks(db_conn, tmp_path)
    service = _service(db_conn)
    renderer = FakeRenderer()
    service.renderers = {renderer.udn: renderer}
    service.select_output(renderer.udn)
    service.set_queue(track_ids)
    asyncio.run(service.play_current())

    _patch_discovery_to_return(monkeypatch, [])  # genuinely gone
    renderer.fail_times["set_next_transport_uri"] = 1
    service._pushed_next_track_id = None  # force a re-push attempt

    asyncio.run(service._push_next_if_needed())  # must not raise

    assert service._pushed_next_track_id is None  # didn't pretend it succeeded


def _seed_api(db_conn, tmp_path):
    music = tmp_path / "music"
    make_flac(music / "01.flac", tags={"TITLE": "Song One", "ARTIST": "A", "ALBUM": "Al", "TRACKNUMBER": "1"})
    repo.add_root(db_conn, str(music), None, None)
    root = repo.get_root_by_path(db_conn, str(music))
    scan_root(db_conn, root, orv_paths.artwork_dir())


def test_api_returns_503_instead_of_crashing_on_persistent_renderer_failure(db_conn, tmp_path, monkeypatch):
    _seed_api(db_conn, tmp_path)
    playback = PlaybackService(db_conn, BASE, KeepAwakeController())
    renderer = FakeRenderer()
    playback.renderers = {renderer.udn: renderer}
    playback.select_output(renderer.udn)
    track_ids = [r["id"] for r in db_conn.execute("SELECT id FROM tracks ORDER BY rel_path")]
    playback.set_queue(track_ids)
    asyncio.run(playback.play_current())

    _patch_discovery_to_return(monkeypatch, [renderer])
    renderer.fail_times["pause"] = 2  # both the attempt and the retry fail

    app = create_app(db_conn, BASE, playback)
    client = TestClient(app)
    resp = client.post("/api/playback/pause")

    assert resp.status_code == 503
    assert "detail" in resp.json()
