"""
Minimal quickstart script — demonstrates the full pipeline in ~30 lines.
For the full-featured CLI, use main.py or python -m src.pipeline.run_backtest_pipeline.

Run:
    python backtest.py
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.pipeline.run_fcsp_pipeline import run_pipeline
from src.strategies.flow_confirmed_pullback import FlowConfirmedPullback
from src.backtesting.backtester import run_backtest, compute_metrics, summarize_by_period

# ── Configuration ─────────────────────────────────────────────────────────────
START = datetime(2024, 1, 1, tzinfo=timezone.utc)
END = None                    # None = today
RISK_PCT = 0.01               # 1% of equity risked per trade
INITIAL_EQUITY = 100_000.0    # USDT
EXECUTION_TIMING = "next_open"
COSTS = 0.001                 # 0.1% round-trip
# ─────────────────────────────────────────────────────────────────────────────

strategy = FlowConfirmedPullback(
    ema_fast=9,
    ema_slow=21,
    atr_stop_mult=2.0,
    atr_period=14,
    require_both_confluence_legs=False,  # price action + funding only
)

print(f"Fetching data from {START.date()} ...")
pipeline = run_pipeline(
    start=START,
    end=END,
    generate_signals=False,  # backtest will call strategy
)

print(f"  OHLCV rows: {pipeline.ohlcv_rows}")
print(f"  Funding NaNs: {pipeline.funding_nan_count}")
print(f"  ETF flow NaNs: {pipeline.etf_flow_nan_count}")
print(f"\nRunning backtest ({EXECUTION_TIMING} fills, costs={COSTS:.3f}) ...")

result = run_backtest(
    pipeline.merged_data,
    strategy=strategy,
    risk_pct=RISK_PCT,
    initial_equity=INITIAL_EQUITY,
    execution_timing=EXECUTION_TIMING,
    costs=COSTS,
)

m = compute_metrics(result)
print("\n========== BACKTEST RESULTS ==========")
print(f"Trades       : {m['total_trades']}")
print(f"Win rate     : {m['win_rate']:.1f}%" if m['win_rate'] == m['win_rate'] else "Win rate     : N/A")
print(f"Profit factor: {m['profit_factor']:.2f}" if m['profit_factor'] == m['profit_factor'] else "Profit factor: N/A")
print(f"Sharpe       : {m['sharpe_ratio']:.2f}")
print(f"Max drawdown : {m['max_drawdown']:.2f}%")
print(f"Total return : {m['total_return']:.2f}%")
print(f"Final equity : ${m['final_equity']:,.2f}")
print("======================================")

print("\nPeriod summary:")
print(summarize_by_period(result)[["total_trades", "win_rate", "total_return", "sharpe_ratio"]].to_string())
