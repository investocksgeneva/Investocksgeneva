# TradeForge TODO

## Priority 1 — First live run (do this before anything else)

- [ ] Run `python main.py backtest --start 2024-01-01 --skip-etf` with real Binance API key
      (skip ETF initially — validate OHLCV + funding path first)
- [ ] Then run with ETF flows enabled; expect schema-drift check to pass
- [ ] Compare live results to backtest output — sanity-check signal dates
- [ ] Document any surprises from the first live fetch in a `NOTES.md`

## Priority 2 — Walk-forward optimizer CLI

- [ ] Build `src/pipeline/run_walk_forward_pipeline.py` mirroring the two existing pipeline
      scripts (same CLI conventions: `--start`, `--end`, `--train-window-days`, `--objective`)
- [ ] Wire into `main.py optimize` (already stubbed, needs the pipeline script to exist)
- [ ] Write 12 tests matching the pattern of `test_run_backtest_pipeline.py`

## Priority 3 — Diagnose fold fallback rate

- [ ] Run `summarize_folds()` on real data; check `used_fallback` and `candidates_qualified`
- [ ] If most folds fall back to defaults: strategy doesn't produce enough trades for this
      optimizer — acceptable conclusion, document it in NOTES.md rather than forcing it
- [ ] If fallback rate is low: trust `combined_metrics` as the headline number

## Priority 4 — Parameter sensitivity sweep

- [ ] Vary `atr_stop_mult` from 1.0 to 3.0 in 0.5 steps; plot Sharpe vs. drawdown
- [ ] Vary `pullback_band` from 0.01 to 0.05; check if wider band improves trade count
- [ ] Check whether `require_both_confluence_legs=True` vs. `False` materially changes results

## Priority 5 — Regime filter robustness

- [ ] Test EMA(200) vs. EMA(100) vs. no regime filter at all
- [ ] Check what fraction of BUY signals are filtered by the regime (how often is BTC
      below its 200 EMA during the test period?)

## Known limitations to document

- Funding rate data: only available on perpetual contracts (not spot). The daily sum is an
  approximation — actual settlement depends on the hour funding is calculated.
- ETF flow data: Farside Investors publishes with a ~1-day delay and sometimes revises.
  The scraper takes the last-available row; no revision tracking.
- Backtest costs (0.1% round-trip) are a rough estimate. Real costs depend on maker/taker
  tier, funding, and slippage — all of which vary with trade size.
- Walk-forward folds use an expanding training window (always from data start).
  A rolling window would be more regime-adaptive but needs more history.
