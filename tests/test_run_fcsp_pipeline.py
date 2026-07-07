"""Tests for run_fcsp_pipeline — 11 tests (mocked fetchers)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from src.pipeline.run_fcsp_pipeline import PipelineResult, merge_data, run_pipeline


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ohlcv(n: int = 50) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")
    p = np.linspace(50_000, 55_000, n)
    return pd.DataFrame(
        {"open": p * 0.999, "high": p * 1.01, "low": p * 0.99, "close": p, "volume": np.ones(n) * 1e6},
        index=idx,
    )


def _funding(n: int = 50) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")
    return pd.DataFrame({"funding_rate": np.random.default_rng(0).uniform(-0.0002, 0.0003, n)}, index=idx)


def _etf(n: int = 50) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")
    return pd.DataFrame({"etf_flow": np.random.default_rng(1).uniform(-100, 500, n)}, index=idx)


# ── merge_data ────────────────────────────────────────────────────────────────

def test_merge_data_returns_dataframe():
    result = merge_data(_ohlcv())
    assert isinstance(result, pd.DataFrame)


def test_merge_data_ohlcv_only_no_extra_columns():
    result = merge_data(_ohlcv())
    assert "funding_rate" not in result.columns
    assert "etf_flow" not in result.columns


def test_merge_data_adds_funding_column():
    result = merge_data(_ohlcv(), funding=_funding())
    assert "funding_rate" in result.columns


def test_merge_data_adds_etf_column():
    result = merge_data(_ohlcv(), etf_flows=_etf())
    assert "etf_flow" in result.columns


def test_merge_data_length_equals_ohlcv():
    ohlcv = _ohlcv(60)
    funding = _funding(50)   # shorter — should not shrink the spine
    result = merge_data(ohlcv, funding=funding)
    assert len(result) == len(ohlcv)


def test_merge_preserves_ohlcv_index():
    ohlcv = _ohlcv(30)
    result = merge_data(ohlcv, funding=_funding(30), etf_flows=_etf(30))
    pd.testing.assert_index_equal(result.index, ohlcv.index.normalize())


# ── run_pipeline abort-on-failure ─────────────────────────────────────────────

def test_pipeline_raises_on_empty_ohlcv():
    with patch("src.pipeline.run_fcsp_pipeline.OHLCVFetcher") as mock_cls:
        mock_cls.return_value.fetch.return_value = pd.DataFrame()
        with pytest.raises(RuntimeError):
            run_pipeline(start=datetime(2024, 1, 1, tzinfo=timezone.utc), skip_funding=True, skip_etf=True)


def test_pipeline_propagates_fetcher_error():
    with patch("src.pipeline.run_fcsp_pipeline.OHLCVFetcher") as mock_cls:
        mock_cls.return_value.fetch.side_effect = RuntimeError("network failure")
        with pytest.raises(RuntimeError, match="network failure"):
            run_pipeline(start=datetime(2024, 1, 1, tzinfo=timezone.utc), skip_funding=True, skip_etf=True)


# ── run_pipeline happy path ────────────────────────────────────────────────────

def test_pipeline_returns_pipeline_result():
    with patch("src.pipeline.run_fcsp_pipeline.OHLCVFetcher") as mock_cls:
        mock_cls.return_value.fetch.return_value = _ohlcv()
        result = run_pipeline(
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            skip_funding=True, skip_etf=True,
        )
    assert isinstance(result, PipelineResult)


def test_pipeline_signal_df_populated_when_generate_signals_true():
    with patch("src.pipeline.run_fcsp_pipeline.OHLCVFetcher") as mock_cls:
        mock_cls.return_value.fetch.return_value = _ohlcv(300)
        result = run_pipeline(
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            skip_funding=True, skip_etf=True,
            generate_signals=True,
        )
    assert result.signal_df is not None
    assert "signal" in result.signal_df.columns
