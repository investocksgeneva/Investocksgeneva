"""
Fetch perpetual funding rate history from Binance and aggregate to daily.

Binance perpetuals settle funding every 8 hours (00:00, 08:00, 16:00 UTC),
so each calendar day has exactly three funding periods whose rates we sum to
a single daily_funding_rate column.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import ccxt
import pandas as pd


class FundingRateFetcher:
    """
    Parameters
    ----------
    exchange_id : ccxt exchange, must support fetch_funding_rate_history
    symbol      : perpetual market, e.g. "BTC/USDT:USDT"
    max_retries : retries on transient errors
    """

    PERIODS_PER_DAY = 3       # 8-hour funding
    FUNDING_INTERVAL_MS = 8 * 3_600_000

    def __init__(
        self,
        exchange_id: str = "binance",
        symbol: str = "BTC/USDT:USDT",
        max_retries: int = 3,
    ) -> None:
        self.exchange_id = exchange_id
        self.symbol = symbol
        self.max_retries = max_retries
        self._exchange: Optional[ccxt.Exchange] = None

    def _get_exchange(self) -> ccxt.Exchange:
        if self._exchange is None:
            cls = getattr(ccxt, self.exchange_id)
            self._exchange = cls({"enableRateLimit": True})
        return self._exchange

    def _fetch_chunk(self, since_ms: int, limit: int = 500) -> list:
        ex = self._get_exchange()
        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                return ex.fetch_funding_rate_history(
                    self.symbol, since=since_ms, limit=limit
                )
            except (ccxt.NetworkError, ccxt.RequestTimeout) as err:
                last_err = err
                time.sleep(2 ** attempt)
        raise RuntimeError(
            f"FundingRateFetcher: failed after {self.max_retries} retries"
        ) from last_err

    def fetch(
        self,
        start: datetime,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """
        Fetch funding rates from *start* to *end* and return a daily-indexed
        DataFrame with column 'funding_rate' (sum of three 8-hour rates per day).

        Raises RuntimeError if any calendar day is missing all three periods.
        """
        if end is None:
            end = datetime.now(timezone.utc)

        since_ms = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)
        all_records: list[dict] = []

        while since_ms < end_ms:
            chunk = self._fetch_chunk(since_ms)
            if not chunk:
                break
            chunk = [r for r in chunk if r["timestamp"] <= end_ms]
            all_records.extend(chunk)
            if not chunk or chunk[-1]["timestamp"] >= end_ms:
                break
            since_ms = chunk[-1]["timestamp"] + self.FUNDING_INTERVAL_MS
            time.sleep(self._get_exchange().rateLimit / 1000)

        if not all_records:
            return pd.DataFrame(columns=["funding_rate"])

        raw = pd.DataFrame(all_records)
        raw["dt"] = pd.to_datetime(raw["timestamp"], unit="ms", utc=True)
        raw = raw.drop_duplicates("dt").sort_values("dt")

        # Aggregate to daily: sum three 8-hour periods per calendar day
        raw["date"] = raw["dt"].dt.normalize()
        daily = raw.groupby("date")["fundingRate"].sum().rename("funding_rate")
        daily.index = pd.DatetimeIndex(daily.index, tz="UTC")
        daily = daily.sort_index()

        self._check_gaps(daily, start, end)
        return daily.to_frame()

    def _check_gaps(self, daily: pd.Series, start: datetime, end: datetime) -> None:
        if len(daily) < 2:
            return
        expected_days = pd.date_range(
            start=daily.index[0], end=daily.index[-1], freq="D", tz="UTC"
        )
        missing = expected_days.difference(daily.index)
        if len(missing) > 0:
            raise RuntimeError(
                f"FundingRateFetcher: {len(missing)} missing day(s) in funding data: "
                f"{missing[:5].tolist()}"
            )
