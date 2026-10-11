"""
Portfolio-level backtest: one account, many tickers, real constraints.

The per-ticker simulator in :mod:`backtest` answers "do the signals have
edge, in R?". This module answers the question a trader actually lives with:
"what does the *account* do when every signal competes for the same cash,
position slots and risk budget?"

Mechanics (per bar of the union calendar, in strict intraday order)
-------------------------------------------------------------------
1. **Open — gap exits.** An open position whose bar opens through its stop
   (or target) exits at the open price — gaps are where real losses exceed 1R.
2. **Open — entries.** Signals from the previous close fill at this open.
   If more signals than capacity, they are ranked by ``signal_priority``.
   Each fill must pass, in order:
     * not already holding the ticker;
     * a free slot (``max_positions``);
     * full-risk size = equity × risk% / (fill − stop), capped by
       ``risk.max_position_pct`` — the same rule as live sizing;
     * portfolio heat (sum of open initial risk) stays ≤ ``max_portfolio_heat_pct``;
     * buying power (``max_gross_exposure`` × equity − current exposure, and
       cash when unlevered).
   Heat/buying-power limits may *shrink* a position; below
   ``min_size_fraction`` of intended size it is skipped instead.
3. **Intrabar.** Stop checked before target (conservative on OHLC data).
4. **Close.** Time stop after ``max_hold_bars``; mark every position to its
   last close; record equity, cash, exposure, heat.

Sizing uses equity at the *previous close* — the latest number a trader
could know at the open — so there is no look-ahead in compounding either.
Cash freed by an exit later in the day is not available at that day's open.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from .config import ScannerConfig
from .models import EntrySignal

if TYPE_CHECKING:  # pragma: no cover
    from .signal_generator import PreparedTicker

_PRIORITY = {
    "rs_value": lambda s: -(s.metrics.get("rs_value") or -math.inf),
    "rr_to_swing_high": lambda s: -(s.rr_to_swing_high if s.rr_to_swing_high is not None else -math.inf),
    "tightest_stop": lambda s: s.stop_atr_multiple,
    "fifo": lambda s: 0.0,
}


@dataclass
class _Position:
    ticker: str
    signal: EntrySignal
    shares: int
    entry: float
    stop: float
    target: float
    entry_time: pd.Timestamp
    entry_equity: float
    bars_held: int = 0

    @property
    def initial_risk(self) -> float:
        return self.shares * (self.entry - self.stop)


@dataclass
class PortfolioResult:
    equity_curve: pd.DataFrame  # equity, cash, exposure, n_positions, heat
    trades: pd.DataFrame
    skipped: pd.DataFrame  # signals not taken, with the binding constraint
    metrics: dict[str, float] = field(default_factory=dict)


class PortfolioBacktester:
    def __init__(self, config: ScannerConfig) -> None:
        self.cfg = config
        self.bt = config.backtest
        self.risk = config.risk
        if self.bt.signal_priority not in _PRIORITY:
            raise ValueError(f"backtest.signal_priority must be one of {sorted(_PRIORITY)}")

    # ------------------------------------------------------------------ #
    def run(
        self,
        prepared: dict[str, "PreparedTicker"],
        signals: dict[str, list[EntrySignal]],
        benchmark: pd.DataFrame | None = None,
        start: pd.Timestamp | None = None,
    ) -> PortfolioResult:
        bt, risk = self.bt, self.risk
        capital0 = bt.initial_capital or risk.account_equity
        slip, comm = bt.slippage_pct, bt.commission_per_share

        calendar = pd.DatetimeIndex(sorted(set().union(*(p.df.index for p in prepared.values()))))
        if start is not None:
            calendar = calendar[calendar >= start]
        if len(calendar) == 0:
            raise ValueError("empty backtest calendar")

        # Per-ticker arrays and calendar → local-bar maps (−1 = no bar that day).
        arr = {t: {k: p.df[k].to_numpy(float) for k in ("open", "high", "low", "close")} for t, p in prepared.items()}
        local = {t: p.df.index.get_indexer(calendar) for t, p in prepared.items()}

        # Schedule each signal for its fill bar.
        open_fills: dict[pd.Timestamp, list[EntrySignal]] = {}
        close_fills: dict[pd.Timestamp, list[EntrySignal]] = {}
        for t, sigs in signals.items():
            idx = prepared[t].df.index
            for s in sigs:
                i = int(idx.searchsorted(pd.Timestamp(s.timestamp)))
                if bt.fill_next_open:
                    if i + 1 < len(idx):
                        open_fills.setdefault(idx[i + 1], []).append(s)
                else:
                    close_fills.setdefault(idx[i], []).append(s)

        cash = capital0
        equity_prev = capital0
        positions: dict[str, _Position] = {}
        last_close: dict[str, float] = {}
        trades: list[dict] = []
        skipped: list[dict] = []
        curve: list[dict] = []

        def close_position(pos: _Position, px: float, when: pd.Timestamp, reason: str) -> None:
            nonlocal cash
            exit_net = px * (1 - slip)
            cash += pos.shares * (exit_net - comm)
            pnl = pos.shares * (exit_net - pos.entry - 2 * comm)
            trades.append({
                "ticker": pos.ticker, "signal_time": pd.Timestamp(pos.signal.timestamp),
                "entry_time": pos.entry_time, "exit_time": when, "shares": pos.shares,
                "entry": pos.entry, "stop": pos.stop, "target": pos.target, "exit": exit_net,
                "exit_reason": reason, "bars_held": pos.bars_held,
                "r_multiple": (exit_net - pos.entry - 2 * comm) / (pos.entry - pos.stop),
                "pnl": pnl, "return_on_equity": pnl / pos.entry_equity, "setup_type": pos.signal.setup_type,
            })
            del positions[pos.ticker]

        def try_enter(s: EntrySignal, px: float, when: pd.Timestamp) -> None:
            nonlocal cash
            t = s.ticker
            fill = px * (1 + slip)

            def skip(reason: str) -> None:
                skipped.append({"time": when, "ticker": t, "signal_time": pd.Timestamp(s.timestamp), "reason": reason})

            if t in positions:
                return skip("already_in_position")
            if len(positions) >= bt.max_positions:
                return skip("max_positions")
            if not s.stop_loss < fill < s.target_price:
                return skip("gapped_through_levels")
            ref = equity_prev if bt.compound else capital0
            rps = fill - s.stop_loss
            lot = risk.lot_size
            # Intended size: the same rule live sizing uses.
            intended = min(ref * risk.risk_per_trade_pct / rps, ref * risk.max_position_pct / fill)
            heat_now = sum(p.initial_risk for p in positions.values())
            heat_room = ref * bt.max_portfolio_heat_pct - heat_now
            exposure = sum(p.shares * last_close.get(p.ticker, p.entry) for p in positions.values())
            bp = ref * bt.max_gross_exposure - exposure
            if bt.max_gross_exposure <= 1.0:
                bp = min(bp, cash)
            limits = {"risk": intended, "heat_cap": heat_room / rps, "buying_power": bp / (fill + comm)}
            binding = min(limits, key=limits.get)
            shares = int(math.floor(max(limits[binding], 0.0) / lot) * lot)
            if shares <= 0 or shares < bt.min_size_fraction * intended:
                return skip(binding if binding != "risk" else "size_rounds_to_zero")
            cash -= shares * (fill + comm)
            positions[t] = _Position(t, s, shares, fill, s.stop_loss, s.target_price, when, ref)

        for k, d in enumerate(calendar):
            live = {t: int(local[t][k]) for t in prepared}
            # 1) gap exits at the open
            for pos in list(positions.values()):
                i = live[pos.ticker]
                if i < 0:
                    continue
                o = arr[pos.ticker]["open"][i]
                if o <= pos.stop:
                    close_position(pos, o, d, "stop")
                elif o >= pos.target:
                    close_position(pos, o, d, "target")
            # 2) entries at the open
            new_today: set[str] = set()
            for s in sorted(open_fills.get(d, []), key=_PRIORITY[bt.signal_priority]):
                i = live[s.ticker]
                if i >= 0:
                    try_enter(s, arr[s.ticker]["open"][i], d)
                    if s.ticker in positions and positions[s.ticker].signal is s:
                        new_today.add(s.ticker)
            # 3) intrabar stop / target (stop first)
            for pos in list(positions.values()):
                i = live[pos.ticker]
                if i < 0:
                    continue
                pos.bars_held += 1
                a = arr[pos.ticker]
                if a["low"][i] <= pos.stop:
                    close_position(pos, pos.stop, d, "stop")
                elif a["high"][i] >= pos.target:
                    close_position(pos, pos.target, d, "target")
            # 4) close: update marks, signal-close fills, time stops
            for t, i in live.items():
                if i >= 0:
                    last_close[t] = arr[t]["close"][i]
            for s in sorted(close_fills.get(d, []), key=_PRIORITY[bt.signal_priority]):
                if live[s.ticker] >= 0:
                    try_enter(s, s.entry_price, d)  # entry_price is the signal close
            for pos in list(positions.values()):
                if pos.bars_held >= bt.max_hold_bars and live[pos.ticker] >= 0:
                    close_position(pos, last_close[pos.ticker], d, "time")

            exposure = sum(p.shares * last_close[p.ticker] for p in positions.values())
            equity = cash + exposure
            curve.append({
                "time": d, "equity": equity, "cash": cash, "exposure": exposure,
                "gross_exposure_pct": exposure / equity if equity > 0 else np.nan,
                "n_positions": len(positions),
                "heat_pct": sum(p.initial_risk for p in positions.values()) / equity if equity > 0 else np.nan,
            })
            equity_prev = equity

        # Positions still open at the end are listed (marked at the last close)
        # for information; they are excluded from trade statistics. The equity
        # curve already includes their mark-to-market value.
        for pos in list(positions.values()):
            close_position(pos, last_close[pos.ticker] / (1 - slip), calendar[-1], "open")
        ec = pd.DataFrame(curve).set_index("time")
        tr = pd.DataFrame(trades)
        sk = pd.DataFrame(skipped)
        bench_close = benchmark["close"] if benchmark is not None else None
        metrics = portfolio_metrics(ec, tr, self._periods_per_year(), bt.risk_free_rate, bench_close)
        metrics["signals_total"] = sum(len(v) for v in signals.values())
        metrics["signals_skipped"] = len(sk)
        return PortfolioResult(ec, tr, sk, metrics)

    def _periods_per_year(self) -> float:
        return 252.0 * max(self.cfg.data.bars_per_day, 1)


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def drawdown(equity: pd.Series) -> pd.Series:
    return equity / equity.cummax() - 1.0


def _max_dd_duration(dd: pd.Series) -> int:
    """Longest run of bars spent below a prior equity peak."""
    longest = run = 0
    for under in (dd < 0).to_numpy():
        run = run + 1 if under else 0
        longest = max(longest, run)
    return longest


def portfolio_metrics(
    curve: pd.DataFrame,
    trades: pd.DataFrame,
    periods_per_year: float,
    risk_free_rate: float = 0.0,
    bench_close: pd.Series | None = None,
) -> dict[str, float]:
    """Account-level statistics.

    CAGR uses calendar time; volatility-based ratios use bar returns
    annualised with ``periods_per_year``. Sharpe is a point estimate — its
    standard error over ~2 years of daily data is roughly ±0.7, so treat
    differences smaller than that as noise.
    """
    eq = curve["equity"]
    ret = eq.pct_change().dropna()
    years = max((eq.index[-1] - eq.index[0]).days / 365.25, 1e-9)
    total = eq.iloc[-1] / eq.iloc[0] - 1.0
    cagr = (1.0 + total) ** (1.0 / years) - 1.0 if total > -1 else -1.0
    rf_bar = risk_free_rate / periods_per_year
    sd = ret.std(ddof=1)
    downside = np.sqrt(np.mean(np.minimum(ret - rf_bar, 0.0) ** 2)) if len(ret) else np.nan
    dd = drawdown(eq)
    mdd = float(dd.min())

    m: dict[str, float] = {
        "start": eq.index[0].strftime("%Y-%m-%d"),
        "end": eq.index[-1].strftime("%Y-%m-%d"),
        "final_equity": float(eq.iloc[-1]),
        "total_return": float(total),
        "cagr": float(cagr),
        "ann_volatility": float(sd * np.sqrt(periods_per_year)) if sd > 0 else 0.0,
        "sharpe": float((ret.mean() - rf_bar) / sd * np.sqrt(periods_per_year)) if sd > 0 else np.nan,
        "sortino": float((ret.mean() - rf_bar) / downside * np.sqrt(periods_per_year)) if downside > 0 else np.nan,
        "max_drawdown": mdd,
        "max_dd_duration_bars": _max_dd_duration(dd),
        "calmar": float(cagr / -mdd) if mdd < 0 else np.nan,
        "time_in_market": float((curve["n_positions"] > 0).mean()),
        "avg_gross_exposure": float(curve["gross_exposure_pct"].mean()),
        "avg_positions": float(curve["n_positions"].mean()),
        "max_positions_held": int(curve["n_positions"].max()),
        "avg_heat": float(curve["heat_pct"].mean()),
        "max_heat": float(curve["heat_pct"].max()),
    }
    closed = trades[trades["exit_reason"] != "open"] if not trades.empty else trades
    if not closed.empty:
        r = closed["r_multiple"]
        gross_win = closed.loc[closed["pnl"] > 0, "pnl"].sum()
        gross_loss = -closed.loc[closed["pnl"] <= 0, "pnl"].sum()
        m.update({
            "trades": int(len(closed)),
            "win_rate": float((r > 0).mean()),
            "avg_r": float(r.mean()),
            "profit_factor": float(gross_win / gross_loss) if gross_loss > 0 else np.inf,
            "avg_bars_held": float(closed["bars_held"].mean()),
        })
    else:
        m["trades"] = 0
    if bench_close is not None:
        b = bench_close.reindex(eq.index, method="ffill").dropna()
        if len(b) > 2:
            b_ret = b.pct_change().dropna()
            aligned = pd.concat([ret, b_ret], axis=1, join="inner").dropna()
            b_total = b.iloc[-1] / b.iloc[0] - 1.0
            var_b = aligned.iloc[:, 1].var()
            m.update({
                "benchmark_total_return": float(b_total),
                "benchmark_cagr": float((1 + b_total) ** (1 / years) - 1),
                "benchmark_max_drawdown": float(drawdown(b).min()),
                "beta": float(aligned.cov().iloc[0, 1] / var_b) if var_b > 0 else np.nan,
                "correlation": float(aligned.corr().iloc[0, 1]) if len(aligned) > 2 else np.nan,
            })
    return m
