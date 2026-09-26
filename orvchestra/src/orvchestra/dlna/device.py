"""The MediaServer device itself: description metadata plus which services
it exposes. Only `friendly_name` is spec-mandated ("Orvchestra (MacBook)");
everything else is cosmetic identification shown in WiiM Home's server
list.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from async_upnp_client.const import DeviceInfo
from async_upnp_client.server import UpnpServerDevice

from orvchestra.dlna.connection_manager import ConnectionManagerService
from orvchestra.dlna.content_directory import ContentDirectoryService


def make_device_class(udn: str) -> type[UpnpServerDevice]:
    """A UDN is only known at runtime (persisted in the DB so it survives
    restarts -- see `repository.get_or_create_device_udn`), and
    `UpnpServer` instantiates `DEVICE_DEFINITION`'s class with no way to
    pass extra constructor arguments, so the class itself has to be built
    per-run with the right UDN baked in."""

    class OrvchestraMediaServerDevice(UpnpServerDevice):
        DEVICE_DEFINITION = DeviceInfo(
            device_type="urn:schemas-upnp-org:device:MediaServer:1",
            friendly_name="Orvchestra (MacBook)",
            manufacturer="Orvchestra",
            manufacturer_url=None,
            model_description="A private streaming-style player for a local music library",
            model_name="Orvchestra Engine",
            model_number="1",
            model_url=None,
            serial_number=None,
            udn=udn,
            upc=None,
            presentation_url=None,
            url="/upnp/device.xml",
            icons=[],
            xml=ET.Element("device"),
        )
        EMBEDDED_DEVICES = []
        SERVICES = [ContentDirectoryService, ConnectionManagerService]

    return OrvchestraMediaServerDevice
