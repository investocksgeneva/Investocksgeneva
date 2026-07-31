"""
Glue script: fetch → merge → signal → backtest in a single command.

This module's entire job is calling run_pipeline(), feeding its merged_data
into run_backtest(), and formatting the performance output.  No new logic lives
here — if you want to change strategy behaviour, edit run_fcsp_pipeline.py or
backtester.py, not this file.

Error propagation: if run_pipeline() raises (bad fetch, schema drift, etc.)
this script surfaces that and exits non-zero.  It will not silently continue
with stale or partial data.

CLI:
    python -m src.pipeline.run_backtest_pipeline \\
        --start 2024-01-01 --end 2026-07-01 \\
        --risk-pct 0.01 --trades-csv trades.csv --period-summary
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from ..backtesting.backtester import BacktestResult, compute_metrics, run_backtest, summarize_by_period
from .run_fcsp_pipeline import PipelineResult, _print_data_quality, run_pipeline


def run_fetch_to_backtest(
    start: datetime,
    end: Optional[datetime] = None,
    exchange: str = "binance",
    symbol: str = "BTC/USDT",
    risk_pct: float = 0.01,
    initial_equity: float = 100_000.0,
    execution_timing: str = "next_open",
    costs: float = 0.001,
    skip_funding: bool = False,
    skip_etf: bool = False,
    strategy=None,
) -> tuple[PipelineResult, BacktestResult]:
    """
    Fetch data, generate signals, and run backtest.

    Returns (PipelineResult, BacktestResult) so callers can inspect both
    data quality and performance.

    Raises RuntimeError (from run_pipeline) if any fetch step fails.
    Does not silently fall back to partial data.
    """
    pipeline_result = run_pipeline(
        start=start, end=end, exchange=exchange, symbol=symbol,
        skip_funding=skip_funding, skip_etf=skip_etf,
        generate_signals=False,   # backtest will call strategy internally
        strategy=strategy,
    )

    if strategy is None:
        from ..strategies.flow_confirmed_pullback import FlowConfirmedPullback
        strategy = FlowConfirmedPullback()

    backtest_result = run_backtest(
        pipeline_result.merged_data,
        strategy=strategy,
        risk_pct=risk_pct,
        initial_equity=initial_equity,
        execution_timing=execution_timing,
        costs=costs,
    )

    return pipeline_result, backtest_result


def _print_performance(result: BacktestResult, period_summary: bool = False) -> None:
    m = compute_metrics(result)
    print("\n" + "=" * 70)
    print("TradeForge FCSP Backtest — RESEARCH ARTIFACT ONLY, no orders placed")
    print("=" * 70)
    print("\nPerformance summary:")
    print(f"  Total trades:            {m['total_trades']}")
    win = f"{m['win_rate']:.1f}%" if m['win_rate'] == m['win_rate'] else "N/A"
    pf = f"{m['profit_factor']:.2f}" if m['profit_factor'] == m['profit_factor'] else "N/A"
    dur = f"{m['avg_trade_duration']:.1f} days" if m['avg_trade_duration'] == m['avg_trade_duration'] else "N/A"
    print(f"  Win rate:                {win}")
    print(f"  Profit factor:           {pf}")
    print(f"  Sharpe ratio (ann.):     {m['sharpe_ratio']:.2f}")
    print(f"  Max drawdown:            {m['max_drawdown']:.2f}%")
    print(f"  Avg trade duration:      {dur}")
    print(f"  Total return:            {m['total_return']:.2f}%")
    print(f"  Initial equity:          ${m['initial_equity']:,.2f}")
    print(f"  Final equity:            ${m['final_equity']:,.2f}")

    if period_summary:
        periods = summarize_by_period(result)
        if not periods.empty:
            print("\nPeriod summary (by year):")
            print(periods[["total_trades", "win_rate", "total_return", "max_drawdown", "sharpe_ratio"]].to_string())


def _write_trades_csv(result: BacktestResult, path: str) -> None:
    if not result.trades:
        print("No trades to write.")
        return
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "entry_time", "exit_time", "entry_price", "exit_price",
                "size", "pnl_usdt", "pnl_pct", "exit_reason", "hold_days",
            ],
        )
        writer.writeheader()
        for t in result.trades:
            writer.writerow({
                "entry_time": t.entry_time, "exit_time": t.exit_time,
                "entry_price": t.entry_price, "exit_price": t.exit_price,
                "size": t.size, "pnl_usdt": t.pnl_usdt, "pnl_pct": t.pnl_pct,
                "exit_reason": t.exit_reason, "hold_days": t.hold_days,
            })
    print(f"Trade log written to {path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="TradeForge: fetch → merge → signal → backtest pipeline"
    )
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--risk-pct", type=float, default=0.01)
    parser.add_argument("--initial-equity", type=float, default=100_000.0)
    parser.add_argument("--execution-timing", choices=["next_open", "close"], default="next_open")
    parser.add_argument("--costs", type=float, default=0.001)
    parser.add_argument("--skip-funding", action="store_true")
    parser.add_argument("--skip-etf", action="store_true")
    parser.add_argument("--trades-csv", default=None)
    parser.add_argument("--period-summary", action="store_true")
    args = parser.parse_args()

    start = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc) if args.end else None

    print(f"TradeForge backtest pipeline: BTC/USDT from {start.date()} ...")
    try:
        pipeline_result, backtest_result = run_fetch_to_backtest(
            start=start, end=end, exchange=args.exchange,
            risk_pct=args.risk_pct, initial_equity=args.initial_equity,
            execution_timing=args.execution_timing, costs=args.costs,
            skip_funding=args.skip_funding, skip_etf=args.skip_etf,
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    _print_data_quality(pipeline_result)
    _print_performance(backtest_result, period_summary=args.period_summary)

    if args.trades_csv:
        _write_trades_csv(backtest_result, args.trades_csv)


if __name__ == "__main__":
    main()
