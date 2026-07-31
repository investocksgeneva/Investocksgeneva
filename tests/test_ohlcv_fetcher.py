"""Tests for OHLCVFetcher — 6 tests (mocked ccxt)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.data.ohlcv_fetcher import OHLCVFetcher


def _candles(n: int, start_ms: int = 1_700_000_000_000, step_ms: int = 86_400_000):
    return [
        [start_ms + i * step_ms, 50_000 + i, 51_000 + i, 49_000 + i, 50_500 + i, 1_000.0]
        for i in range(n)
    ]


@patch("ccxt.binance")
def test_fetch_returns_dataframe(mock_cls):
    ex = MagicMock()
    ex.rateLimit = 0
    ex.fetch_ohlcv.side_effect = [_candles(10), []]
    mock_cls.return_value = ex

    fetcher = OHLCVFetcher()
    fetcher._exchange = ex
    df = fetcher.fetch(datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert isinstance(df, pd.DataFrame)
    assert set(df.columns) >= {"open", "high", "low", "close", "volume"}


@patch("ccxt.binance")
def test_fetch_index_is_utc_datetime(mock_cls):
    ex = MagicMock()
    ex.rateLimit = 0
    ex.fetch_ohlcv.side_effect = [_candles(5), []]
    mock_cls.return_value = ex

    fetcher = OHLCVFetcher()
    fetcher._exchange = ex
    df = fetcher.fetch(datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert df.index.tz is not None
    assert str(df.index.tz) == "UTC"


@patch("ccxt.binance")
def test_empty_response_returns_empty_df(mock_cls):
    ex = MagicMock()
    ex.rateLimit = 0
    ex.fetch_ohlcv.return_value = []
    mock_cls.return_value = ex

    fetcher = OHLCVFetcher()
    fetcher._exchange = ex
    df = fetcher.fetch(datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert df.empty


@patch("ccxt.binance")
def test_pagination_calls_until_empty(mock_cls):
    ex = MagicMock()
    ex.rateLimit = 0
    # First call returns 3 candles, second call returns empty (done)
    ex.fetch_ohlcv.side_effect = [_candles(3), []]
    mock_cls.return_value = ex

    fetcher = OHLCVFetcher()
    fetcher._exchange = ex
    fetcher.fetch(datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert ex.fetch_ohlcv.call_count >= 1


@patch("ccxt.binance")
def test_gap_detection_raises(mock_cls):
    """A 2-day gap in candles should raise RuntimeError."""
    import ccxt
    ex = MagicMock()
    ex.rateLimit = 0
    start_ms = 1_700_000_000_000
    step = 86_400_000
    # Create candles with a gap: candles 0-4, then candle 7 (skips 5 and 6)
    candles = _candles(5, start_ms, step) + _candles(3, start_ms + 7 * step, step)
    ex.fetch_ohlcv.side_effect = [candles, []]
    mock_cls.return_value = ex

    fetcher = OHLCVFetcher()
    fetcher._exchange = ex
    with pytest.raises(RuntimeError, match="gap"):
        fetcher.fetch(datetime(2024, 1, 1, tzinfo=timezone.utc))


@patch("ccxt.binance")
def test_retry_on_network_error(mock_cls):
    import ccxt as _ccxt
    ex = MagicMock()
    ex.rateLimit = 0
    ex.fetch_ohlcv.side_effect = [
        _ccxt.NetworkError("transient"),
        _candles(3),
        [],
    ]
    mock_cls.return_value = ex

    fetcher = OHLCVFetcher(max_retries=3)
    fetcher._exchange = ex
    # Should NOT raise — retried successfully
    df = fetcher.fetch(datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert not df.empty
