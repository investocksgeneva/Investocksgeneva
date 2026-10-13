"""Top-level lifecycle wrapper: SSDP advertisement/search-response plus the
device-description/SOAP-control HTTP server, all provided by
`async_upnp_client.server.UpnpServer`. The actual media bytes are served
separately by the FastAPI app in `orvchestra.media` -- DIDL-Lite `<res>`
elements just point at it -- so this class owns nothing but the UPnP
control-plane.

A sleep/wake cycle, a VPN like Tailscale rewriting the routing table on
(re)connect, or a flaky Wi-Fi reconnect can all leave the SSDP advertiser's
UDP socket bound to a route that no longer exists -- every send after that
fails with "Network is unreachable", logged by async_upnp_client's own
SsdpProtocol.error_received() (see ssdp.py), which does nothing but log:
nothing in the library itself ever notices and rebinds. Left alone this
repeats forever and was observed to degrade the whole process (the web app
sharing the same event loop became unresponsive too, not just DLNA) until
the service was manually restarted. `_install_network_recovery` watches for
that exact log line via a standard logging.Handler (a supported extension
point -- not patching the library's internals) and restarts just the DLNA
side, which creates fresh sockets and clears the problem without touching
the already-running web app or playback state.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import time

from async_upnp_client.server import UpnpServer
from async_upnp_client.utils import get_local_ip

from orvchestra.db import repository as repo
from orvchestra.dlna.content_directory import ContentDirectoryService
from orvchestra.dlna.device import make_device_class

logger = logging.getLogger("orvchestra.dlna")

# One restart is enough to fix a transient blip; this stops a genuinely-down
# network from causing a tight restart loop while it stays down.
_RESTART_COOLDOWN_SECONDS = 10.0


class _SsdpNetworkErrorWatcher(logging.Handler):
    """Fires `on_network_error` whenever async_upnp_client's own SSDP
    logger reports a send/receive failure -- the one error class its
    `SsdpProtocol.error_received()` logs but never recovers from itself."""

    def __init__(self, on_network_error) -> None:
        super().__init__(level=logging.ERROR)
        self._on_network_error = on_network_error

    def emit(self, record: logging.LogRecord) -> None:
        if record.getMessage().startswith("Received error"):
            self._on_network_error()


class DlnaMediaServer:
    def __init__(self, conn: sqlite3.Connection, media_base_url: str, dlna_port: int, host: str | None = None):
        self.conn = conn
        self.media_base_url = media_base_url
        self.dlna_port = dlna_port
        self.host = host
        self._server: UpnpServer | None = None
        self._restarting = False
        self._last_restart_at = 0.0
        self._ssdp_logger = logging.getLogger("async_upnp_client.ssdp")
        self._error_watcher = _SsdpNetworkErrorWatcher(self._on_ssdp_network_error)

    async def start(self) -> None:
        # See ContentDirectoryService's docstring for why these are class
        # attributes rather than constructor arguments.
        ContentDirectoryService.conn = self.conn
        ContentDirectoryService.media_base_url = self.media_base_url

        udn = repo.get_or_create_device_udn(self.conn)
        device_class = make_device_class(udn)

        local_ip = self.host or get_local_ip()
        self._server = UpnpServer(device_class, source=(local_ip, 0), http_port=self.dlna_port)
        await self._server.async_start()
        self._ssdp_logger.addHandler(self._error_watcher)
        logger.info("DLNA MediaServer listening at http://%s:%s/upnp/device.xml", local_ip, self.dlna_port)

    async def stop(self) -> None:
        self._ssdp_logger.removeHandler(self._error_watcher)
        if self._server is not None:
            await self._server.async_stop()
            self._server = None

    async def restart(self) -> None:
        """Tears down and rebuilds the SSDP/UPnP server with fresh sockets
        -- see the module docstring for why this is needed at all."""
        if self._restarting:
            return
        self._restarting = True
        try:
            logger.warning("DLNA advertisement lost its network; restarting it")
            await self.stop()
            await self.start()
        except Exception:
            logger.exception("failed to restart DLNA advertisement after a network error")
        finally:
            self._restarting = False

    def _on_ssdp_network_error(self) -> None:
        now = time.monotonic()
        if now - self._last_restart_at < _RESTART_COOLDOWN_SECONDS:
            return
        self._last_restart_at = now
        asyncio.ensure_future(self.restart())
