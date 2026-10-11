"""
Visual verification of a setup — always eyeball a sample of signals before
trusting any scanner.

Layout: price panel (candles, pullback MA, trend SMA, swing points, entry /
stop / target) above a separate volume panel. Separate panels rather than a
twin axis: two y-scales on one plot invite false visual correlations.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:  # pragma: no cover
    from .models import EntrySignal
    from .signal_generator import PreparedTicker

# Reference palette (light mode). Categorical slots in fixed order; status
# colours reserved for stop/target and always paired with a text label.
PALETTE = {
    "surface": "#fcfcfb",
    "ink": "#0b0b0b",
    "ink2": "#52514e",
    "grid": "#e6e5e0",
    "series1": "#2a78d6",   # pullback MA
    "series2": "#eb6834",   # trend SMA
    "good": "#0ca30c",      # target
    "critical": "#d03b3b",  # stop
}


def _human(v: float, _pos: int | None = None) -> str:
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(v) >= div:
            return f"{v / div:.0f}{suf}"
    return f"{v:.0f}"


def plot_setup(
    p: "PreparedTicker",
    signal: "EntrySignal | None" = None,
    bars: int = 120,
    path: str | Path | None = None,
    show: bool = False,
):
    """Plot the last ``bars`` bars up to the signal (or the latest bar).

    Returns the matplotlib ``Figure``; saves to ``path`` when given.
    """
    import matplotlib

    if not show:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    c = PALETTE
    end = len(p.df) if signal is None else int(p.df.index.searchsorted(pd.Timestamp(signal.timestamp))) + 1
    # Leave a little room after the signal to see what happened next.
    tail = min(len(p.df), end + 15)
    sl = slice(max(0, end - bars), tail)
    df, mom, pb = p.df.iloc[sl], p.momentum.iloc[sl], p.pullback.iloc[sl]
    x = np.arange(len(df))

    fig, (ax, axv) = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                                  gridspec_kw={"height_ratios": [3, 1], "hspace": 0.05})
    fig.patch.set_facecolor(c["surface"])
    for a in (ax, axv):
        a.set_facecolor(c["surface"])
        a.grid(True, color=c["grid"], linewidth=0.6)
        a.set_axisbelow(True)
        for side in ("top", "right"):
            a.spines[side].set_visible(False)
        a.spines["left"].set_color(c["ink2"])
        a.spines["bottom"].set_color(c["ink2"])
        a.tick_params(colors=c["ink2"], labelsize=8)

    # Candles: hollow = up, filled = down (direction by shape, not hue).
    up = (df["close"] >= df["open"]).to_numpy()
    ax.vlines(x, df["low"], df["high"], color=c["ink2"], linewidth=0.8)
    body_lo = np.minimum(df["open"], df["close"]).to_numpy()
    body_h = np.maximum(np.abs(df["close"] - df["open"]).to_numpy(), 1e-9)
    ax.bar(x[up], body_h[up], bottom=body_lo[up], width=0.6, color=c["surface"], edgecolor=c["ink2"], linewidth=0.8)
    ax.bar(x[~up], body_h[~up], bottom=body_lo[~up], width=0.6, color=c["ink2"], edgecolor=c["ink2"], linewidth=0.8)

    ma_label = p.pullback.attrs.get("ma_label", "pullback MA")
    ax.plot(x, pb["pb_ma"], color=c["series1"], linewidth=2, label=f"{ma_label} (pullback MA)")
    ax.plot(x, mom["sma_fast"], color=c["series2"], linewidth=2, label=p.momentum.attrs.get("sma_label", "trend SMA"))

    if signal is not None:
        si = end - 1 - sl.start
        m = signal.metrics
        for key, txt, dy in (("impulse_low", "L", -14), ("swing_high", "H", 8), ("pullback_low", "P", -14)):
            ago, val = m.get(f"{key}_bars_ago"), m.get(key)
            if ago is not None and val is not None and 0 <= si - int(ago) < len(df):
                ax.annotate(txt, (si - int(ago), val), xytext=(0, dy), textcoords="offset points",
                            ha="center", fontsize=9, fontweight="bold", color=c["ink"])
        x0, x1 = si, len(df) - 1
        for price, colr, lab, ls in (
            (signal.entry_price, c["ink"], f"Entry {signal.entry_price:.2f}", "--"),
            (signal.stop_loss, c["critical"], f"Stop {signal.stop_loss:.2f}", "-"),
            (signal.target_price, c["good"], f"Target {signal.target_price:.2f} ({signal.r_multiple_target:.1f}R)", "-"),
        ):
            ax.hlines(price, x0, x1, colors=colr, linestyles=ls, linewidth=1.5)
            ax.annotate(lab, (x1, price), xytext=(4, 0), textcoords="offset points", va="center",
                        fontsize=8, color=c["ink"])
        ax.axvline(si, color=c["ink2"], linewidth=0.8, linestyle=":")

    # Volume panel; pullback bars (after H, up to signal) highlighted.
    vol_colors = np.full(len(df), c["grid"], dtype=object)
    if signal is not None and signal.metrics.get("pullback_bars"):
        n_pb = int(signal.metrics["pullback_bars"])
        vol_colors[max(0, si - n_pb + 1): si + 1] = c["series1"]
    axv.bar(x, df["volume"], width=0.7, color=list(vol_colors))
    axv.set_ylabel("Volume", color=c["ink2"], fontsize=8)
    axv.yaxis.set_major_formatter(FuncFormatter(_human))

    step = max(1, len(df) // 8)
    fmt = "%Y-%m-%d" if p.df.index.freqstr in (None, "B", "D") or len(df) < 2 else "%m-%d %H:%M"
    axv.set_xticks(x[::step])
    axv.set_xticklabels([ts.strftime(fmt) for ts in df.index[::step]], rotation=0)

    title = f"{p.ticker} — {signal.setup_type}" if signal is not None else p.ticker
    ax.set_title(title, loc="left", fontsize=11, color=c["ink"])
    ax.legend(loc="upper left", frameon=False, fontsize=8, labelcolor=c["ink"])
    ax.margins(x=0.01)
    fig.subplots_adjust(right=0.86)

    if path is not None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=120, facecolor=fig.get_facecolor())
    if show:
        plt.show()
    else:
        plt.close(fig)
    return fig
