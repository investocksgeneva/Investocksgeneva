# Hybrid Momentum + Pullback Scanner

A modular scanner and entry-signal generator for a two-stage long strategy:
**find the leaders, then buy their constructive pullbacks.** Every signal comes
with an entry, stop, target, R-multiple and risk-based position size. Every
rejection records which rule failed and by how much.

```
Universe ─► Stage 1: Momentum / leadership ─► Stage 2: Pullback + trigger ─► Risk gate ─► EntrySignal
              trend · RS · 52w-high · thrust      depth · MA tag · vol dry-up      stop ≤ N·ATR    entry/stop/target
              liquidity · VCP · HTF trend         higher low · confirmation        size > 0        size · R · reason
```

## Quick start

```bash
pip install -r hybrid_scanner/requirements.txt

# Offline demo on deterministic synthetic data (no network needed)
python -m hybrid_scanner.main --source synthetic --recent 60 --backtest --plot

# Real data via yfinance, default 20-name watchlist, signals on the latest bar
python -m hybrid_scanner.main

# Hourly chart, custom tickers, 0.5% risk, stricter 52-week-high filter
python -m hybrid_scanner.main --timeframe 1h --tickers NVDA AVGO META \
    --risk 0.005 --set momentum.high_proximity.max_distance_pct=0.15

# Built-in S&P 500 universe (see "Running on the S&P 500")
python -m hybrid_scanner.main --universe sp500 --period 5y --portfolio --plot

# Any constituents CSV (symbol column); export and alert (dry run)
python -m hybrid_scanner.main --watchlist sp500.csv --export --notify discord

# Portfolio-level backtest: shared capital, 5 slots, rank competing signals
python -m hybrid_scanner.main --source synthetic --portfolio --plot --export \
    --set backtest.max_positions=5 --set backtest.signal_priority=tightest_stop

# Inspect every rejection reason
python -m hybrid_scanner.main --show-rejections -v

python -m pytest hybrid_scanner/tests -q
```

### In Python

```python
from hybrid_scanner import ScannerConfig, HybridSignalGenerator
from hybrid_scanner.utils import YFinanceProvider, load_universe

cfg = ScannerConfig.for_timeframe("1d").with_overrides({
    "pullback.ma_type": "sma", "pullback.ma_period": 10,
    "confirmation.min_triggers": 2,
    "risk.account_equity": 50_000, "risk.risk_per_trade_pct": 0.0075,
})
prov = YFinanceProvider()
data, _ = load_universe(prov, ["NVDA", "META", "AVGO"], "1d", "2y", cfg.data.min_bars)
report = HybridSignalGenerator(cfg).scan(data, benchmark=prov.get_history("SPY", "1d", "2y"))
for s in report.signals:
    print(s.summary())
```

## Modules

| File | Responsibility |
|---|---|
| `config.py` | Every parameter, as nested dataclasses. Includes timeframe presets, dotted-path overrides, JSON I/O and validation |
| `indicators.py` | Pure-pandas indicators: MAs, VWAP, ATR, RSI, Stoch, MACD, ADX, RS, VCP, swing pivots, candles, HTF trend |
| `momentum_filter.py` | Stage 1, computed as vectorised per-bar pass flags. Each decision is explained check by check |
| `pullback_entry.py` | Stage 2: pullback geometry (H / L / P), volume dry-up, higher low, six confirmation triggers |
| `position_sizing.py` | Structure/ATR stops, noise floor, max-stop gate, targets, fixed-fractional sizing |
| `signal_generator.py` | Orchestrates the stages. `scan()` (live) and `signal_history()` (research) share one code path |
| `models.py` | `FilterCheck`, `StageResult`, `PullbackSetup` (dataclasses) and `EntrySignal` (validated pydantic model) |
| `backtest.py` | Per-ticker R-based trade simulator for sanity-checking signal mechanics |
| `portfolio.py` | Portfolio backtest: one account, max positions, heat cap, buying power, signal ranking, compounding, equity curve and metrics vs benchmark |
| `notifiers.py` | Console, CSV, Discord and Telegram sinks. Webhooks run in **dry-run** mode by default |
| `plotting.py` | Setup chart for visual verification (candles, MAs, H/L/P, levels, pullback volume) |
| `utils.py` | `DataProvider` protocol (yfinance / CSV / synthetic), OHLCV cleaning, watchlists, logging |
| `main.py` | CLI and `example_parameter_tuning()` |

## Design decisions

1. **No look-ahead, enforced by a test.** All indicators are causal. Swing pivots
   are reported only once they are *confirmed*, `swing_order` bars later. HTF
   bars become usable only after their last constituent bar closes.
   `test_no_lookahead_signals_reproduce_on_truncated_data` re-runs the live
   scanner on data truncated at each historical signal and requires an
   identical signal.
2. **One code path for live and backtest.** Stage 1 is vectorised over all bars,
   and a live scan simply reads the last row. What you backtest is what you trade.
3. **Explainability first.** Each rule yields a `FilterCheck(name, passed, value,
   threshold)`. Rejections are exportable as a tidy CSV, which shows which
   filter is doing the work. That matters when tuning, and it guards against
   overfitting through a single dominant rule.
4. **Pending setups.** A valid pullback structure without a trigger is reported
   separately, so you can set an alert for the next session.
5. **One signal per pullback** (configurable). Without it, a setup that keeps
   confirming fires on consecutive bars, which duplicates alerts and
   double-counts backtest trades.
6. **Percentage-based volatility contraction.** A raw ATR(10)/ATR(50) ratio is
   biased upward in rising stocks, because dollar ATR grows with price. That is
   exactly the wrong bias for a leadership scan, so true range is normalised by
   price.
7. **No TA-library dependency.** `ta` fails to build on Python 3.13, and the
   formulas are short. Owning them makes every number auditable. Wilder
   smoothing matches TradingView / TA-Lib after warm-up.
8. **Bars, not days.** Lookbacks are counted in bars. `for_timeframe("1h")`
   rescales only the calendar-meaning parameters (the 52-week window, per-bar
   volume floors, pullback depth).

## Running on the S&P 500

```bash
# First run downloads ~503 tickers via yfinance (a few minutes) into data/cache/;
# re-runs within 12 h load from disk in seconds. --refresh forces a re-download.
python -m hybrid_scanner.main --universe sp500 --period 5y --portfolio --plot --export
```

* **Use `--period 5y` (or longer) for backtests.** The 200-SMA plus its slope
  window consumes about 10 months of warm-up, so `2y` leaves only around 14
  months of tradeable history.
* **Position cap vs. slots.** `risk.max_position_pct` defaults to 10%, so a
  cash account can hold about 10 positions, matching `backtest.max_positions`.
  At 25%, buying power ran out after about four positions and the slot and
  heat limits never bound. Check `portfolio_skipped.csv` to see which
  constraint binds.
* **Survivorship bias.** `universes/sp500.csv` holds *today's* constituents
  (source: github.com/datasets/s-and-p-500-companies). Back-testing today's
  members over past years flatters results, because the losers that were
  removed are missing. For research-grade numbers, use point-in-time
  membership.
* Runtime for 503 names × 5 years is about 30–60 s once the data is cached.

## Run it daily on your Mac

A notification and an HTML report every weekday evening, with no cloud
services or accounts. To set it up, follow **[mac/README.md](mac/README.md)**.
In short, it is three commands:

```bash
cd ~ && git clone https://github.com/investocksgeneva/Investocksgeneva.git
cd ~/Investocksgeneva && ./hybrid_scanner/mac/install.sh
```

The new CLI options also work on any OS: `--output-dir DIR`, `--report
report.html` (a self-contained HTML report), `--state-file` (stay quiet on
market holidays), and `--notify macos`.

## Discord scan on GitHub Actions (manual)

`.github/workflows/weekly-scan.yml` runs the scan on GitHub's servers on real
Yahoo data and posts to Discord: a header (candidates, pending setups to
watch, data errors) followed by every signal from the last 5 daily bars.
It is **manual-only**. The scheduled daily scan runs on your Mac (see above).
The workflow file explains how to restore the Friday schedule.

1. In Discord, open **Channel settings → Integrations → Webhooks → New
   Webhook → Copy Webhook URL**.
2. In GitHub, go to **Settings → Secrets and variables → Actions → New
   repository secret**, name it `DISCORD_WEBHOOK_URL`, and paste the URL.
3. Run it: **Actions → Weekly hybrid scan → Run workflow**. Tick *dry run*
   to log the payload without posting. You can also give a few tickers for a
   faster run.

Behaviour worth knowing:
* **Data problems are named, not just counted.** Tickers that fail to load
  are listed with ⚠️. Recent listings and spin-offs that lack the 260 bars of
  history are listed separately, without a warning, because skipping them is
  expected. A failed yfinance download is retried once without threads,
  which avoids yfinance's intermittent `database is locked` error.
* **A header is posted even when there are no signals.** A silent channel
  therefore means a broken job, not a quiet week.
* **Failed delivery fails the run.** A missing secret, an HTTP error, or a
  persistent 429 makes the run fail, so GitHub emails you.
* **Charts and CSVs are kept.** Signal charts and CSVs are uploaded as a run
  artifact and kept for 30 days.
* **If you restore the schedule:** schedules only run from the default
  branch, and GitHub pauses them after 60 days without repository activity.

Locally, the same thing is
`python -m hybrid_scanner.main --universe sp500 --alert-window 5 --notify discord`
(this is a dry run unless you add `--live-alerts`).

## Portfolio backtest

The per-ticker simulator answers *"do the signals have edge, in R?"*. The
portfolio backtester answers *"what does the account do when every signal
competes for the same cash, slots and risk budget?"*

Each bar runs in a fixed intraday order: **gap exits at the open → entries at
the open → intrabar stop/target (stop first) → time stops at the close →
mark-to-market.** Sizing uses the *previous close's* equity, and cash freed by
an exit later in the day is never spent at that morning's open, so there is
no look-ahead in compounding.

| Parameter | Default | Meaning |
|---|---|---|
| `backtest.max_positions` | 10 | concurrent positions |
| `backtest.max_portfolio_heat_pct` | 6% | total open initial risk ÷ equity |
| `backtest.max_gross_exposure` | 1.0 | 1.0 = cash account; > 1 allows margin |
| `backtest.signal_priority` | `rs_value` | tie-break when signals exceed capacity: `rs_value`, `rr_to_swing_high`, `tightest_stop`, `fifo` |
| `backtest.compound` | true | size off current equity rather than starting capital |
| `backtest.min_size_fraction` | 0.25 | skip, rather than take a token position, when heat or buying power shrinks a trade below this fraction |

Outputs: `equity_curve.csv` (equity, cash, exposure, positions, heat per bar),
`portfolio_trades.csv`, and `portfolio_skipped.csv`, which records the
**binding constraint** for every signal not taken. Metrics include CAGR,
volatility, Sharpe, Sortino, max drawdown and its duration, Calmar, time in
market, average exposure and heat, and benchmark return / drawdown / beta /
correlation.

Validation: with every limit disabled, the portfolio engine reproduces the
per-ticker simulator's R-multiples trade-for-trade. Final equity also
reconciles exactly with the sum of trade P&L. Both checks are covered by tests.

**Reading the results.** On a 20-name watchlist the strategy is typically flat
most of the time (low time-in-market and exposure), so its CAGR understates
the per-trade edge. Breadth is the lever: run it on a few hundred names. When
comparing configurations, judge them on risk-adjusted metrics and on
drawdown, not raw return.

## Key parameters (defaults)

| Area | Parameter | Default |
|---|---|---|
| Trend | `momentum.trend.mode` | `sma` (50 > 150 > 200, 50 & 200 rising over 20 bars); also `ema_stack`, `both`, `either` |
| RS | `momentum.relative_strength.mode` | `auto`: universe percentile ≥ 70 when ≥ 20 names, else excess return vs SPY > 0 over 20/50 bars |
| Near high | `momentum.high_proximity.max_distance_pct` | 0.25 |
| Thrust | `momentum.recent_strength.min_return_pct` | +5% within 20 bars |
| Liquidity | `momentum.volume.min_avg_volume` / `min_avg_dollar_volume` | 500k sh / $10M |
| VCP | `momentum.vcp.max_atr_ratio` | 1.0 (ATR%10 / ATR%50) |
| HTF | `mtf.enabled` | weekly close > rising 10-week SMA |
| Pullback MA | `pullback.ma_type`, `ma_period` | 20-EMA (also `sma`, `vwap`) |
| Depth | `pullback.depth_mode` | `either`: 3–12% **or** fib 0.382–0.50 |
| Volume | `pullback.max_volume_ratio` | pullback vol ≤ 0.9 × impulse vol |
| Triggers | `confirmation.triggers`, `min_triggers` | engulfing, hammer, MA reclaim, micro-high break; ≥ 1 |
| Stop | `risk.stop_method`, `stop_buffer_atr` | below pullback low − 0.2 ATR; floor 0.5 ATR; reject > 2.5 ATR |
| Target | `risk.target_method`, `target_r_multiple` | 2R (`swing_high`, `max` available) |
| Size | `risk.risk_per_trade_pct`, `max_position_pct` | 1% risk, ≤ 10% of equity per position |

Dump all of them with `python -m hybrid_scanner.main --dump-config params.json`.

## Connecting live data

Implement one method and pass the object wherever a provider is expected:

```python
class PolygonProvider:
    def get_history(self, ticker: str, timeframe: str, period: str) -> pd.DataFrame:
        raw = ...  # call the API
        return normalize_ohlcv(raw, ticker)   # from hybrid_scanner.utils
```

For streaming (IBKR or a TradingView webhook), append each closed bar to the
ticker's frame and call `generator.signal_at(prepared, -1)`. To keep it cheap,
re-run `prepare_universe` once per bar close rather than on every tick.

## Caveats (please read)

* **The synthetic backtest proves plumbing, not edge.** On synthetic data the
  sample is about 30 trades with a standard error of ±0.27R. That is
  statistically indistinguishable from zero.
* **Survivorship bias.** Today's watchlist is made of yesterday's winners.
  Backtest on a point-in-time universe before believing any numbers.
* **Sharpe ratios are noisy.** Over about two years of daily data, the standard
  error of a Sharpe estimate is roughly ±0.7.
* **OHLC ambiguity.** When a bar touches both stop and target, the simulator
  assumes the stop was hit first (conservative).
* **RS rank** is only meaningful across a reasonably broad universe. Below
  `min_universe_for_rank` names, the scanner falls back to beating the benchmark.
* This is research software, not investment advice.
