"""Fetch daily OHLCV candles from any ccxt-supported spot exchange."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import ccxt
import pandas as pd


class OHLCVFetcher:
    """
    Paginated OHLCV fetcher with gap detection and retry.

    Parameters
    ----------
    exchange_id : ccxt exchange id string, e.g. "binance"
    symbol      : market symbol, e.g. "BTC/USDT"
    timeframe   : ccxt timeframe string, e.g. "1d"
    max_retries : number of retries on transient errors
    """

    def __init__(
        self,
        exchange_id: str = "binance",
        symbol: str = "BTC/USDT",
        timeframe: str = "1d",
        max_retries: int = 3,
    ) -> None:
        self.exchange_id = exchange_id
        self.symbol = symbol
        self.timeframe = timeframe
        self.max_retries = max_retries
        self._exchange: Optional[ccxt.Exchange] = None

    def _get_exchange(self) -> ccxt.Exchange:
        if self._exchange is None:
            cls = getattr(ccxt, self.exchange_id)
            self._exchange = cls({"enableRateLimit": True})
        return self._exchange

    def _tf_ms(self) -> int:
        """Return the number of milliseconds in one candle period."""
        mapping = {
            "1m": 60_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000,
            "1h": 3_600_000, "2h": 7_200_000, "4h": 14_400_000,
            "6h": 21_600_000, "12h": 43_200_000, "1d": 86_400_000,
        }
        return mapping.get(self.timeframe, 86_400_000)

    def _fetch_chunk(self, since_ms: int, limit: int = 500) -> list:
        ex = self._get_exchange()
        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                return ex.fetch_ohlcv(self.symbol, self.timeframe, since=since_ms, limit=limit)
            except (ccxt.NetworkError, ccxt.RequestTimeout) as err:
                last_err = err
                time.sleep(2 ** attempt)
        raise RuntimeError(f"OHLCVFetcher: failed after {self.max_retries} retries") from last_err

    def fetch(
        self,
        start: datetime,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV candles from *start* to *end* (inclusive).

        Returns a DataFrame indexed by UTC datetime with columns:
        open, high, low, close, volume.
        Raises RuntimeError if gaps > 1 missing candle are detected.
        """
        if end is None:
            end = datetime.now(timezone.utc)

        since_ms = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)
        tf_ms = self._tf_ms()
        all_candles: list = []

        while since_ms < end_ms:
            chunk = self._fetch_chunk(since_ms)
            if not chunk:
                break
            # Trim to requested end
            chunk = [c for c in chunk if c[0] <= end_ms]
            all_candles.extend(chunk)
            if len(chunk) == 0 or chunk[-1][0] >= end_ms:
                break
            since_ms = chunk[-1][0] + tf_ms
            time.sleep(self._get_exchange().rateLimit / 1000)

        if not all_candles:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        df = pd.DataFrame(
            all_candles, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.drop_duplicates("timestamp").sort_values("timestamp")
        df.set_index("timestamp", inplace=True)

        self._check_gaps(df, tf_ms)
        return df

    def _check_gaps(self, df: pd.DataFrame, tf_ms: int) -> None:
        if len(df) < 2:
            return
        expected = pd.Timedelta(milliseconds=tf_ms)
        diffs = df.index.to_series().diff().dropna()
        bad = diffs[diffs > expected * 1.5]
        if not bad.empty:
            raise RuntimeError(
                f"OHLCVFetcher: detected {len(bad)} gap(s) in {self.symbol} {self.timeframe} data. "
                "Inspect or widen the fetch window."
            )
