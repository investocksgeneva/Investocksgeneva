from __future__ import annotations

import subprocess

from orvchestra import network

# A trimmed but real excerpt of `ifconfig` output from the exact machine that
# surfaced this bug: a real Wi-Fi address alongside a Tailscale tunnel
# interface (point-to-point, /32 netmask) that was getting picked instead.
_REAL_IFCONFIG_OUTPUT = """\
lo0: flags=8049<UP,LOOPBACK,RUNNING,MULTICAST> mtu 16384
	inet 127.0.0.1 netmask 0xff000000
en0: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500
	inet 192.168.1.12 netmask 0xffffff00 broadcast 192.168.1.255
utun4: flags=8051<UP,POINTOPOINT,RUNNING,MULTICAST> mtu 1280
	inet 100.83.114.77 --> 100.83.114.77 netmask 0xffffffff
"""


class _FakeCompletedProcess:
    def __init__(self, stdout: str) -> None:
        self.stdout = stdout


def test_picks_real_lan_address_over_tailscale_tunnel(monkeypatch):
    def fake_run(args, **kwargs):
        assert args == ["ifconfig"]
        return _FakeCompletedProcess(_REAL_IFCONFIG_OUTPUT)

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert network.detect_lan_ip() == "192.168.1.12"


def test_ignores_point_to_point_interfaces():
    found = network._IFCONFIG_RE.findall(_REAL_IFCONFIG_OUTPUT)
    assert ("100.83.114.77", "ffffffff") in found
    assert not network._is_real_lan_address("100.83.114.77")  # CGNAT range, excluded regardless


def test_prefers_192_168_over_10_range():
    assert network._rank("192.168.1.5") < network._rank("10.0.0.5")


def test_falls_back_when_no_interfaces_found(monkeypatch):
    def fake_run(args, **kwargs):
        raise FileNotFoundError("no such command")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(network, "_socket_trick_local_ip", lambda: "203.0.113.5")
    assert network.detect_lan_ip() == "203.0.113.5"
