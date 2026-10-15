"""
Follow-up on recent signals: what happened to each one since it fired?

A signal appears in the daily report only on the day its trigger happens.
This module re-checks the last few days' signals against the bars that came
after, so the report can show whether each is still actionable.

Status rules (evaluated bar by bar after the signal bar, daily OHLC):
  * **stopped**  — a later low touched the stop. If the same bar also touched
    the target we assume the stop came first (conservative; intrabar order
    is unknown on daily data).
  * **target**   — a later high reached the target.
  * **extended** — still open, but the last close is more than
    ``extended_r`` risk units above entry: entering now means a wider stop
    or a worse reward-to-risk than planned.
  * **valid**    — still open and near the planned entry.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .models import EntrySignal

STATUS_LABELS = {
    "target": "✓ Target hit",
    "stopped": "✗ Stopped out",
    "extended": "▲ Extended — too far above entry",
    "valid": "● Still valid — near entry",
}


@dataclass
class TrackedSignal:
    signal: EntrySignal
    status: str            # "valid" | "extended" | "target" | "stopped"
    last_close: float
    r_now: float           # (last close − entry) / risk, or the exit R once closed
    bars_since: int
    event_date: pd.Timestamp | None = None  # when the stop/target was hit

    @property
    def label(self) -> str:
        return STATUS_LABELS[self.status]


def track_signal(signal: EntrySignal, df: pd.DataFrame, extended_r: float = 0.5) -> TrackedSignal | None:
    """Status of one signal given the ticker's bars (``None`` if the signal
    bar isn't in ``df``)."""
    ts = pd.Timestamp(signal.timestamp)
    idx = df.index
    t = int(idx.searchsorted(ts))
    if t >= len(idx) or idx[t] != ts:
        return None
    entry, stop, target = signal.entry_price, signal.stop_loss, signal.target_price
    risk = entry - stop
    hi = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float)
    cl = df["close"].to_numpy(float)
    after = range(t + 1, len(df))
    for j in after:
        if lo[j] <= stop:
            return TrackedSignal(signal, "stopped", float(cl[-1]), (stop - entry) / risk, len(df) - 1 - t, idx[j])
        if hi[j] >= target:
            return TrackedSignal(signal, "target", float(cl[-1]), (target - entry) / risk, len(df) - 1 - t, idx[j])
    last = float(cl[-1])
    r_now = (last - entry) / risk if risk > 0 else np.nan
    status = "extended" if r_now > extended_r else "valid"
    return TrackedSignal(signal, status, last, float(r_now), len(df) - 1 - t)


def track_signals(signals: list[EntrySignal], frames: dict[str, pd.DataFrame],
                  extended_r: float = 0.5) -> list[TrackedSignal]:
    """Track many signals; newest first."""
    out = []
    for s in signals:
        df = frames.get(s.ticker)
        if df is None:
            continue
        tracked = track_signal(s, df, extended_r)
        if tracked is not None:
            out.append(tracked)
    return sorted(out, key=lambda x: x.signal.timestamp, reverse=True)
