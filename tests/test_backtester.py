"""Tests for the backtester — 12 tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.backtesting.backtester import (
    BacktestResult,
    TradeRecord,
    compute_metrics,
    run_backtest,
    summarize_by_period,
)
from src.strategies.base import SignalType


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_data(n: int = 100, price: float = 50_000.0) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")
    close = np.full(n, price)
    return pd.DataFrame({
        "open": close * 0.999,
        "high": close * 1.01,
        "low": close * 0.99,
        "close": close,
        "volume": np.ones(n) * 1e6,
        "atr": np.full(n, price * 0.02),
    }, index=idx)


class _FlatStrategy:
    """Always holds — never signals."""
    atr_stop_mult = 2.0
    atr_period = 14

    def __call__(self, df):
        df = df.copy()
        df["signal"] = SignalType.HOLD
        return df


class _BuyOnceStrategy:
    """Signals BUY on bar 5, SELL on bar 20."""
    atr_stop_mult = 2.0
    atr_period = 14

    def __call__(self, df):
        df = df.copy()
        df["signal"] = SignalType.HOLD
        df.iloc[5, df.columns.get_loc("signal")] = SignalType.BUY
        df.iloc[20, df.columns.get_loc("signal")] = SignalType.SELL
        return df


# ── Flat strategy ─────────────────────────────────────────────────────────────

def test_no_signals_means_no_trades():
    result = run_backtest(_make_data(), _FlatStrategy())
    assert len(result.trades) == 0


def test_no_trades_equity_equals_initial():
    result = run_backtest(_make_data(), _FlatStrategy(), initial_equity=100_000)
    assert result.equity_curve.iloc[-1] == pytest.approx(100_000, rel=1e-4)


# ── Basic trade lifecycle ─────────────────────────────────────────────────────

def test_buy_then_sell_creates_one_trade():
    result = run_backtest(_make_data(), _BuyOnceStrategy())
    assert len(result.trades) == 1


def test_trade_exit_reason_signal_exit():
    result = run_backtest(_make_data(), _BuyOnceStrategy())
    assert result.trades[0].exit_reason == "signal_exit"


def test_equity_curve_length_matches_data():
    data = _make_data(50)
    result = run_backtest(data, _FlatStrategy())
    assert len(result.equity_curve) == 50


# ── Stop loss ─────────────────────────────────────────────────────────────────

def test_stop_loss_triggered():
    data = _make_data(50, price=50_000.0)
    # After BUY signal, crash price well below any stop
    data.iloc[7:, data.columns.get_loc("low")] = 1_000.0
    data.iloc[7:, data.columns.get_loc("close")] = 1_000.0

    class _BuyBar5:
        atr_stop_mult = 2.0
        atr_period = 14

        def __call__(self, df):
            df = df.copy()
            df["signal"] = SignalType.HOLD
            df.iloc[5, df.columns.get_loc("signal")] = SignalType.BUY
            return df

    result = run_backtest(data, _BuyBar5())
    exits = {t.exit_reason for t in result.trades}
    assert exits & {"stop_loss", "gap_open"}


# ── Precomputed signals ───────────────────────────────────────────────────────

def test_precomputed_signals_used_instead_of_strategy():
    data = _make_data(40)
    signals = pd.Series(SignalType.HOLD, index=data.index)
    signals.iloc[5] = SignalType.BUY
    signals.iloc[20] = SignalType.SELL

    result = run_backtest(data, strategy=None, precomputed_signals=signals)
    assert len(result.trades) >= 1


def test_precomputed_signals_identity_preserved():
    """The same signal object passed in should reach the backtest unchanged."""
    data = _make_data(30)
    original = pd.Series(SignalType.HOLD, index=data.index)
    original.iloc[3] = SignalType.BUY
    original_copy = original.copy()

    run_backtest(data, strategy=None, precomputed_signals=original)
    # Original must not have been mutated
    pd.testing.assert_series_equal(original, original_copy)


# ── Metrics ───────────────────────────────────────────────────────────────────

def test_compute_metrics_no_trades():
    equity = pd.Series([100_000.0] * 50,
                       index=pd.date_range("2024-01-01", periods=50, freq="D", tz="UTC"))
    result = BacktestResult(trades=[], equity_curve=equity, initial_equity=100_000.0)
    m = compute_metrics(result)
    assert m["total_trades"] == 0
    assert m["total_return"] == pytest.approx(0.0, abs=1e-6)


def test_compute_metrics_positive_pnl():
    equity = pd.Series(
        [100_000.0, 101_000.0, 102_000.0, 105_000.0],
        index=pd.date_range("2024-01-01", periods=4, freq="D", tz="UTC"),
    )
    t = TradeRecord(
        entry_time=pd.Timestamp("2024-01-01", tz="UTC"),
        entry_price=50_000.0,
        exit_time=pd.Timestamp("2024-01-04", tz="UTC"),
        exit_price=52_500.0,
        size=0.1,
        stop_price=49_000.0,
        tp_price=55_000.0,
        pnl_usdt=250.0,
        pnl_pct=5.0,
        exit_reason="take_profit",
        hold_days=3.0,
    )
    result = BacktestResult(trades=[t], equity_curve=equity, initial_equity=100_000.0)
    m = compute_metrics(result)
    assert m["total_trades"] == 1
    assert m["win_rate"] == pytest.approx(100.0)
    assert m["total_return"] > 0


def test_max_drawdown_is_negative_or_zero():
    equity = pd.Series(
        [100_000, 98_000, 95_000, 97_000, 100_000],
        index=pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC"),
    )
    result = BacktestResult(trades=[], equity_curve=equity, initial_equity=100_000.0)
    m = compute_metrics(result)
    assert m["max_drawdown"] <= 0


def test_summarize_by_period_returns_dataframe():
    result = run_backtest(_make_data(365), _FlatStrategy(), initial_equity=100_000.0)
    summary = summarize_by_period(result)
    assert isinstance(summary, pd.DataFrame)
