"""Entry point — run backtest or paper trade."""

from __future__ import annotations

import sys


def main() -> None:
    args = sys.argv[1:]
    cmd = args[0] if args else "help"

    if cmd == "backtest":
        from .data import fetch_ohlcv
        from .backtest import run
        from .config import CFG
        print(f"Fetching {CFG.backtest_days} days of {CFG.timeframe} candles for {CFG.symbol}...")
        df = fetch_ohlcv()
        print(f"Got {len(df)} candles. Running backtest...")
        result = run(df)
        result.print_summary()

    elif cmd == "paper":
        from .paper_trader import run_loop
        run_loop()

    else:
        print("""
InvestocksGeneva — BTC Swing Trade Bot

Commands:
  python -m btc_bot backtest    Run backtest on historical data
  python -m btc_bot paper       Start paper trading loop (live prices, no real orders)

Config via environment variables:
  BINANCE_API_KEY       Binance API key  (optional for backtest)
  BINANCE_API_SECRET    Binance API secret
  BINANCE_TESTNET       true/false (default: true)

Edit btc_bot/config.py to change EMA periods, risk %, position size, timeframe.
""")


if __name__ == "__main__":
    main()
