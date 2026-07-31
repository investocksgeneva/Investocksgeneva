"""Tests for run_backtest_pipeline — 12 tests (fully mocked)."""

from __future__ import annotations

import csv
import io
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from src.backtesting.backtester import BacktestResult, TradeRecord
from src.pipeline.run_backtest_pipeline import (
    _print_performance,
    _write_trades_csv,
    run_fetch_to_backtest,
)
from src.pipeline.run_fcsp_pipeline import PipelineResult


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_pipeline_result(n: int = 50) -> PipelineResult:
    idx = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")
    p = np.linspace(50_000, 55_000, n)
    ohlcv = pd.DataFrame(
        {"open": p, "high": p * 1.01, "low": p * 0.99, "close": p, "volume": np.ones(n)},
        index=idx,
    )
    return PipelineResult(
        merged_data=ohlcv, ohlcv_rows=n, funding_nan_count=0, etf_flow_nan_count=3
    )


def _mock_backtest_result(n: int = 50) -> BacktestResult:
    idx = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")
    equity = pd.Series(np.linspace(100_000, 105_000, n), index=idx)
    trades = [
        TradeRecord(
            entry_time=pd.Timestamp("2024-01-10", tz="UTC"),
            entry_price=50_000.0,
            exit_time=pd.Timestamp("2024-01-13", tz="UTC"),
            exit_price=53_000.0,
            size=0.05,
            stop_price=48_000.0,
            tp_price=56_000.0,
            pnl_usdt=150.0,
            pnl_pct=3.0,
            exit_reason="take_profit",
            hold_days=3.0,
        ),
        TradeRecord(
            entry_time=pd.Timestamp("2024-01-20", tz="UTC"),
            entry_price=52_000.0,
            exit_time=pd.Timestamp("2024-01-23", tz="UTC"),
            exit_price=51_000.0,
            size=0.05,
            stop_price=50_000.0,
            tp_price=55_000.0,
            pnl_usdt=-50.0,
            pnl_pct=-1.9,
            exit_reason="stop_loss",
            hold_days=3.0,
        ),
    ]
    return BacktestResult(trades=trades, equity_curve=equity, initial_equity=100_000.0)


# ── Orchestration ─────────────────────────────────────────────────────────────

def test_run_fetch_to_backtest_calls_pipeline():
    with patch("src.pipeline.run_backtest_pipeline.run_pipeline") as mock_pipe, \
         patch("src.pipeline.run_backtest_pipeline.run_backtest") as mock_bt:
        mock_pipe.return_value = _mock_pipeline_result()
        mock_bt.return_value = _mock_backtest_result()
        run_fetch_to_backtest(start=datetime(2024, 1, 1, tzinfo=timezone.utc))
        mock_pipe.assert_called_once()


def test_run_fetch_to_backtest_calls_backtest_with_merged_data():
    """The merged_data from run_pipeline must be passed directly to run_backtest."""
    with patch("src.pipeline.run_backtest_pipeline.run_pipeline") as mock_pipe, \
         patch("src.pipeline.run_backtest_pipeline.run_backtest") as mock_bt:
        pr = _mock_pipeline_result()
        mock_pipe.return_value = pr
        mock_bt.return_value = _mock_backtest_result()

        run_fetch_to_backtest(start=datetime(2024, 1, 1, tzinfo=timezone.utc))

        call_args = mock_bt.call_args
        # First positional arg to run_backtest must be the same DataFrame object
        assert call_args[0][0] is pr.merged_data


def test_run_fetch_to_backtest_returns_tuple():
    with patch("src.pipeline.run_backtest_pipeline.run_pipeline") as mock_pipe, \
         patch("src.pipeline.run_backtest_pipeline.run_backtest") as mock_bt:
        mock_pipe.return_value = _mock_pipeline_result()
        mock_bt.return_value = _mock_backtest_result()
        result = run_fetch_to_backtest(start=datetime(2024, 1, 1, tzinfo=timezone.utc))
        assert isinstance(result, tuple)
        assert len(result) == 2


def test_pipeline_error_propagates():
    with patch("src.pipeline.run_backtest_pipeline.run_pipeline") as mock_pipe:
        mock_pipe.side_effect = RuntimeError("fetch failed")
        with pytest.raises(RuntimeError, match="fetch failed"):
            run_fetch_to_backtest(start=datetime(2024, 1, 1, tzinfo=timezone.utc))


def test_risk_pct_forwarded_to_backtest():
    with patch("src.pipeline.run_backtest_pipeline.run_pipeline") as mock_pipe, \
         patch("src.pipeline.run_backtest_pipeline.run_backtest") as mock_bt:
        mock_pipe.return_value = _mock_pipeline_result()
        mock_bt.return_value = _mock_backtest_result()
        run_fetch_to_backtest(start=datetime(2024, 1, 1, tzinfo=timezone.utc), risk_pct=0.02)
        _, kwargs = mock_bt.call_args
        assert kwargs.get("risk_pct") == 0.02


def test_execution_timing_forwarded():
    with patch("src.pipeline.run_backtest_pipeline.run_pipeline") as mock_pipe, \
         patch("src.pipeline.run_backtest_pipeline.run_backtest") as mock_bt:
        mock_pipe.return_value = _mock_pipeline_result()
        mock_bt.return_value = _mock_backtest_result()
        run_fetch_to_backtest(
            start=datetime(2024, 1, 1, tzinfo=timezone.utc), execution_timing="close"
        )
        _, kwargs = mock_bt.call_args
        assert kwargs.get("execution_timing") == "close"


# ── Output formatting ──────────────────────────────────────────────────────────

def test_print_performance_does_not_raise(capsys):
    _print_performance(_mock_backtest_result())
    out = capsys.readouterr().out
    assert "Sharpe" in out or "sharpe" in out.lower()


def test_print_performance_shows_total_return(capsys):
    _print_performance(_mock_backtest_result())
    out = capsys.readouterr().out
    assert "return" in out.lower()


def test_zero_trades_performance_prints_na(capsys):
    idx = pd.date_range("2024-01-01", periods=10, freq="D", tz="UTC")
    result = BacktestResult(
        trades=[],
        equity_curve=pd.Series(100_000.0, index=idx),
        initial_equity=100_000.0,
    )
    _print_performance(result)
    out = capsys.readouterr().out
    assert "0" in out


# ── CSV output ────────────────────────────────────────────────────────────────

def test_write_trades_csv_creates_file(tmp_path):
    path = str(tmp_path / "trades.csv")
    _write_trades_csv(_mock_backtest_result(), path)
    with open(path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 2


def test_write_trades_csv_correct_columns(tmp_path):
    path = str(tmp_path / "trades.csv")
    _write_trades_csv(_mock_backtest_result(), path)
    with open(path) as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames
    assert "pnl_usdt" in cols
    assert "exit_reason" in cols


def test_write_trades_csv_no_trades_prints_message(capsys, tmp_path):
    path = str(tmp_path / "empty.csv")
    idx = pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC")
    result = BacktestResult(trades=[], equity_curve=pd.Series(100_000.0, index=idx), initial_equity=100_000.0)
    _write_trades_csv(result, path)
    out = capsys.readouterr().out
    assert "No trades" in out
