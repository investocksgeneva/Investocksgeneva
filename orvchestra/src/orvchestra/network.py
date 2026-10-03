"""Picks the IP address Orvchestra advertises to the DLNA network and hands
out in /art, /track URLs -- the one address every other device (phone, the
WiiM) needs to be able to reach regardless of how *they* got to the web app.

async_upnp_client's own `get_local_ip()` opens a UDP socket "connected" to a
public address and reads back whatever local address the OS routing table
picked for it -- normally fine, but a VPN/mesh-networking client (Tailscale,
a corporate VPN) can make the OS prefer its own tunnel interface over the
real LAN one, especially right after connecting. Pick from the machine's own
interface list instead, filtering for what's actually a real LAN address,
so a VPN being active never routes media URLs through an address the phone
and the WiiM have no way to reach.
"""

from __future__ import annotations

import ipaddress
import logging
import re
import subprocess

from async_upnp_client.utils import get_local_ip as _socket_trick_local_ip

logger = logging.getLogger("orvchestra.network")

# A tunnel interface's own overlay range (Tailscale, and the CGNAT space
# some VPNs reuse) -- never a real LAN a phone sitting on plain Wi-Fi shares.
_CGNAT_RANGE = ipaddress.ip_network("100.64.0.0/10")

# Preference order when more than one real LAN candidate is found: the
# conventional home-router range first, since it's by far the most common.
_PREFERRED_RANGES = [
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("10.0.0.0/8"),
]

_IFCONFIG_RE = re.compile(r"inet (\d+\.\d+\.\d+\.\d+)(?: --> \d+\.\d+\.\d+\.\d+)? netmask 0x([0-9a-f]{8})")
_IP_ADDR_RE = re.compile(r"inet (\d+\.\d+\.\d+\.\d+)/(\d+)")


def _candidates_from_ifconfig() -> list[str]:
    """macOS (and many Linux systems still ship net-tools' ifconfig too)."""
    output = subprocess.run(["ifconfig"], capture_output=True, text=True, timeout=3).stdout
    found = []
    for ip_text, hex_mask in _IFCONFIG_RE.findall(output):
        prefix = bin(int(hex_mask, 16)).count("1")
        # A point-to-point tunnel interface always has src == dst and a /32
        # mask -- the netmask alone (no broadcast-capable prefix) is the
        # fastest tell, cheaper than re-checking the "-->" text.
        if prefix == 32:
            continue
        found.append(ip_text)
    return found


def _candidates_from_ip_addr() -> list[str]:
    """Linux without ifconfig (iproute2's `ip` is standard on modern distros)."""
    output = subprocess.run(["ip", "-4", "-o", "addr", "show"], capture_output=True, text=True, timeout=3).stdout
    found = []
    for ip_text, prefix_text in _IP_ADDR_RE.findall(output):
        if int(prefix_text) == 32:
            continue
        found.append(ip_text)
    return found


def _is_real_lan_address(ip_text: str) -> bool:
    addr = ipaddress.ip_address(ip_text)
    if addr.is_loopback or addr in _CGNAT_RANGE:
        return False
    return addr.is_private


def _rank(ip_text: str) -> int:
    addr = ipaddress.ip_address(ip_text)
    for i, network in enumerate(_PREFERRED_RANGES):
        if addr in network:
            return i
    return len(_PREFERRED_RANGES)


def detect_lan_ip() -> str:
    candidates: list[str] = []
    for getter in (_candidates_from_ifconfig, _candidates_from_ip_addr):
        try:
            candidates = [ip for ip in getter() if _is_real_lan_address(ip)]
        except (OSError, subprocess.SubprocessError, FileNotFoundError):
            continue
        if candidates:
            break

    if not candidates:
        # Nothing usable found by enumerating interfaces (an unsupported
        # platform, or a genuinely unusual setup) -- fall back to the
        # original heuristic rather than failing to start at all.
        fallback = _socket_trick_local_ip()
        logger.warning("could not enumerate network interfaces; falling back to %s", fallback)
        return fallback

    candidates.sort(key=_rank)
    return candidates[0]
