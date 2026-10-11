"""
Indicator library — pure pandas/numpy, no TA-library dependency.

Why not ``ta`` / ``pandas-ta``?
    Both work, but they are thin wrappers over the same formulas, have had
    long maintenance gaps, and (at the time of writing) ``ta`` fails to build
    on Python 3.13. Owning ~200 lines of well-tested formulas removes a
    fragile dependency and makes every number auditable.

Causality contract
    Every function here is *causal*: the value at bar ``t`` depends only on
    bars ``<= t``. This is what lets the same code power live scanning and
    backtesting without look-ahead bias. The one subtle case is swing-pivot
    detection, which is handled explicitly in :func:`swing_points`.

Conventions
    Input frames have lowercase ``open, high, low, close, volume`` columns and
    a monotonic ``DatetimeIndex``. Wilder smoothing (RSI, ATR, ADX) uses
    ``ewm(alpha=1/n, adjust=False)``, matching TradingView/TA-Lib to within
    warm-up differences.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

# --------------------------------------------------------------------------- #
# Moving averages & basic transforms
# --------------------------------------------------------------------------- #


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period, min_periods=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    # min_periods avoids trusting an EMA that has barely warmed up.
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def wilder(series: pd.Series, period: int) -> pd.Series:
    """Wilder's smoothing (an EMA with alpha = 1/period)."""
    return series.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def is_rising(series: pd.Series, lookback: int) -> pd.Series:
    """True where the series is higher than it was ``lookback`` bars ago."""
    return series > series.shift(lookback)


def vwap(df: pd.DataFrame, period: int | None = None, anchor: str = "rolling") -> pd.Series:
    """Volume-weighted average price.

    * ``anchor="session"`` — classic intraday VWAP, reset each calendar day.
    * ``anchor="rolling"`` — VWAP of the last ``period`` bars; on daily charts
      this behaves like a volume-weighted moving average.
    """
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    pv = typical * df["volume"]
    if anchor == "session":
        day = df.index.normalize()
        return pv.groupby(day).cumsum() / df["volume"].groupby(day).cumsum().replace(0, np.nan)
    if not period:
        raise ValueError("rolling VWAP requires a period")
    vol = df["volume"].rolling(period, min_periods=period).sum().replace(0, np.nan)
    return pv.rolling(period, min_periods=period).sum() / vol


def moving_average(df: pd.DataFrame, ma_type: str, period: int, vwap_anchor: str = "rolling") -> pd.Series:
    """Dispatch helper so callers can pick the pullback MA from config."""
    if ma_type == "sma":
        return sma(df["close"], period)
    if ma_type == "ema":
        return ema(df["close"], period)
    if ma_type == "vwap":
        return vwap(df, period, anchor=vwap_anchor)
    raise ValueError(f"Unknown ma_type {ma_type!r}")


def roc(series: pd.Series, period: int) -> pd.Series:
    """Rate of change as a fraction (0.10 == +10%)."""
    return series / series.shift(period) - 1.0


# --------------------------------------------------------------------------- #
# Volatility
# --------------------------------------------------------------------------- #


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    ranges = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()],
        axis=1,
    )
    return ranges.max(axis=1)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    return wilder(true_range(df), period)


def atr_contraction_ratio(df: pd.DataFrame, short: int, long: int) -> pd.Series:
    """Short- vs long-window *percentage* true range. Values < 1 indicate
    contracting volatility — the "coiling spring" that often precedes the
    next leg of a leader.

    Percentage, not dollars: in a stock that has risen 50%, dollar ATR rises
    with price, so a raw ATR(10)/ATR(50) ratio is biased upward precisely in
    the leaders we want to find. Normalising each bar's true range by the
    prior close removes that bias.
    """
    tr_pct = true_range(df) / df["close"].shift(1)
    return wilder(tr_pct, short) / wilder(tr_pct, long)


def range_tightness(close: pd.Series, window: int) -> pd.Series:
    """(Highest close − lowest close) / current close over ``window`` bars."""
    return (close.rolling(window).max() - close.rolling(window).min()) / close


# --------------------------------------------------------------------------- #
# Oscillators
# --------------------------------------------------------------------------- #


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = wilder(delta.clip(lower=0.0), period)
    loss = wilder(-delta.clip(upper=0.0), period)
    rs = gain / loss.replace(0, np.nan)
    out = 100.0 - 100.0 / (1.0 + rs)
    # All-gain windows: loss == 0 → RSI is 100 by definition.
    return out.where(loss != 0, 100.0).where(gain.notna())


def stochastic(df: pd.DataFrame, k: int = 14, d: int = 3, smooth: int = 3) -> pd.DataFrame:
    """Slow stochastic. Returns columns ``k`` and ``d`` on a 0–100 scale."""
    lo = df["low"].rolling(k).min()
    hi = df["high"].rolling(k).max()
    raw_k = 100.0 * (df["close"] - lo) / (hi - lo).replace(0, np.nan)
    slow_k = raw_k.rolling(smooth).mean()
    return pd.DataFrame({"k": slow_k, "d": slow_k.rolling(d).mean()}, index=df.index)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(close, fast) - ema(close, slow)
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig}, index=close.index)


def adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Wilder's ADX with +DI / −DI."""
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    tr_s = wilder(true_range(df), period)
    plus_di = 100.0 * wilder(plus_dm, period) / tr_s
    minus_di = 100.0 * wilder(minus_dm, period) / tr_s
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return pd.DataFrame({"adx": wilder(dx, period), "plus_di": plus_di, "minus_di": minus_di}, index=df.index)


# --------------------------------------------------------------------------- #
# Trend structure
# --------------------------------------------------------------------------- #


def ema_stack_aligned(close: pd.Series, periods: tuple[int, ...]) -> pd.Series:
    """True when price > EMA(p1) > EMA(p2) > ... for ascending periods."""
    periods = tuple(sorted(periods))
    emas = [ema(close, p) for p in periods]
    ok = close > emas[0]
    for faster, slower in zip(emas, emas[1:]):
        ok &= faster > slower
    return ok.fillna(False)


def pct_from_high(df: pd.DataFrame, lookback: int) -> pd.Series:
    """Fractional distance of the close below the rolling ``lookback`` high.

    ``min_periods`` is half the window so a stock with, say, 9 months of
    history isn't excluded purely for being young — a deliberate trade-off
    for IPO leaders.
    """
    hi = df["high"].rolling(lookback, min_periods=max(lookback // 2, 1)).max()
    return 1.0 - df["close"] / hi


def swing_points(high: pd.Series, low: pd.Series, order: int = 3) -> pd.DataFrame:
    """Detect swing highs/lows **without look-ahead**.

    A bar ``i`` is a pivot high if its high is the strict maximum of the
    window ``[i-order, i+order]``. That definition peeks ``order`` bars into
    the future, so we report the pivot only at bar ``i + order`` — the first
    moment a live trader could actually know it.

    Returns columns:
      * ``pivot_high`` / ``pivot_low`` — the pivot price, placed on the bar
        where the pivot is *confirmed* (NaN elsewhere).
      * ``pivot_high_bar`` / ``pivot_low_bar`` — integer position of the
        original pivot bar, for plotting and structure checks.
    """
    n = len(high)
    is_ph = pd.Series(_strict_center_extreme(high.to_numpy(float), order, np.max), index=high.index)
    is_pl = pd.Series(_strict_center_extreme(low.to_numpy(float), order, np.min), index=high.index)

    out = pd.DataFrame(index=high.index)
    out["pivot_high"] = high.where(is_ph).shift(order)
    out["pivot_low"] = low.where(is_pl).shift(order)
    idx = pd.Series(np.arange(n), index=high.index, dtype=float)
    out["pivot_high_bar"] = idx.where(is_ph).shift(order)
    out["pivot_low_bar"] = idx.where(is_pl).shift(order)
    return out


# --------------------------------------------------------------------------- #
# Relative strength
# --------------------------------------------------------------------------- #


def excess_return(close: pd.Series, bench_close: pd.Series, lookback: int) -> pd.Series:
    """Stock return minus benchmark return over ``lookback`` bars."""
    bench = bench_close.reindex(close.index).ffill()
    return roc(close, lookback) - roc(bench, lookback)


def weighted_return(close: pd.Series, lookbacks: tuple[int, ...], weights: tuple[float, ...]) -> pd.Series:
    """Weighted multi-horizon return — the raw input to an RS ranking."""
    total = sum(weights)
    score = sum(w * roc(close, lb) for lb, w in zip(lookbacks, weights))
    return score / total


def weighted_excess_return(
    close: pd.Series, bench_close: pd.Series, lookbacks: tuple[int, ...], weights: tuple[float, ...]
) -> pd.Series:
    total = sum(weights)
    return sum(w * excess_return(close, bench_close, lb) for lb, w in zip(lookbacks, weights)) / total


def cross_sectional_rank(scores: pd.DataFrame) -> pd.DataFrame:
    """Percentile rank (0–100) across columns (tickers) on each date."""
    return scores.rank(axis=1, pct=True) * 100.0


# --------------------------------------------------------------------------- #
# Candlestick patterns
# --------------------------------------------------------------------------- #


def bullish_engulfing(df: pd.DataFrame, require_prior_red: bool = True) -> pd.Series:
    """Today's green real body fully engulfs yesterday's real body."""
    o, c = df["open"], df["close"]
    po, pc = o.shift(1), c.shift(1)
    green = c > o
    engulf = (c >= pmax(po, pc)) & (o <= pmin(po, pc)) & ((c - o) > (pc - po).abs())
    sig = green & engulf
    if require_prior_red:
        sig &= pc < po
    return sig.fillna(False)


def hammer(
    df: pd.DataFrame,
    min_lower_wick_body: float = 2.0,
    max_upper_wick_body: float = 0.75,
    close_top_fraction: float = 0.4,
) -> pd.Series:
    """Hammer / pin bar: long lower wick showing rejection of lower prices.

    Colour-agnostic (a red hammer is still a rejection), but the close must
    sit in the top ``close_top_fraction`` of the bar's range.
    """
    o, h, lo, c = df["open"], df["high"], df["low"], df["close"]
    body = (c - o).abs()
    rng = (h - lo).replace(0, np.nan)
    # Floor the body at 10% of range: otherwise a near-doji hammer's tiny body
    # makes the upper-wick limit microscopic and rejects textbook hammers.
    body_ref = np.maximum(body, 0.10 * rng)
    lower = pmin(o, c) - lo
    upper = h - pmax(o, c)
    sig = (
        (lower >= min_lower_wick_body * body_ref)
        & (upper <= max_upper_wick_body * body_ref)
        & ((c - lo) / rng >= 1.0 - close_top_fraction)
    )
    return sig.fillna(False)


def _strict_center_extreme(arr: np.ndarray, order: int, fn) -> np.ndarray:
    """Boolean mask: centre of each (2*order+1) window is its *unique* extreme.

    Ties with neighbours are rejected so flat tops don't produce double pivots.
    """
    win = 2 * order + 1
    out = np.zeros(len(arr), dtype=bool)
    if len(arr) < win:
        return out
    w = sliding_window_view(arr, win)
    ext = fn(w, axis=1)
    unique = (w == ext[:, None]).sum(axis=1) == 1
    out[order : len(arr) - order] = (w[:, order] == ext) & unique
    return out


def pmax(a: pd.Series, b: pd.Series) -> pd.Series:
    return pd.concat([a, b], axis=1).max(axis=1)


def pmin(a: pd.Series, b: pd.Series) -> pd.Series:
    return pd.concat([a, b], axis=1).min(axis=1)


# --------------------------------------------------------------------------- #
# Multi-timeframe
# --------------------------------------------------------------------------- #


def higher_timeframe_trend(df: pd.DataFrame, rule: str, ma_period: int, require_rising: bool = True) -> pd.Series:
    """Higher-timeframe "price above (rising) MA" flag mapped back onto ``df``.

    Look-ahead safety: a weekly bar's value is only valid once its *last*
    constituent bar has closed. We therefore index each HTF bar by the
    timestamp of its final source bar and forward-fill. In a backtest the
    Monday–Thursday bars of a week see the previous completed week; in live
    use the current (partial) week is used — a small, documented asymmetry.
    """
    tmp = df[["close"]].copy()
    tmp["_ts"] = df.index
    htf = tmp.resample(rule).agg({"close": "last", "_ts": "last"}).dropna()
    htf_ma = sma(htf["close"], ma_period)
    ok = htf["close"] > htf_ma
    if require_rising:
        ok &= htf_ma > htf_ma.shift(1)
    ok = ok & htf_ma.notna()
    ok.index = pd.DatetimeIndex(htf["_ts"])
    ok = ok[~ok.index.duplicated(keep="last")]
    # Carry the flag as float through the reindex: reindexing a bool Series
    # introduces NaN (object dtype), and fillna on object relies on pandas'
    # deprecated silent downcasting.
    return ok.astype(float).reindex(df.index, method="ffill").fillna(0.0).astype(bool)
