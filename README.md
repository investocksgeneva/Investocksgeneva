# InvestocksGeneva

Python tools for tracking stock portfolios and running a BTC swing trading bot — powered by Yahoo Finance and Binance data.

---

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your Binance keys (optional for backtest)
```

---

## BTC Swing Trade Bot

EMA crossover strategy on BTC/USDT with backtesting and paper trading.

### Strategy

| Signal | Condition |
|--------|-----------|
| **BUY** | EMA(9) crosses above EMA(21) — golden cross |
| **SELL** | EMA(9) crosses below EMA(21) — death cross |
| **Stop loss** | 3% below entry |
| **Take profit** | 6% above entry (2:1 RR) |
| **Position size** | 10% of available capital per trade |

### Commands

```bash
# Backtest on 365 days of 4h Binance candles
python -m btc_bot backtest

# Start paper trading (live prices, no real orders)
python -m btc_bot paper
```

### Backtest output example

```
========== BACKTEST RESULTS ==========
Period       : 365 days
Symbol       : BTC/USDT  (4h candles)
EMA          : fast=9  slow=21
Initial cap  : $10,000.00
Final cap    : $13,420.00
Total return : +34.20%
Trades       : 28
Win rate     : 57.1%
Max drawdown : -8.43%
Sharpe ratio : 1.87
======================================
```

### Configuration

Edit `btc_bot/config.py` or set environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `BINANCE_API_KEY` | — | Only needed for paper trade |
| `BINANCE_API_SECRET` | — | Only needed for paper trade |
| `BINANCE_TESTNET` | `true` | Use Binance testnet |
| `ema_fast` | `9` | Fast EMA period |
| `ema_slow` | `21` | Slow EMA period |
| `stop_loss_pct` | `0.03` | 3% stop loss |
| `take_profit_pct` | `0.06` | 6% take profit |
| `position_size_pct` | `0.10` | 10% of capital per trade |
| `timeframe` | `4h` | Candle timeframe |

Paper trade state is saved to `paper_state.json` — the bot resumes where it left off on restart.

---

## Stock Portfolio Tracker

Track any stock with live prices and P&L via Yahoo Finance (including Swiss SIX tickers).

```bash
# Show portfolio with live prices
python portfolio.py show

# Add a position
python portfolio.py add NESN.SW 10 95.50
python portfolio.py add AAPL 5 180.00

# Remove a ticker
python portfolio.py remove NESN.SW
```

### Example output

```
Ticker      Shares      Buy @      Now @          Cost        Value        P&L       %
------------------------------------------------------------------------------------------
NESN.SW      10.00      95.50      98.20        955.00       982.00      +27.00   +2.8%
AAPL          5.00     180.00     195.50        900.00       977.50      +77.50   +8.6%
------------------------------------------------------------------------------------------
TOTAL                                          1855.00      1959.50     +104.50   +5.6%
```

Supports SIX (`.SW`), NYSE/NASDAQ, LSE (`.L`), Euronext Paris (`.PA`), and any Yahoo Finance ticker.

---

> **Disclaimer:** This software is for educational purposes only. Not financial advice. Always test with paper trading before using real funds.
