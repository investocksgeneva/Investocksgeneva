"""
Backtest the EMA crossover strategy on historical Binance candles.
Produces a trade log and performance summary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from .config import CFG
from .indicators import add_signals


@dataclass
class Trade:
    entry_time: pd.Timestamp
    entry_price: float
    size: float              # BTC amount
    stop_loss: float
    take_profit: float
    exit_time: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    pnl_usdt: float = 0.0
    exit_reason: str = ""


@dataclass
class BacktestResult:
    trades: list[Trade] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=pd.Series)
    initial_capital: float = CFG.initial_capital

    @property
    def final_capital(self) -> float:
        return self.equity_curve.iloc[-1] if len(self.equity_curve) else self.initial_capital

    @property
    def total_return_pct(self) -> float:
        return (self.final_capital / self.initial_capital - 1) * 100

    @property
    def num_trades(self) -> int:
        return len(self.trades)

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        wins = sum(1 for t in self.trades if t.pnl_usdt > 0)
        return wins / len(self.trades) * 100

    @property
    def max_drawdown_pct(self) -> float:
        curve = self.equity_curve
        if curve.empty:
            return 0.0
        roll_max = curve.cummax()
        dd = (curve - roll_max) / roll_max * 100
        return float(dd.min())

    @property
    def sharpe(self) -> float:
        if len(self.equity_curve) < 2:
            return 0.0
        returns = self.equity_curve.pct_change().dropna()
        if returns.std() == 0:
            return 0.0
        # annualise by candle count per year
        candles_per_year = (365 * 24) / _timeframe_hours(CFG.timeframe)
        return float(returns.mean() / returns.std() * (candles_per_year ** 0.5))

    def print_summary(self) -> None:
        print("\n========== BACKTEST RESULTS ==========")
        print(f"Period       : {CFG.backtest_days} days")
        print(f"Symbol       : {CFG.symbol}  ({CFG.timeframe} candles)")
        print(f"EMA          : fast={CFG.ema_fast}  slow={CFG.ema_slow}")
        print(f"Initial cap  : ${self.initial_capital:,.2f}")
        print(f"Final cap    : ${self.final_capital:,.2f}")
        print(f"Total return : {self.total_return_pct:+.2f}%")
        print(f"Trades       : {self.num_trades}")
        print(f"Win rate     : {self.win_rate:.1f}%")
        print(f"Max drawdown : {self.max_drawdown_pct:.2f}%")
        print(f"Sharpe ratio : {self.sharpe:.2f}")
        print("======================================\n")

        if self.trades:
            print(f"{'Entry':20} {'Exit':20} {'Entry $':>10} {'Exit $':>10} {'P&L $':>10} {'Reason'}")
            print("-" * 85)
            for t in self.trades[-20:]:  # last 20 trades
                xt = str(t.exit_time)[:19] if t.exit_time else "OPEN"
                xp = f"{t.exit_price:.2f}" if t.exit_price else "-"
                print(f"{str(t.entry_time)[:19]:20} {xt:20} {t.entry_price:>10.2f} {xp:>10} {t.pnl_usdt:>+10.2f} {t.exit_reason}")
            print()


def _timeframe_hours(tf: str) -> float:
    mapping = {"1m": 1/60, "5m": 5/60, "15m": 0.25, "30m": 0.5,
               "1h": 1, "2h": 2, "4h": 4, "6h": 6, "12h": 12, "1d": 24}
    return mapping.get(tf, 4)


def run(df: pd.DataFrame) -> BacktestResult:
    df = add_signals(df)
    capital = CFG.initial_capital
    equity: list[float] = []
    trades: list[Trade] = []
    position: Optional[Trade] = None

    for ts, row in df.iterrows():
        price = float(row["close"])
        signal = int(row["signal"])

        # Check stop/TP on open position
        if position is not None:
            hit_sl = price <= position.stop_loss
            hit_tp = price >= position.take_profit

            if hit_sl or hit_tp:
                exit_price = position.stop_loss if hit_sl else position.take_profit
                pnl = (exit_price - position.entry_price) * position.size
                capital += position.size * exit_price
                position.exit_time = ts
                position.exit_price = exit_price
                position.pnl_usdt = pnl
                position.exit_reason = "stop_loss" if hit_sl else "take_profit"
                trades.append(position)
                position = None

        # New entry on golden cross (only when flat)
        if signal == 1 and position is None:
            usdt_to_spend = capital * CFG.position_size_pct
            btc_size = usdt_to_spend / price
            capital -= usdt_to_spend
            position = Trade(
                entry_time=ts,
                entry_price=price,
                size=btc_size,
                stop_loss=price * (1 - CFG.stop_loss_pct),
                take_profit=price * (1 + CFG.take_profit_pct),
            )

        # Close on death cross
        elif signal == -1 and position is not None:
            pnl = (price - position.entry_price) * position.size
            capital += position.size * price
            position.exit_time = ts
            position.exit_price = price
            position.pnl_usdt = pnl
            position.exit_reason = "signal_exit"
            trades.append(position)
            position = None

        # Mark-to-market equity
        open_value = position.size * price if position else 0.0
        equity.append(capital + open_value)

    result = BacktestResult(
        trades=trades,
        equity_curve=pd.Series(equity, index=df.index),
        initial_capital=CFG.initial_capital,
    )
    return result
