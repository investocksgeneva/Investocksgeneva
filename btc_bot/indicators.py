"""EMA crossover signal generation."""

from __future__ import annotations

import pandas as pd

from .config import CFG


def add_emas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ema_fast"] = df["close"].ewm(span=CFG.ema_fast, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=CFG.ema_slow, adjust=False).mean()
    return df


def add_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add 'signal' column: +1 on bullish cross (fast > slow after being <=),
    -1 on bearish cross, 0 otherwise.
    """
    df = add_emas(df)
    above = df["ema_fast"] > df["ema_slow"]
    df["signal"] = 0
    df.loc[above & ~above.shift(1).fillna(False), "signal"] = 1   # golden cross
    df.loc[~above & above.shift(1).fillna(True), "signal"] = -1   # death cross
    return df


def current_signal(df: pd.DataFrame) -> int:
    """Return the signal on the most recent fully-closed candle."""
    df = add_signals(df)
    return int(df["signal"].iloc[-1])


def current_emas(df: pd.DataFrame) -> tuple[float, float]:
    df = add_emas(df)
    return float(df["ema_fast"].iloc[-1]), float(df["ema_slow"].iloc[-1])
