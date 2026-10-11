"""
Minimal event-style backtest of generated signals.

Purpose: sanity-check the *signal logic* (do stops/targets behave, what is
the R-distribution), not to produce publishable performance figures. It is
single-ticker, long-only, one position at a time, with no portfolio-level
capital constraints.

Execution assumptions (all configurable in ``BacktestConfig``):
  * Signal at bar t's close → fill at bar t+1's open (``fill_next_open``).
    If the open gaps below the stop, the trade is skipped (no edge left).
  * Each subsequent bar: if low <= stop → exit at stop (or at open on a gap
    down); elif high >= target → exit at target (or open on a gap up).
    If both are touched in one bar we assume **stop first** — the
    conservative choice since intrabar order is unknown on OHLC data.
  * Time stop after ``max_hold_bars``, exit at close.

Known biases to keep in mind: survivorship (today's watchlist were
yesterday's winners), no borrow/halts, slippage modelled as a flat %.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import BacktestConfig
from .models import EntrySignal


@dataclass
class Trade:
    ticker: str
    signal_time: pd.Timestamp
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry: float
    stop: float
    target: float
    exit: float
    exit_reason: str
    bars_held: int
    r_multiple: float
    setup_type: str


def simulate(df: pd.DataFrame, signals: list[EntrySignal], cfg: BacktestConfig) -> pd.DataFrame:
    """Simulate trades for one ticker. Returns one row per trade."""
    if not signals:
        return pd.DataFrame()
    o, h, lo, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    idx = df.index
    trades: list[Trade] = []
    busy_until = -1
    slip = cfg.slippage_pct

    for s in sorted(signals, key=lambda x: x.timestamp):
        t = int(idx.searchsorted(pd.Timestamp(s.timestamp)))
        # A signal on the exit bar itself is fine: we exited intrabar and can
        # re-enter at the next open (matches the portfolio simulator).
        if t >= len(df) or (cfg.one_position_per_ticker and t < busy_until):
            continue
        e = t + 1 if cfg.fill_next_open else t
        if e >= len(df):
            continue
        entry = (o[e] if cfg.fill_next_open else s.entry_price) * (1 + slip)
        stop, target = s.stop_loss, s.target_price
        if not stop < entry < target:
            continue  # gapped through the stop or target before we got in
        risk = entry - stop  # actual R after the fill
        # With a next-open fill the entry bar itself is live after the open.
        first = e if cfg.fill_next_open else e + 1
        last = min(len(df) - 1, first + cfg.max_hold_bars - 1)
        if first > last:
            continue
        for j in range(first, last + 1):
            if lo[j] <= stop:
                exit_px = stop if j == e else min(o[j], stop)  # gap-down fills at the open
                reason = "stop"
                break
            if h[j] >= target:
                exit_px = target if j == e else max(o[j], target)
                reason = "target"
                break
        else:
            j = last
            exit_px = c[j]
            # Ran out of data before the time stop → still open (excluded from stats).
            reason = "time" if last == first + cfg.max_hold_bars - 1 else "open"
        exit_px *= (1 - slip)
        r = (exit_px - entry - 2 * cfg.commission_per_share) / risk
        trades.append(Trade(s.ticker, pd.Timestamp(s.timestamp), idx[e], idx[j], entry, stop, target,
                            exit_px, reason, j - e, r, s.setup_type))
        busy_until = j
    return pd.DataFrame([t.__dict__ for t in trades])


def summarize(trades: pd.DataFrame) -> dict[str, float]:
    """Core R-based statistics. Expectancy (mean R) is the number that
    matters; win rate alone is meaningless without payoff size."""
    closed = trades[trades["exit_reason"] != "open"] if not trades.empty else trades
    if closed.empty:
        return {"trades": 0}
    r = closed["r_multiple"]
    wins, losses = r[r > 0], r[r <= 0]
    streak = max_streak = 0
    for x in r:
        streak = streak + 1 if x <= 0 else 0
        max_streak = max(max_streak, streak)
    return {
        "trades": int(len(r)),
        "win_rate": float((r > 0).mean()),
        "avg_r": float(r.mean()),
        "median_r": float(r.median()),
        "profit_factor": float(wins.sum() / -losses.sum()) if losses.sum() < 0 else float("inf"),
        "total_r": float(r.sum()),
        "max_consecutive_losses": int(max_streak),
        "avg_bars_held": float(closed["bars_held"].mean()),
        # Rough sampling uncertainty on expectancy — small samples lie.
        "avg_r_stderr": float(r.std(ddof=1) / np.sqrt(len(r))) if len(r) > 1 else float("nan"),
    }
