"""
Centralised configuration for TradeForge.

Previously each CLI script declared its own argparse defaults independently —
a footgun if risk_pct or any other shared value ever drifts out of sync.
This dataclass is the single source of truth; CLI parsers import from here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class TradeForgeConfig:
    # Data
    exchange: str = "binance"
    symbol: str = "BTC/USDT"
    perp_symbol: str = "BTC/USDT:USDT"
    timeframe: str = "1d"
    start: datetime = field(
        default_factory=lambda: datetime(2024, 1, 1, tzinfo=timezone.utc)
    )
    end: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # Strategy
    ema_fast: int = 9
    ema_slow: int = 21
    atr_period: int = 14
    atr_stop_mult: float = 2.0
    require_both_confluence_legs: bool = False

    # Risk / execution
    risk_pct: float = 0.01
    initial_equity: float = 100_000.0
    execution_timing: str = "next_open"  # "next_open" | "close"
    costs: float = 0.001                 # round-trip fraction

    # Walk-forward optimizer
    train_window_days: int = 180
    test_window_days: int = 60
    objective: str = "sharpe_ratio"
    min_trades: int = 3

    # Output
    trades_csv: str = ""
    output_csv: str = ""
    period_summary: bool = False

    # Data switches
    skip_funding: bool = False
    skip_etf: bool = False


# Module-level singleton for import convenience
CFG = TradeForgeConfig()
