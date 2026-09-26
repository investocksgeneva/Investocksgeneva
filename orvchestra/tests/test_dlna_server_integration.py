"""A real end-to-end pass through `DlnaMediaServer`: an actual bound socket,
an actual SOAP request over HTTP, an actual response parsed back. The
`_children`/`_metadata` unit tests exercise the browse logic in isolation,
but they can't catch a wiring problem in how `async_upnp_client.server`
reflects over our service classes to build actions/SCPD (that class of bug
only shows up once a real `UpnpServerService` gets instantiated) -- this
test is what would have caught it.
"""

from __future__ import annotations

import asyncio

import httpx2

from orvchestra.db import repository as repo
from orvchestra.dlna.server import DlnaMediaServer
from orvchestra.scanner.scan import scan_root
from orvchestra import paths as orv_paths

from conftest import make_flac

_PORT = 18201


def _browse_body(object_id: str, flag: str = "BrowseDirectChildren") -> str:
    return (
        '<?xml version="1.0"?>'
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
        's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
        '<s:Body><u:Browse xmlns:u="urn:schemas-upnp-org:service:ContentDirectory:1">'
        f"<ObjectID>{object_id}</ObjectID><BrowseFlag>{flag}</BrowseFlag><Filter>*</Filter>"
        "<StartingIndex>0</StartingIndex><RequestedCount>0</RequestedCount><SortCriteria></SortCriteria>"
        "</u:Browse></s:Body></s:Envelope>"
    )


async def _run(db_conn, tmp_path):
    music = tmp_path / "music"
    make_flac(music / "a.flac", tags={"TITLE": "Real Track", "ARTIST": "Real Artist"})
    repo.add_root(db_conn, str(music), None, None)
    root = repo.get_root_by_path(db_conn, str(music))
    scan_root(db_conn, root, orv_paths.artwork_dir())

    server = DlnaMediaServer(db_conn, "http://127.0.0.1:9999", _PORT, host="127.0.0.1")
    await server.start()
    try:
        async with httpx2.AsyncClient() as client:
            device_xml = await client.get(f"http://127.0.0.1:{_PORT}/upnp/device.xml")
            assert device_xml.status_code == 200
            assert "Orvchestra (MacBook)" in device_xml.text
            assert "urn:schemas-upnp-org:device:MediaServer:1" in device_xml.text

            resp = await client.post(
                f"http://127.0.0.1:{_PORT}/upnp/content_directory/control",
                content=_browse_body("artists"),
                headers={
                    "Content-Type": 'text/xml; charset="utf-8"',
                    "SOAPAction": '"urn:schemas-upnp-org:service:ContentDirectory:1#Browse"',
                },
            )
            assert resp.status_code == 200
            assert "Real Artist" in resp.text
            assert "<NumberReturned>1</NumberReturned>" in resp.text

            bad = await client.post(
                f"http://127.0.0.1:{_PORT}/upnp/content_directory/control",
                content=_browse_body("nonsense"),
                headers={
                    "Content-Type": 'text/xml; charset="utf-8"',
                    "SOAPAction": '"urn:schemas-upnp-org:service:ContentDirectory:1#Browse"',
                },
            )
            assert bad.status_code == 500
            assert "701" in bad.text
    finally:
        await server.stop()


def test_dlna_server_real_http_roundtrip(db_conn, tmp_path):
    asyncio.run(_run(db_conn, tmp_path))
