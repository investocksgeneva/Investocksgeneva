import numpy as np
import pandas as pd
import pytest

from hybrid_scanner.backtest import simulate
from hybrid_scanner.portfolio import PortfolioBacktester


@pytest.fixture(scope="module")
def history(generator, prepared):
    return {t: generator.signal_history(p) for t, p in prepared.items()}


@pytest.fixture(scope="module")
def start(generator, prepared):
    return min(p.df.index[generator.warmup_bars] for p in prepared.values())


def _run(cfg, prepared, history, start, bench=None, **overrides):
    c = cfg.with_overrides({f"backtest.{k}": v for k, v in overrides.items()})
    return PortfolioBacktester(c).run(prepared, history, bench, start)


def test_unconstrained_portfolio_matches_single_ticker_simulator(cfg, prepared, history, start):
    """Two independent engines must agree trade-for-trade when no portfolio
    constraint binds — the strongest check on the accounting."""
    res = _run(cfg, prepared, history, start, max_positions=10_000, max_portfolio_heat_pct=100.0,
               max_gross_exposure=1_000.0, min_size_fraction=0.0)
    single = pd.concat([simulate(prepared[t].df, s, cfg.backtest) for t, s in history.items() if s])
    key = ["ticker", "signal_time"]
    a = res.trades.set_index(key).sort_index()
    b = single.set_index(key).sort_index()
    assert a.index.equals(b.index)
    np.testing.assert_allclose(a["r_multiple"], b["r_multiple"], atol=1e-9)
    assert (a["exit_reason"] == b["exit_reason"]).all()


@pytest.mark.parametrize("max_pos", [1, 2, 3])
def test_position_limit_respected(cfg, prepared, history, start, max_pos):
    res = _run(cfg, prepared, history, start, max_positions=max_pos)
    assert res.equity_curve["n_positions"].max() <= max_pos


def test_one_slot_means_no_overlapping_trades(cfg, prepared, history, start):
    res = _run(cfg, prepared, history, start, max_positions=1)
    tr = res.trades.sort_values("entry_time")
    # Next entry never before the previous exit.
    assert (tr["entry_time"].iloc[1:].to_numpy() >= tr["exit_time"].iloc[:-1].to_numpy()).all()
    assert "max_positions" in set(res.skipped["reason"])


def test_heat_cap_respected(cfg, prepared, history, start):
    cap = 0.012
    res = _run(cfg, prepared, history, start, max_portfolio_heat_pct=cap, min_size_fraction=0.0)
    # Heat is measured vs equity at entry; allow small drift from MTM moves.
    assert res.equity_curve["heat_pct"].max() <= cap * 1.15


def test_cash_account_never_borrows(cfg, prepared, history, start):
    res = _run(cfg, prepared, history, start, max_gross_exposure=1.0)
    ec = res.equity_curve
    assert (ec["cash"] >= -1e-6).all()
    np.testing.assert_allclose(ec["equity"], ec["cash"] + ec["exposure"])


def test_equity_reconciles_with_trade_pnl(cfg, prepared, history, start):
    res = _run(cfg, prepared, history, start)
    capital0 = cfg.risk.account_equity
    # Every trade (incl. still-open ones marked at the last close) explains the final equity.
    assert res.equity_curve["equity"].iloc[-1] == pytest.approx(capital0 + res.trades["pnl"].sum(), rel=1e-9)


def test_metrics_and_benchmark(cfg, prepared, history, start, universe):
    _, bench = universe
    res = _run(cfg, prepared, history, start, bench)
    m = res.metrics
    for k in ("cagr", "sharpe", "max_drawdown", "time_in_market", "beta", "benchmark_total_return"):
        assert k in m
    assert -1 <= m["max_drawdown"] <= 0
    assert m["signals_total"] == sum(len(v) for v in history.values())


def test_invalid_priority_rejected(cfg):
    with pytest.raises(ValueError):
        cfg.with_overrides({"backtest.signal_priority": "vibes"}).validate()
