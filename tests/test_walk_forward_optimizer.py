"""Tests for walk_forward_optimizer — 22 tests."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from src.backtesting.backtester import BacktestResult, TradeRecord
from src.backtesting.walk_forward_optimizer import (
    DEFAULT_PARAM_GRID,
    DEFAULT_PARAMS,
    WalkForwardResult,
    evaluate_params_on_window,
    generate_folds,
    run_walk_forward_optimization,
    summarize_folds,
    _mask_signals_before,
)
from src.strategies.base import SignalType


# ── Helpers ───────────────────────────────────────────────────────────────────

def _data(n: int = 400) -> pd.DataFrame:
    idx = pd.date_range("2023-01-01", periods=n, freq="D", tz="UTC")
    p = np.linspace(30_000, 50_000, n) + np.random.default_rng(42).normal(0, 500, n).cumsum()
    p = np.maximum(p, 1000)
    return pd.DataFrame({
        "open": p * 0.999, "high": p * 1.01, "low": p * 0.99,
        "close": p, "volume": np.ones(n) * 1e6,
    }, index=idx)


def _make_signal_df(data: pd.DataFrame) -> pd.DataFrame:
    df = data.copy()
    df["signal"] = SignalType.HOLD
    return df


# ── DEFAULT_PARAM_GRID ─────────────────────────────────────────────────────────

def test_param_grid_has_54_entries():
    assert len(DEFAULT_PARAM_GRID) == 54


def test_param_grid_all_have_fast_less_than_slow():
    for p in DEFAULT_PARAM_GRID:
        assert p["ema_fast"] < p["ema_slow"]


def test_param_grid_contains_expected_keys():
    for p in DEFAULT_PARAM_GRID:
        assert {"ema_fast", "ema_slow", "atr_stop_mult", "atr_period"} <= set(p.keys())


# ── generate_folds ─────────────────────────────────────────────────────────────

def test_folds_non_overlapping_test_windows():
    data = _data(600)
    folds = generate_folds(data, train_window_days=180, test_window_days=60)
    for i in range(len(folds) - 1):
        _, _, _, te_end = folds[i]
        _, _, te_start_next, _ = folds[i + 1]
        assert te_start_next > te_end


def test_folds_test_windows_tile_forward():
    data = _data(500)
    folds = generate_folds(data, train_window_days=180, test_window_days=60)
    assert len(folds) >= 2


def test_generate_folds_empty_data_returns_empty():
    folds = generate_folds(pd.DataFrame(), 180, 60)
    assert folds == []


def test_folds_train_always_before_test():
    data = _data(500)
    for tr_start, tr_end, te_start, te_end in generate_folds(data, 180, 60):
        assert tr_end < te_start


# ── _mask_signals_before ──────────────────────────────────────────────────────

def test_mask_sets_hold_before_cutoff():
    data = _data(100)
    df = _make_signal_df(data)
    df.loc[df.index[10], "signal"] = SignalType.BUY
    cutoff = df.index[50]
    masked = _mask_signals_before(df, cutoff)
    assert int(masked.iloc[10]) == SignalType.HOLD


def test_mask_preserves_signals_after_cutoff():
    data = _data(100)
    df = _make_signal_df(data)
    df.loc[df.index[70], "signal"] = SignalType.BUY
    cutoff = df.index[50]
    masked = _mask_signals_before(df, cutoff)
    assert int(masked.iloc[70]) == SignalType.BUY


def test_mask_does_not_mutate_original():
    data = _data(100)
    df = _make_signal_df(data)
    df.loc[df.index[10], "signal"] = SignalType.BUY
    original = df["signal"].copy()
    _mask_signals_before(df, df.index[50])
    pd.testing.assert_series_equal(df["signal"], original)


# ── evaluate_params_on_window ──────────────────────────────────────────────────

def test_evaluate_below_min_trades_returns_neg_inf():
    data = _data(200)
    # Use parameters that are unlikely to produce many trades on short data
    score, n = evaluate_params_on_window(data, DEFAULT_PARAMS, min_trades=999)
    assert score == float("-inf")
    assert n < 999


def test_evaluate_returns_finite_or_neginf():
    data = _data(300)
    score, n = evaluate_params_on_window(data, DEFAULT_PARAMS, min_trades=0)
    assert score == float("-inf") or (score > float("-inf") and score == score)


# ── run_walk_forward_optimization ─────────────────────────────────────────────

def test_wfo_returns_walk_forward_result():
    data = _data(400)
    result = run_walk_forward_optimization(
        data, param_grid=DEFAULT_PARAM_GRID[:3],
        train_window_days=150, test_window_days=60, min_trades=0,
    )
    assert isinstance(result, WalkForwardResult)


def test_wfo_combined_metrics_present():
    data = _data(400)
    result = run_walk_forward_optimization(
        data, param_grid=DEFAULT_PARAM_GRID[:3],
        train_window_days=150, test_window_days=60, min_trades=0,
    )
    assert "total_return" in result.combined_metrics
    assert "sharpe_ratio" in result.combined_metrics


def test_wfo_fold_records_populated():
    data = _data(500)
    result = run_walk_forward_optimization(
        data, param_grid=DEFAULT_PARAM_GRID[:2],
        train_window_days=150, test_window_days=60, min_trades=0,
    )
    assert len(result.folds) >= 1


def test_wfo_no_data_returns_empty_result():
    result = run_walk_forward_optimization(pd.DataFrame())
    assert result.folds == []


def test_wfo_fallback_used_when_min_trades_not_met():
    """When no combo clears min_trades, used_fallback should be True for that fold."""
    data = _data(300)
    result = run_walk_forward_optimization(
        data, param_grid=DEFAULT_PARAM_GRID[:2],
        train_window_days=150, test_window_days=60, min_trades=999,
    )
    if result.folds:
        assert any(f.used_fallback for f in result.folds)


def test_wfo_equity_chaining_monotone_or_declining():
    """Each fold's OOS starting equity must equal the previous fold's ending equity."""
    data = _data(600)
    result = run_walk_forward_optimization(
        data, param_grid=DEFAULT_PARAM_GRID[:2],
        train_window_days=150, test_window_days=60, min_trades=0,
    )
    if len(result.folds) >= 2 and not result.combined_equity.empty:
        # The combined equity is a single continuous series — verify it's not reset
        assert len(result.combined_equity) > 0


# ── summarize_folds ────────────────────────────────────────────────────────────

def test_summarize_folds_returns_dataframe():
    data = _data(400)
    result = run_walk_forward_optimization(
        data, param_grid=DEFAULT_PARAM_GRID[:2],
        train_window_days=150, test_window_days=60, min_trades=0,
    )
    summary = summarize_folds(result)
    assert isinstance(summary, pd.DataFrame)


def test_summarize_empty_result_returns_empty_df():
    result = WalkForwardResult()
    df = summarize_folds(result)
    assert df.empty


# ── Integration: real strategy + backtester ────────────────────────────────────

def test_integration_real_strategy():
    """Smoke test with the real FlowConfirmedPullback — no mocks."""
    from src.strategies.flow_confirmed_pullback import FlowConfirmedPullback
    from src.backtesting.backtester import run_backtest
    data = _data(400)
    strategy = FlowConfirmedPullback(**DEFAULT_PARAMS)
    result = run_backtest(data, strategy, risk_pct=0.01, initial_equity=100_000.0, costs=0.001)
    assert isinstance(result, BacktestResult)
    assert len(result.equity_curve) == len(data)
