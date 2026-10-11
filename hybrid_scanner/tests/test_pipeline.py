import pandas as pd
import pytest

from hybrid_scanner.backtest import simulate, summarize
from hybrid_scanner.config import ScannerConfig
from hybrid_scanner.main import main


def _all_signals(generator, prepared):
    return {t: generator.signal_history(p) for t, p in prepared.items()}


def test_signals_are_generated_and_sane(generator, prepared, cfg):
    sigs = [s for v in _all_signals(generator, prepared).values() for s in v]
    assert len(sigs) > 5
    for s in sigs:
        assert s.stop_loss < s.entry_price < s.target_price
        assert s.dollar_risk <= cfg.risk.account_equity * cfg.risk.risk_per_trade_pct + 1e-6
        assert s.stop_atr_multiple <= cfg.risk.max_stop_atr + 1e-9
        assert s.triggers


def test_one_signal_per_pullback(generator, prepared):
    for sigs in _all_signals(generator, prepared).values():
        highs = [s.metrics["swing_high"] for s in sigs]
        # consecutive signals never share the same swing high
        assert all(a != b for a, b in zip(highs, highs[1:], strict=False))


def test_no_lookahead_signals_reproduce_on_truncated_data(generator, universe):
    """The core integrity test: a signal at bar t must be identical when the
    scanner only sees data up to t (as it would have, live)."""
    data, bench = universe
    prepared = generator.prepare_universe(data, bench)
    history = _all_signals(generator, prepared)
    checked = 0
    for ticker, sigs in history.items():
        for s in sigs[-3:]:
            ts = pd.Timestamp(s.timestamp)
            cut = {t: d.loc[:ts] for t, d in data.items()}
            report = generator.scan(cut, bench.loc[:ts])
            live = {x.ticker: x for x in report.signals}
            assert ticker in live, f"{ticker} @ {ts} not reproduced live"
            a, b = s.model_dump(), live[ticker].model_dump()
            assert a == b, f"{ticker} @ {ts} differs:\n{a}\n{b}"
            checked += 1
    assert checked >= 5


def test_rejections_are_explained(generator, universe):
    data, bench = universe
    report = generator.scan(data, bench)
    for r in report.rejections:
        assert r.rejection_reasons, f"{r.ticker} rejected without a reason"


def test_backtest_runs(generator, prepared, cfg):
    trades = pd.concat([simulate(prepared[t].df, s, cfg.backtest)
                        for t, s in _all_signals(generator, prepared).items() if s])
    stats = summarize(trades)
    assert stats["trades"] > 0
    assert set(trades["exit_reason"]) <= {"stop", "target", "time", "open"}
    # Stops are honoured: no closed loss worse than -1R beyond slippage, except gaps.
    stopped = trades[trades["exit_reason"] == "stop"]
    assert (stopped["exit"] <= stopped["stop"] + 1e-9).all()


def test_config_overrides_and_validation():
    cfg = ScannerConfig().with_overrides({
        "pullback.ma_period": "10", "confirmation.triggers": "hammer,rsi_bounce",
        "risk.min_rr_to_swing_high": "1.5", "mtf.enabled": "false",
    })
    assert cfg.pullback.ma_period == 10
    assert cfg.confirmation.triggers == ("hammer", "rsi_bounce")
    assert cfg.risk.min_rr_to_swing_high == 1.5
    assert cfg.mtf.enabled is False
    with pytest.raises(KeyError):
        ScannerConfig().with_overrides({"pullback.nope": 1})
    with pytest.raises(ValueError):
        ScannerConfig().with_overrides({"confirmation.triggers": "moonphase"}).validate()


def test_config_json_roundtrip(tmp_path):
    cfg = ScannerConfig.for_timeframe("1h")
    cfg.to_json(tmp_path / "c.json")
    assert ScannerConfig.from_json(tmp_path / "c.json") == cfg


def test_hourly_timeframe_runs():
    from hybrid_scanner.signal_generator import HybridSignalGenerator
    from hybrid_scanner.utils import SyntheticProvider

    cfg = ScannerConfig.for_timeframe("1h")
    cfg.output.log_level = "WARNING"
    prov = SyntheticProvider(n_bars=2400)
    data = {t: prov.get_history(t, "1h") for t in ("AAA", "BBB", "CCC")}
    report = HybridSignalGenerator(cfg).scan(data, prov.get_history("SPY", "1h"))
    assert report.as_of is not None


def test_cli_end_to_end(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc = main(["--source", "synthetic", "--recent", "60", "--backtest", "--export", "--plot",
               "--notify", "console", "discord", "--set", "risk.target_r_multiple=2.5"])
    assert rc == 0
    assert (tmp_path / "output" / "rejections.csv").exists()
