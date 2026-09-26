"""A thin proxy onto Radio Browser (radio-browser.info), a free, open,
no-API-key community database of internet radio streams -- the only
internet-dependent part of the radio feature. Playing a station you've
already saved never touches this; it's only used to search for new ones.

Routed through our own backend rather than fetched directly from the web
app so the frontend never needs Radio Browser's CORS posture to cooperate,
and so there's exactly one place that knows its base URL.
"""

from __future__ import annotations

import logging
import ssl
from typing import Any

import aiohttp
import certifi

logger = logging.getLogger("orvchestra.radio")

# A `uv`-managed Python on macOS has no reason to trust the system Keychain's
# root certificates the way a python.org installer's "Install Certificates
# .command" wires up -- without this, verifying radio-browser.info's TLS
# certificate fails with "unable to get local issuer certificate" even
# though the connection itself is fine. certifi ships a trusted CA bundle
# that works the same on every platform, so this never depends on what a
# given machine happens to have configured at the OS level.
_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

# One of Radio Browser's official mirrors. Their docs describe resolving
# `all.api.radio-browser.info` via DNS and picking one at random for load
# balancing across the whole project; a single fixed mirror is a simpler
# choice for a single-user app; swap it here if it ever goes offline.
_BASE_URL = "https://de1.api.radio-browser.info"
_USER_AGENT = "Orvchestra/1.0 (private single-user music player)"
_TIMEOUT = aiohttp.ClientTimeout(total=8)


def _simplify(station: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": station.get("stationuuid"),
        "name": station.get("name") or "Untitled station",
        # url_resolved has already followed redirects; url sometimes hasn't.
        "stream_url": station.get("url_resolved") or station.get("url"),
        "favicon": station.get("favicon") or None,
        "tags": station.get("tags") or None,
        "country": station.get("country") or None,
    }


async def search_stations(query: str, limit: int = 25) -> list[dict[str, Any]]:
    if not query.strip():
        return []
    async with aiohttp.ClientSession(timeout=_TIMEOUT, headers={"User-Agent": _USER_AGENT}) as session:
        async with session.get(
            f"{_BASE_URL}/json/stations/search",
            params={"name": query, "limit": limit, "hidebroken": "true", "order": "votes", "reverse": "true"},
            ssl=_SSL_CONTEXT,
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()

    return [_simplify(s) for s in data if s.get("stationuuid") and (s.get("url_resolved") or s.get("url"))]
