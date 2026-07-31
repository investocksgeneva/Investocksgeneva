# TradeForge — Claude Code Context

## Project purpose

Research tool for a BTC swing-trading strategy called FlowConfirmedSwingPullback (FCSP).
This is a **research artifact only** — no live order placement, no real money deployed.

## Architecture overview

```
src/
  strategies/   Strategy ABC + FlowConfirmedPullback implementation
  core/         Risk management (position sizing, portfolio checks)
  data/         Three fetchers: OHLCV (ccxt), funding rates (ccxt), ETF flows (web scraper)
  pipeline/     Orchestration: run_fcsp_pipeline.py, run_backtest_pipeline.py
  backtesting/  backtester.py, walk_forward_optimizer.py
config.py       Centralised defaults (single source of truth — don't duplicate in argparse)
main.py         Unified CLI: pipeline | backtest | optimize subcommands
backtest.py     Minimal quickstart script
```

## Key architectural decisions and reasoning

### 1. Strategy is pure — no side effects
`FlowConfirmedPullback.generate_signals()` returns a copy of the input DataFrame with added
columns. It never mutates inputs. This makes it safe to call in parallel folds.

### 2. No-lookahead enforced via shift(1)
Every indicator comparison that informs a signal uses `shift(1)` — the strategy sees only
the most recently *closed* candle. First-bar signal is always HOLD (no prior bar to look at).

### 3. ATR-based stops live in the backtester, not the strategy
Strategy outputs a signal; the backtester computes stop/TP prices using ATR. This decouples
signal generation from execution simulation.

### 4. next_open is the default execution timing
Filling at the next candle's open is conservative and avoids "I can only know the close after
it closes" bias. The `close` timing mode exists for upper-bound comparison.

### 5. Backtest costs model
Single round-trip fraction deducted at entry. Simple but honest — realistic enough for a
research artifact where the goal is relative comparison, not precise P&L prediction.

### 6. Walk-forward optimizer: signal masking for fold isolation
The warmup data before each test window feeds indicators (EMA/ATR need history) but any
signal before `test_start` is forced to HOLD. This prevents a trade from crossing fold
boundaries while still letting EMA warm up properly.

### 7. min_trades fallback instead of silent overfitting
If no param combo in a training fold produces >= min_trades trades, we log `used_fallback=True`
and use the theory-driven default params. Selecting a "best" combo from n=1 trade is worse
than no selection. Check `summarize_folds()` for fallback rates before trusting the result.

### 8. ETF flow scraper has strict schema-drift detection
If Farside Investors changes their table layout, we raise `SchemaError` rather than silently
returning junk data. The scraper validates: `Total` column present + first column parseable
as dates.

### 9. config.py is the single source of truth for defaults
Previously each CLI script had its own argparse defaults. Centralised in `TradeForgeConfig`
dataclass. CLI parsers import from there.

## Current state, honestly

- All 10 source modules and all test suites were built and validated.
- **No live data has been fetched yet.** Every fetcher passed its test suite against mocked
  responses. The first real run (real Binance API + Farside scrape) is still ahead.
- Priority 1 in TODO.md is that first live run, not new features.

## Testing discipline

Every module has a companion test file in `tests/`. Network-dependent calls are mocked.
At least one integration test in `test_walk_forward_optimizer.py` runs the real strategy
against the real backtester (no network, synthetic data) to catch interface bugs that
pure mocks would miss.

Run all tests:
```bash
python -m pytest tests/ -v
```
Expected: ~110 passed, 1 skipped.

## CLI reference

```bash
# Backtest (single command: fetch → signals → backtest)
python -m src.pipeline.run_backtest_pipeline \
    --start 2024-01-01 --end 2026-07-01 \
    --risk-pct 0.01 --trades-csv trades.csv --period-summary

# Walk-forward optimization (Python API)
from src.backtesting.walk_forward_optimizer import run_walk_forward_optimization, summarize_folds
result = run_walk_forward_optimization(merged_data, min_trades=3)
print(summarize_folds(result))

# Unified CLI
python main.py backtest --start 2024-01-01 --risk-pct 0.01
python main.py optimize --start 2023-01-01 --train-window-days 180
```
