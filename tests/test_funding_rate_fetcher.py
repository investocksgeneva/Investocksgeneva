"""Tests for FundingRateFetcher — 11 tests (mocked ccxt)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.data.funding_rate_fetcher import FundingRateFetcher


def _funding_records(n_days: int, start_ms: int = 1_704_067_200_000):
    """Generate 3 8-hour records per day aligned to UTC midnight (2024-01-01T00:00Z)."""
    day_ms = 24 * 3_600_000
    interval = 8 * 3_600_000
    records = []
    for d in range(n_days):
        for p in range(3):
            records.append({
                "timestamp": start_ms + d * day_ms + p * interval,
                "fundingRate": 0.0001 * (d + 1),
                "symbol": "BTC/USDT:USDT",
            })
    return records


def _patched_fetcher():
    fetcher = FundingRateFetcher()
    ex = MagicMock()
    ex.rateLimit = 0
    fetcher._exchange = ex
    return fetcher, ex


def test_fetch_returns_dataframe():
    fetcher, ex = _patched_fetcher()
    ex.fetch_funding_rate_history.side_effect = [_funding_records(5), []]
    df = fetcher.fetch(datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert isinstance(df, pd.DataFrame)


def test_funding_rate_column_present():
    fetcher, ex = _patched_fetcher()
    ex.fetch_funding_rate_history.side_effect = [_funding_records(5), []]
    df = fetcher.fetch(datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert "funding_rate" in df.columns


def test_daily_aggregation_sums_three_periods():
    """Three 8-hour rates of 0.0001 each → daily rate of 0.0003."""
    fetcher, ex = _patched_fetcher()
    # Use midnight-aligned timestamps: 2024-01-01 00:00, 08:00, 16:00 UTC
    midnight = 1_704_067_200_000
    records = [
        {"timestamp": midnight, "fundingRate": 0.0001, "symbol": "BTC/USDT:USDT"},
        {"timestamp": midnight + 8 * 3_600_000, "fundingRate": 0.0001, "symbol": "BTC/USDT:USDT"},
        {"timestamp": midnight + 16 * 3_600_000, "fundingRate": 0.0001, "symbol": "BTC/USDT:USDT"},
    ]
    ex.fetch_funding_rate_history.side_effect = [records, []]
    df = fetcher.fetch(datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert len(df) == 1
    assert df["funding_rate"].iloc[0] == pytest.approx(0.0003, rel=1e-5)


def test_index_is_utc():
    fetcher, ex = _patched_fetcher()
    ex.fetch_funding_rate_history.side_effect = [_funding_records(3), []]
    df = fetcher.fetch(datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert df.index.tz is not None


def test_empty_response_returns_empty_df():
    fetcher, ex = _patched_fetcher()
    ex.fetch_funding_rate_history.return_value = []
    df = fetcher.fetch(datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert df.empty


def test_gap_detection_raises():
    """Missing a full calendar day should raise RuntimeError."""
    fetcher, ex = _patched_fetcher()
    # Day 0 and day 2 records only — day 1 skipped; all aligned to UTC midnight
    midnight = 1_704_067_200_000   # 2024-01-01T00:00Z
    day = 24 * 3_600_000
    records = _funding_records(1, midnight) + _funding_records(1, midnight + 2 * day)
    ex.fetch_funding_rate_history.side_effect = [records, []]
    with pytest.raises(RuntimeError, match="missing"):
        fetcher.fetch(datetime(2024, 1, 1, tzinfo=timezone.utc))


def test_retry_on_network_error():
    import ccxt as _ccxt
    fetcher, ex = _patched_fetcher()
    ex.fetch_funding_rate_history.side_effect = [
        _ccxt.NetworkError("timeout"),
        _funding_records(3),
        [],
    ]
    df = fetcher.fetch(datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert not df.empty


def test_negative_funding_rates_preserved():
    """Negative rates (overcrowded shorts) must not be clipped."""
    fetcher, ex = _patched_fetcher()
    records = [
        {"timestamp": 1_700_000_000_000 + i * 8 * 3_600_000, "fundingRate": -0.0001, "symbol": "X"}
        for i in range(3)
    ]
    ex.fetch_funding_rate_history.side_effect = [records, []]
    df = fetcher.fetch(datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert df["funding_rate"].iloc[0] < 0


def test_multiple_days_correct_row_count():
    fetcher, ex = _patched_fetcher()
    ex.fetch_funding_rate_history.side_effect = [_funding_records(7), []]
    df = fetcher.fetch(datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert len(df) == 7


def test_sorted_ascending():
    fetcher, ex = _patched_fetcher()
    ex.fetch_funding_rate_history.side_effect = [_funding_records(5), []]
    df = fetcher.fetch(datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert df.index.is_monotonic_increasing


def test_duplicate_timestamps_deduplicated():
    fetcher, ex = _patched_fetcher()
    records = _funding_records(3)
    # Duplicate the first record
    records = [records[0]] + records
    ex.fetch_funding_rate_history.side_effect = [records, []]
    # Should not raise
    df = fetcher.fetch(datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert not df.empty
