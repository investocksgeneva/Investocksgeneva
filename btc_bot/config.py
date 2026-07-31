"""
Central configuration — override via environment variables or edit defaults here.
Copy .env.example to .env and fill in API keys for live/paper mode.
"""

import os
from dataclasses import dataclass, field


@dataclass
class Config:
    # Binance API (only needed for live paper-trade loop; backtest uses public REST)
    api_key: str = field(default_factory=lambda: os.getenv("BINANCE_API_KEY", ""))
    api_secret: str = field(default_factory=lambda: os.getenv("BINANCE_API_SECRET", ""))
    testnet: bool = field(default_factory=lambda: os.getenv("BINANCE_TESTNET", "true").lower() == "true")

    # Market
    symbol: str = "BTC/USDT"
    timeframe: str = "4h"          # ccxt timeframe string

    # EMA crossover parameters
    ema_fast: int = 9
    ema_slow: int = 21

    # Risk management
    stop_loss_pct: float = 0.03    # 3% below entry
    take_profit_pct: float = 0.06  # 6% above entry  (2:1 RR)
    position_size_pct: float = 0.10  # 10% of capital per trade

    # Backtest
    backtest_days: int = 365       # how many days of history to fetch
    initial_capital: float = 10_000.0  # USDT

    # Paper trade
    poll_interval_seconds: int = 60  # how often to re-check price


CFG = Config()
