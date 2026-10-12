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
               "--notify", "console", "discord", "--portfolio", "--set", "risk.target_r_multiple=2.5"])
    assert rc == 0
    assert (tmp_path / "output" / "rejections.csv").exists()
    assert (tmp_path / "output" / "equity_curve.csv").exists()
    assert (tmp_path / "output" / "plots" / "portfolio_equity.png").exists()


def test_cached_provider_fetches_once(tmp_path):
    from hybrid_scanner.utils import CachedProvider, SyntheticProvider

    class Counting(SyntheticProvider):
        calls = 0

        def get_history(self, ticker, timeframe="1d", period=""):
            Counting.calls += 1
            return super().get_history(ticker, timeframe, period)

    cp = CachedProvider(Counting(n_bars=300), tmp_path)
    first = cp.get_many(["AAA", "BBB"], "1d", "2y")
    second = cp.get_many(["AAA", "BBB"], "1d", "2y")
    assert Counting.calls == 2
    for t in ("AAA", "BBB"):
        pd.testing.assert_frame_equal(first[t], second[t], check_freq=False, atol=1e-9)
    CachedProvider(Counting(n_bars=300), tmp_path, refresh=True).get_many(["AAA"], "1d", "2y")
    assert Counting.calls == 3


def test_sp500_universe_file():
    from pathlib import Path

    from hybrid_scanner.utils import read_watchlist

    tickers = read_watchlist(Path(__file__).parents[1] / "universes" / "sp500.csv")
    assert len(tickers) > 490 and "BRK-B" in tickers and "AAPL" in tickers


def _yf_frame(tickers, n=300):
    """Mimic yfinance's group_by='ticker' MultiIndex layout."""
    from hybrid_scanner.utils import SyntheticProvider

    prov = SyntheticProvider(n_bars=n)
    frames = {t: prov.get_history(t).rename(columns=str.title) for t in tickers}
    return pd.concat(frames, axis=1)


def test_yfinance_retries_failed_tickers_serially():
    from hybrid_scanner.utils import YFinanceProvider

    calls = []

    def fake_download(tickers, threads, **kw):
        calls.append((list(tickers), threads))
        if threads:  # threaded pass: simulate the SQLite 'database is locked' drop-out
            return _yf_frame([t for t in tickers if t != "CDNS"])
        return _yf_frame(tickers)

    prov = YFinanceProvider(download=fake_download)
    out = prov.get_many(["AAPL", "CDNS", "MSFT"], "1d", "2y")
    assert set(out) == {"AAPL", "CDNS", "MSFT"}
    assert calls[-1] == (["CDNS"], False)  # only the failure retried, without threads


def test_yfinance_gives_up_after_one_retry():
    from hybrid_scanner.utils import YFinanceProvider

    calls = []

    def fake_download(tickers, threads, **kw):
        calls.append(threads)
        return _yf_frame([t for t in tickers if t != "GONE"])

    out = YFinanceProvider(download=fake_download).get_many(["AAPL", "GONE"], "1d", "2y")
    assert set(out) == {"AAPL"} and calls == [True, False]


def test_yfinance_batch_exception_does_not_abort():
    from hybrid_scanner.utils import YFinanceProvider

    def boom(tickers, threads, **kw):
        raise ConnectionError("network down")

    assert YFinanceProvider(download=boom).get_many(["AAPL"], "1d", "2y") == {}


def test_short_history_reported_separately():
    from hybrid_scanner.utils import SyntheticProvider, load_universe

    class Mixed(SyntheticProvider):
        def get_history(self, ticker, timeframe="1d", period=""):
            df = super().get_history(ticker, timeframe, period)
            return df.iloc[-50:] if ticker == "NEWIPO" else df

    short: dict[str, str] = {}
    data, errors = load_universe(Mixed(n_bars=300), ["AAPL", "NEWIPO"], "1d", "2y", 260, short)
    assert set(data) == {"AAPL"} and errors == {} and "NEWIPO" in short
    # Without the sink, behaviour is unchanged (backward compatible).
    data, errors = load_universe(Mixed(n_bars=300), ["AAPL", "NEWIPO"], "1d", "2y", 260)
    assert "NEWIPO" in errors


# --- unfinished daily bar (US session still open) ----------------------------
def _bars(last_day):
    idx = pd.date_range(end=last_day, periods=5, freq="B")
    return pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}, index=idx)


def test_drop_incomplete_bar_during_session():
    from datetime import datetime

    from hybrid_scanner.utils import NEW_YORK, drop_incomplete_daily_bar

    df = _bars("2026-10-12")  # Monday
    mid_session = datetime(2026, 10, 12, 11, 0, tzinfo=NEW_YORK)
    after_close = datetime(2026, 10, 12, 16, 45, tzinfo=NEW_YORK)
    next_morning = datetime(2026, 10, 13, 2, 0, tzinfo=NEW_YORK)
    assert drop_incomplete_daily_bar(df, mid_session).index[-1] == pd.Timestamp("2026-10-09")
    assert len(drop_incomplete_daily_bar(df, after_close)) == 5
    assert len(drop_incomplete_daily_bar(df, next_morning)) == 5
    # Geneva wall-clock input is converted: 17:00 CEST = 11:00 New York → still open.
    from zoneinfo import ZoneInfo

    geneva = datetime(2026, 10, 12, 17, 0, tzinfo=ZoneInfo("Europe/Zurich"))
    assert len(drop_incomplete_daily_bar(df, geneva)) == 4


def test_last_daily_close_cutoff():
    from datetime import datetime

    from hybrid_scanner.utils import NEW_YORK, last_daily_close

    assert last_daily_close(datetime(2026, 10, 12, 11, 0, tzinfo=NEW_YORK)) == datetime(2026, 10, 11, 16, 30, tzinfo=NEW_YORK)
    assert last_daily_close(datetime(2026, 10, 12, 17, 0, tzinfo=NEW_YORK)) == datetime(2026, 10, 12, 16, 30, tzinfo=NEW_YORK)


def test_cache_saved_mid_session_is_refetched_after_close(tmp_path, monkeypatch):
    import os
    import time as _time
    from datetime import datetime

    from hybrid_scanner import utils
    from hybrid_scanner.utils import NEW_YORK, CachedProvider, SyntheticProvider

    class Counting(SyntheticProvider):
        calls = 0

        def get_history(self, ticker, timeframe="1d", period=""):
            Counting.calls += 1
            return super().get_history(ticker, timeframe, period)

    cp = CachedProvider(Counting(n_bars=300), tmp_path)
    cp.get_many(["AAA"], "1d", "2y")
    # Pretend the file was written at 11:00 NY today and it's now 17:00 NY.
    saved = datetime(2026, 10, 12, 11, 0, tzinfo=NEW_YORK).timestamp()
    for f in tmp_path.iterdir():
        os.utime(f, (saved, saved))
    monkeypatch.setattr(utils, "last_daily_close", lambda now=None: datetime(2026, 10, 12, 16, 30, tzinfo=NEW_YORK))
    monkeypatch.setattr(_time, "time", lambda: datetime(2026, 10, 12, 17, 0, tzinfo=NEW_YORK).timestamp())
    cp.get_many(["AAA"], "1d", "2y")
    assert Counting.calls == 2  # refetched, not served from the mid-session cache
