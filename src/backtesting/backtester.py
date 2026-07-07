"""
Realistic backtester for TradeForge strategies.

Execution assumptions (documented explicitly, not buried in defaults):
- next_open  : position opens at the NEXT candle's open after signal fires.
               This is the default and is deliberately conservative — it avoids
               look-ahead bias from acting on a candle's close before it closes.
- close      : position opens at the signal candle's close.  More optimistic;
               useful for understanding the theoretical upper bound.

Exit hierarchy (checked in this order each candle):
  1. Stop loss: low <= stop_price  → exit at stop_price (worst-case fill)
  2. Take profit: high >= tp_price → exit at tp_price
  3. Gap-open below stop: open < stop_price → exit at open (gap-down fill)
  4. Signal exit: strategy emits SELL → exit at execution price
  5. Time exit: max_hold_days exceeded → exit at close

Costs: a single round-trip cost fraction applied at the open of each trade
(e.g. costs=0.001 deducts 0.1% of notional from capital at entry).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np
import pandas as pd

from ..strategies.base import SignalType


@dataclass
class TradeRecord:
    entry_time: pd.Timestamp
    entry_price: float
    exit_time: Optional[pd.Timestamp]
    exit_price: Optional[float]
    size: float                   # units of base asset (BTC)
    stop_price: float
    tp_price: float
    pnl_usdt: float
    pnl_pct: float
    exit_reason: str              # stop_loss | take_profit | gap_open | signal_exit | time_exit | end_of_data
    hold_days: float


@dataclass
class BacktestResult:
    trades: list[TradeRecord] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=pd.Series)
    initial_equity: float = 100_000.0
    signal_df: pd.DataFrame = field(default_factory=pd.DataFrame)


def compute_metrics(result: BacktestResult) -> dict:
    """
    Compute performance metrics from a BacktestResult.

    Returns a dict with the keys used throughout the codebase and printed
    in the CLI summary.
    """
    trades = result.trades
    curve = result.equity_curve

    if curve.empty or len(curve) < 2:
        return _zero_metrics(result.initial_equity)

    total_return = (curve.iloc[-1] / result.initial_equity - 1) * 100
    returns = curve.pct_change().dropna()

    # Annualise by calendar days in the backtest
    days = (curve.index[-1] - curve.index[0]).days or 1
    ann_factor = 365 / days
    ann_return = ((curve.iloc[-1] / result.initial_equity) ** ann_factor - 1) * 100

    # Sharpe (annualised, assuming 0 risk-free rate — crypto context)
    daily_std = returns.std()
    sharpe = (returns.mean() / daily_std * np.sqrt(252)) if daily_std > 0 else 0.0

    # Max drawdown
    roll_max = curve.cummax()
    drawdown = (curve - roll_max) / roll_max * 100
    max_drawdown = float(drawdown.min())

    if not trades:
        return {
            "total_trades": 0, "win_rate": float("nan"), "profit_factor": float("nan"),
            "sharpe_ratio": sharpe, "max_drawdown": max_drawdown,
            "avg_trade_duration": float("nan"), "total_return": total_return,
            "ann_return": ann_return, "initial_equity": result.initial_equity,
            "final_equity": float(curve.iloc[-1]),
        }

    wins = [t for t in trades if t.pnl_usdt > 0]
    losses = [t for t in trades if t.pnl_usdt <= 0]
    win_rate = len(wins) / len(trades) * 100
    gross_profit = sum(t.pnl_usdt for t in wins)
    gross_loss = abs(sum(t.pnl_usdt for t in losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")
    avg_duration = np.mean([t.hold_days for t in trades]) if trades else float("nan")

    return {
        "total_trades": len(trades),
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "sharpe_ratio": sharpe,
        "max_drawdown": max_drawdown,
        "avg_trade_duration": avg_duration,
        "total_return": total_return,
        "ann_return": ann_return,
        "initial_equity": result.initial_equity,
        "final_equity": float(curve.iloc[-1]),
    }


def _zero_metrics(initial_equity: float) -> dict:
    return {
        "total_trades": 0, "win_rate": float("nan"), "profit_factor": float("nan"),
        "sharpe_ratio": 0.0, "max_drawdown": 0.0, "avg_trade_duration": float("nan"),
        "total_return": 0.0, "ann_return": 0.0,
        "initial_equity": initial_equity, "final_equity": initial_equity,
    }


def summarize_by_period(result: BacktestResult) -> pd.DataFrame:
    """
    Break down performance by calendar year for stability analysis.

    Returns a DataFrame indexed by year with columns matching compute_metrics.
    """
    curve = result.equity_curve
    if curve.empty:
        return pd.DataFrame()

    rows = []
    for year, group in curve.groupby(curve.index.year):
        year_trades = [
            t for t in result.trades
            if t.entry_time.year == year
        ]
        year_result = BacktestResult(
            trades=year_trades,
            equity_curve=group,
            initial_equity=float(group.iloc[0]),
        )
        metrics = compute_metrics(year_result)
        metrics["period"] = year
        rows.append(metrics)

    return pd.DataFrame(rows).set_index("period")


def run_backtest(
    data: pd.DataFrame,
    strategy,
    risk_pct: float = 0.01,
    initial_equity: float = 100_000.0,
    execution_timing: str = "next_open",
    costs: float = 0.001,
    max_hold_days: int = 60,
    precomputed_signals: Optional[pd.Series] = None,
) -> BacktestResult:
    """
    Simulate a strategy on *data* and return a BacktestResult.

    Parameters
    ----------
    data                : merged OHLCV + macro DataFrame
    strategy            : Strategy instance (used only if precomputed_signals is None)
    risk_pct            : fraction of equity to risk per trade
    initial_equity      : starting capital in USDT
    execution_timing    : "next_open" (default, conservative) or "close"
    costs               : round-trip cost fraction applied at entry
    max_hold_days       : force exit after this many calendar days
    precomputed_signals : optional pre-generated signal Series (for walk-forward masking)
    """
    if precomputed_signals is not None:
        signal_df = data.copy()
        signal_df["signal"] = precomputed_signals.reindex(data.index).fillna(SignalType.HOLD)
        if "atr" not in signal_df.columns:
            # Compute ATR for stop placement
            signal_df = _add_atr(signal_df, period=14)
    else:
        signal_df = strategy(data)
        if "atr" not in signal_df.columns:
            signal_df = _add_atr(signal_df, period=getattr(strategy, "atr_period", 14))

    equity = initial_equity
    position: Optional[dict] = None
    trades: list[TradeRecord] = []
    equity_series: list[float] = []

    rows = list(signal_df.iterrows())
    n = len(rows)

    for i, (ts, row) in enumerate(rows):
        price = float(row["close"])
        sig = int(row.get("signal", SignalType.HOLD))

        # ---- Manage open position ----
        if position is not None:
            o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])
            hold_days = (ts - position["entry_time"]).days

            exit_price = None
            exit_reason = None

            # Gap-open below stop
            if o < position["stop"]:
                exit_price, exit_reason = o, "gap_open"
            # Stop loss (low touched stop)
            elif l <= position["stop"]:
                exit_price, exit_reason = position["stop"], "stop_loss"
            # Take profit
            elif h >= position["tp"]:
                exit_price, exit_reason = position["tp"], "take_profit"
            # Time exit
            elif hold_days >= max_hold_days:
                exit_price, exit_reason = c, "time_exit"
            # Signal exit
            elif sig == SignalType.SELL:
                exit_price = o if execution_timing == "next_open" else c
                exit_reason = "signal_exit"

            if exit_price is not None:
                size = position["size"]
                pnl = (exit_price - position["entry_price"]) * size
                pct = (exit_price / position["entry_price"] - 1) * 100
                equity += size * exit_price
                trades.append(TradeRecord(
                    entry_time=position["entry_time"],
                    entry_price=position["entry_price"],
                    exit_time=ts,
                    exit_price=exit_price,
                    size=size,
                    stop_price=position["stop"],
                    tp_price=position["tp"],
                    pnl_usdt=pnl,
                    pnl_pct=pct,
                    exit_reason=exit_reason,
                    hold_days=float(hold_days),
                ))
                position = None

        # ---- Open new position on BUY signal ----
        if position is None and sig == SignalType.BUY:
            atr = float(row.get("atr", price * 0.02))
            atr_mult = getattr(strategy, "atr_stop_mult", 2.0) if strategy is not None else 2.0
            stop = price - atr_mult * atr
            tp = price + 2 * atr_mult * atr  # default 2:1 RR

            if execution_timing == "next_open" and i + 1 < n:
                fill_price = float(rows[i + 1][1]["open"])
            else:
                fill_price = price

            risk_per_unit = fill_price - stop
            if risk_per_unit > 0:
                risk_capital = equity * risk_pct
                size = risk_capital / risk_per_unit
                cost = fill_price * size * costs
                equity -= fill_price * size + cost
                position = {
                    "entry_time": ts,
                    "entry_price": fill_price,
                    "size": size,
                    "stop": stop,
                    "tp": tp,
                }

        # Mark-to-market equity
        open_value = position["size"] * price if position else 0.0
        equity_series.append(equity + open_value)

    # Force-close any open position at end of data
    if position is not None and rows:
        ts, row = rows[-1]
        close = float(row["close"])
        size = position["size"]
        pnl = (close - position["entry_price"]) * size
        pct = (close / position["entry_price"] - 1) * 100
        hold_days = (ts - position["entry_time"]).days
        trades.append(TradeRecord(
            entry_time=position["entry_time"],
            entry_price=position["entry_price"],
            exit_time=ts,
            exit_price=close,
            size=size,
            stop_price=position["stop"],
            tp_price=position["tp"],
            pnl_usdt=pnl,
            pnl_pct=pct,
            exit_reason="end_of_data",
            hold_days=float(hold_days),
        ))

    equity_curve = pd.Series(equity_series, index=signal_df.index, name="equity")

    return BacktestResult(
        trades=trades,
        equity_curve=equity_curve,
        initial_equity=initial_equity,
        signal_df=signal_df,
    )


def _add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    df = df.copy()
    high_low = df["high"] - df["low"]
    high_pc = (df["high"] - df["close"].shift(1)).abs()
    low_pc = (df["low"] - df["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_pc, low_pc], axis=1).max(axis=1)
    df["atr"] = tr.ewm(span=period, adjust=False).mean()
    return df
