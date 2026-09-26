"""Finds DLNA MediaRenderer devices on the LAN -- the WiiM Amp Pro, and any
other renderer that happens to be around. Built on
`async_upnp_client.profiles.dlna.DmrDevice`, which already knows how to
distinguish a real renderer (has AVTransport + RenderingControl) from any
other UPnP device that answers SSDP, so there's no reason to hand-roll that
check.
"""

from __future__ import annotations

import logging

from async_upnp_client.aiohttp import AiohttpRequester
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.profiles.dlna import DmrDevice

logger = logging.getLogger("orvchestra.renderers")


async def discover_renderers(timeout: int = 3) -> list[DmrDevice]:
    """One-shot SSDP sweep for renderers, returning a fresh `DmrDevice` per
    distinct device found. Callers own the returned devices; nothing here is
    cached, since a WiiM that's been power-cycled needs a fresh `UpnpDevice`
    anyway (its description/event URLs may have changed)."""
    responses = await DmrDevice.async_search(timeout=timeout)

    seen_locations: set[str] = set()
    requester = AiohttpRequester()
    factory = UpnpFactory(requester)
    devices: list[DmrDevice] = []

    for response in responses:
        location = response.get("location")
        if not location or location in seen_locations:
            continue
        seen_locations.add(location)

        try:
            upnp_device = await factory.async_create_device(location)
        except Exception as exc:  # noqa: BLE001 - one unreachable/misbehaving device must not sink discovery
            logger.warning("could not fetch device description from %s: %s", location, exc)
            continue

        if not DmrDevice.is_profile_device(upnp_device):
            continue
        devices.append(DmrDevice(upnp_device, event_handler=None))

    return devices
