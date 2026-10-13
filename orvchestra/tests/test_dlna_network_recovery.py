"""Covers DlnaMediaServer's recovery from the one error async_upnp_client's
own SsdpProtocol never recovers from itself: its UDP socket reporting the
network as unreachable (see server.py's module docstring for when this
happens in practice -- sleep/wake, a VPN like Tailscale rewriting routes,
a flaky Wi-Fi reconnect). Two angles: a fast unit-style test of the
trigger/cooldown logic in isolation, and a real end-to-end pass proving the
logger hook actually wires up to a genuine restart that leaves the server
working afterward.
"""

from __future__ import annotations

import asyncio
import logging

import httpx2

from orvchestra.db import repository as repo
from orvchestra.dlna.server import DlnaMediaServer
from orvchestra.scanner.scan import scan_root
from orvchestra import paths as orv_paths

_PORT = 18211


def _seed(db_conn, tmp_path):
    from conftest import make_flac

    music = tmp_path / "music"
    make_flac(music / "a.flac", tags={"TITLE": "Real Track", "ARTIST": "Real Artist"})
    repo.add_root(db_conn, str(music), None, None)
    root = repo.get_root_by_path(db_conn, str(music))
    scan_root(db_conn, root, orv_paths.artwork_dir())


def test_restart_is_scheduled_once_per_cooldown_window(db_conn, tmp_path, monkeypatch):
    _seed(db_conn, tmp_path)
    server = DlnaMediaServer(db_conn, "http://127.0.0.1:9999", _PORT, host="127.0.0.1")

    calls = []

    async def fake_restart():
        calls.append(1)

    monkeypatch.setattr(server, "restart", fake_restart)

    async def _run():
        # Two errors in quick succession (exactly what one underlying
        # network blip produces -- the announcer's and responder's sockets
        # both error around the same time) must only schedule one restart.
        server._on_ssdp_network_error()
        server._on_ssdp_network_error()
        await asyncio.sleep(0)  # let the scheduled task actually run

    asyncio.run(_run())
    assert len(calls) == 1


def test_restart_is_not_scheduled_again_within_cooldown(db_conn, tmp_path, monkeypatch):
    _seed(db_conn, tmp_path)
    server = DlnaMediaServer(db_conn, "http://127.0.0.1:9999", _PORT, host="127.0.0.1")

    calls = []

    async def fake_restart():
        calls.append(1)

    monkeypatch.setattr(server, "restart", fake_restart)

    async def _run():
        server._on_ssdp_network_error()
        await asyncio.sleep(0)
        server._last_restart_at -= 1  # well inside the 10s cooldown still
        server._on_ssdp_network_error()
        await asyncio.sleep(0)

    asyncio.run(_run())
    assert len(calls) == 1  # the second attempt was suppressed by the cooldown


def test_real_network_error_log_triggers_a_working_restart(db_conn, tmp_path):
    """End-to-end: a real async_upnp_client-shaped log record through the
    real logger, through the real handler, triggering a real restart that
    leaves the server reachable afterward -- proving the whole hookup
    works, not just the counting logic in isolation."""
    _seed(db_conn, tmp_path)
    server = DlnaMediaServer(db_conn, "http://127.0.0.1:9999", _PORT, host="127.0.0.1")

    async def _run():
        await server.start()
        try:
            async with httpx2.AsyncClient() as client:
                before = await client.get(f"http://127.0.0.1:{_PORT}/upnp/device.xml")
                assert before.status_code == 200

                logging.getLogger("async_upnp_client.ssdp").error(
                    "Received error: %s, transport: %s, socket: %s", "network is unreachable", "t", "s"
                )
                # Give the scheduled restart() a moment to actually run.
                for _ in range(20):
                    await asyncio.sleep(0.05)
                    if not server._restarting and server._last_restart_at:
                        break

                after = await client.get(f"http://127.0.0.1:{_PORT}/upnp/device.xml")
                assert after.status_code == 200
        finally:
            await server.stop()

    asyncio.run(_run())


def test_handler_is_not_duplicated_across_restarts(db_conn, tmp_path):
    """Restarting must not pile up a fresh logging.Handler on top of the
    old one each time, or a single real error would eventually trigger many
    redundant restarts."""
    _seed(db_conn, tmp_path)
    server = DlnaMediaServer(db_conn, "http://127.0.0.1:9999", _PORT, host="127.0.0.1")
    ssdp_logger = logging.getLogger("async_upnp_client.ssdp")

    counts = []

    async def _run():
        await server.start()
        await server.stop()
        await server.start()  # ends started, not stopped
        counts.append(ssdp_logger.handlers.count(server._error_watcher))
        await server.stop()
        counts.append(ssdp_logger.handlers.count(server._error_watcher))

    asyncio.run(_run())
    assert counts == [1, 0]  # exactly one while started, cleanly removed after stop (no leak)
