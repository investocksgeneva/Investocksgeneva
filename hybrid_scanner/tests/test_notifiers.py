import io
import json
import urllib.error
from datetime import datetime

import pytest

from hybrid_scanner import notifiers
from hybrid_scanner.main import alert_header, main
from hybrid_scanner.models import EntrySignal, ScanReport
from hybrid_scanner.notifiers import DiscordNotifier, _pack


def _signal(ticker="NVDA", day=1):
    return EntrySignal(
        ticker=ticker, timestamp=datetime(2026, 10, day), timeframe="1d",
        setup_type="Momentum + 20EMA pullback + hammer", reason="RS rank 90; pullback 6.0%",
        entry_price=100.0, stop_loss=96.0, target_price=108.0, risk_per_share=4.0,
        r_multiple_target=2.0, shares=250, position_value=25_000.0, dollar_risk=1_000.0,
        account_risk_pct=0.01, atr=2.5, stop_atr_multiple=1.6, triggers=["hammer"],
    )


def test_pack_respects_limit_and_order():
    blocks = [f"block-{i}-" + "x" * 300 for i in range(20)]
    msgs = _pack(blocks, 1900)
    assert all(len(m) <= 1900 for m in msgs)
    assert "\n\n".join(msgs).split("\n\n") == blocks
    assert len(msgs) < len(blocks)


def test_discord_posts_header_even_without_signals(monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://example.invalid/hook")
    d = DiscordNotifier(header="**Weekly** — No new entry signals.", dry_run=True)
    d.send([])
    assert len(d.payloads) == 1 and "No new entry signals" in d.payloads[0]["content"]
    assert d.payloads[0]["allowed_mentions"] == {"parse": []}


def test_discord_batches_many_signals():
    d = DiscordNotifier(header="hdr", dry_run=True)
    sigs = [_signal(f"T{i}") for i in range(30)]
    d.send(sigs)
    assert 1 < len(d.payloads) < 30
    text = "".join(p["content"] for p in d.payloads)
    assert all(f"**T{i}**" in text for i in range(30))
    assert all(len(p["content"]) <= 2000 for p in d.payloads)


def test_live_discord_requires_webhook(monkeypatch):
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    with pytest.raises(ValueError):
        DiscordNotifier(dry_run=False)


class _Resp:
    status = 204

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http_error(code, body=b"{}"):
    return urllib.error.HTTPError("https://example.invalid", code, "err", {}, io.BytesIO(body))


def test_rate_limit_is_retried(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout):
        calls.append(req)
        if len(calls) == 1:
            raise _http_error(429, json.dumps({"retry_after": 0.01}).encode())
        return _Resp()

    monkeypatch.setattr(notifiers.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(notifiers.time, "sleep", lambda s: None)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://example.invalid/hook")
    d = DiscordNotifier(header="hdr", dry_run=False)
    d.send([_signal()])
    assert len(calls) == 2 and d.ok
    assert calls[0].get_header("User-agent").startswith("hybrid-scanner")


def test_delivery_failure_is_counted_not_raised(monkeypatch):
    def fake_urlopen(req, timeout):
        raise _http_error(403)

    monkeypatch.setattr(notifiers.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://example.invalid/hook")
    d = DiscordNotifier(header="hdr", dry_run=False)
    d.send([_signal()])
    assert not d.ok and d.failures == 1


def test_alert_header_contents():
    report = ScanReport(as_of=datetime(2026, 10, 9), signals=[], momentum_candidates=[], rejections=[],
                        errors={"XYZ": "no data"})
    h = alert_header(report, [_signal()], 5, "Weekly hybrid scan", 503)
    assert "Weekly hybrid scan — 2026-10-09" in h
    assert "503 tickers" in h and "1 signal(s)" in h and "last 5 bars" in h and "data errors" in h
    assert "No new entry signals" in alert_header(report, [], 1, "Scan", 10)


def test_cli_live_alert_without_secret_exits_2(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    assert main(["--source", "synthetic", "--notify", "discord", "--live-alerts"]) == 2


def test_cli_alert_window_dry_run(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["--source", "synthetic", "--alert-window", "80", "--notify", "discord", "--export"]) == 0
    import pandas as pd

    df = pd.read_csv(tmp_path / "output" / "signals.csv")
    assert len(df) > 0
    assert not df.duplicated(["ticker", "timestamp"]).any()
