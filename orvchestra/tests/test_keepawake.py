from __future__ import annotations

from orvchestra.playback.keepawake import KeepAwakeController


def test_tracks_active_sources_independently():
    controller = KeepAwakeController()
    controller.set_active("browser", True)
    assert "browser" in controller._active_sources

    controller.set_active("dlna:uuid:x", True)
    assert {"browser", "dlna:uuid:x"} == controller._active_sources

    controller.set_active("browser", False)
    assert controller._active_sources == {"dlna:uuid:x"}


def test_caffeinate_missing_binary_does_not_raise(monkeypatch):
    # This test suite doesn't run on macOS, so `caffeinate` genuinely isn't
    # on PATH -- exercising the real FileNotFoundError path, not a mock of it.
    controller = KeepAwakeController()
    controller.set_active("browser", True)
    assert controller.is_running is False  # no crash, just can't actually run it here


def test_shutdown_clears_everything():
    controller = KeepAwakeController()
    controller.set_active("browser", True)
    controller.set_active("dlna:uuid:x", True)
    controller.shutdown()
    assert controller._active_sources == set()
    assert controller.is_running is False
