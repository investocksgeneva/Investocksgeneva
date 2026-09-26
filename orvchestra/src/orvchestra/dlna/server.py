"""Top-level lifecycle wrapper: SSDP advertisement/search-response plus the
device-description/SOAP-control HTTP server, all provided by
`async_upnp_client.server.UpnpServer`. The actual media bytes are served
separately by the FastAPI app in `orvchestra.media` -- DIDL-Lite `<res>`
elements just point at it -- so this class owns nothing but the UPnP
control-plane.
"""

from __future__ import annotations

import logging
import sqlite3

from async_upnp_client.server import UpnpServer
from async_upnp_client.utils import get_local_ip

from orvchestra.db import repository as repo
from orvchestra.dlna.content_directory import ContentDirectoryService
from orvchestra.dlna.device import make_device_class

logger = logging.getLogger("orvchestra.dlna")


class DlnaMediaServer:
    def __init__(self, conn: sqlite3.Connection, media_base_url: str, dlna_port: int, host: str | None = None):
        self.conn = conn
        self.media_base_url = media_base_url
        self.dlna_port = dlna_port
        self.host = host
        self._server: UpnpServer | None = None

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
        logger.info("DLNA MediaServer listening at http://%s:%s/upnp/device.xml", local_ip, self.dlna_port)

    async def stop(self) -> None:
        if self._server is not None:
            await self._server.async_stop()
            self._server = None
