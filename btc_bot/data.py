"""Fetch OHLCV candles from Binance via ccxt."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import ccxt
import pandas as pd

from .config import CFG


def _exchange() -> ccxt.binance:
    params: dict = {"enableRateLimit": True}
    if CFG.api_key:
        params["apiKey"] = CFG.api_key
        params["secret"] = CFG.api_secret
    ex = ccxt.binance(params)
    if CFG.testnet:
        ex.set_sandbox_mode(True)
    return ex


def fetch_ohlcv(days: int | None = None, since_dt: datetime | None = None) -> pd.DataFrame:
    """Return a DataFrame of OHLCV candles sorted ascending."""
    ex = _exchange()
    days = days or CFG.backtest_days

    if since_dt is None:
        since_dt = datetime.now(timezone.utc) - timedelta(days=days)

    since_ms = int(since_dt.timestamp() * 1000)
    all_candles: list = []

    while True:
        candles = ex.fetch_ohlcv(CFG.symbol, CFG.timeframe, since=since_ms, limit=1000)
        if not candles:
            break
        all_candles.extend(candles)
        last_ts = candles[-1][0]
        if len(candles) < 1000:
            break
        since_ms = last_ts + 1
        time.sleep(ex.rateLimit / 1000)

    df = pd.DataFrame(all_candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("timestamp", inplace=True)
    df.sort_index(inplace=True)
    return df


def fetch_latest_price() -> float:
    """Return the latest BTC/USDT mark price."""
    ex = _exchange()
    ticker = ex.fetch_ticker(CFG.symbol)
    return float(ticker["last"])
