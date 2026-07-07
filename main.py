"""
TradeForge unified CLI.

Subcommands:
  pipeline   — fetch + merge + generate signals
  backtest   — fetch + merge + signals + backtest  (single command)
  optimize   — fetch + walk-forward parameter optimization

Usage:
  python main.py backtest --start 2024-01-01 --end 2026-07-01 --risk-pct 0.01
  python main.py pipeline --start 2024-01-01 --output signals.csv
  python main.py optimize --start 2023-01-01 --train-window-days 180
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from config import CFG


def _date(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tradeforge",
        description="TradeForge — BTC FCSP swing trade research tool",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # Shared date/exchange args
    def _add_common(p):
        p.add_argument("--start", default=CFG.start.date().isoformat())
        p.add_argument("--end", default=None)
        p.add_argument("--exchange", default=CFG.exchange)
        p.add_argument("--skip-funding", action="store_true", default=CFG.skip_funding)
        p.add_argument("--skip-etf", action="store_true", default=CFG.skip_etf)

    # --- pipeline ---
    p_pipe = sub.add_parser("pipeline", help="Fetch data and generate signals")
    _add_common(p_pipe)
    p_pipe.add_argument("--output", default=CFG.output_csv)

    # --- backtest ---
    p_bt = sub.add_parser("backtest", help="Full fetch → backtest pipeline")
    _add_common(p_bt)
    p_bt.add_argument("--risk-pct", type=float, default=CFG.risk_pct)
    p_bt.add_argument("--initial-equity", type=float, default=CFG.initial_equity)
    p_bt.add_argument("--execution-timing", choices=["next_open", "close"], default=CFG.execution_timing)
    p_bt.add_argument("--costs", type=float, default=CFG.costs)
    p_bt.add_argument("--trades-csv", default=CFG.trades_csv)
    p_bt.add_argument("--period-summary", action="store_true", default=CFG.period_summary)

    # --- optimize ---
    p_opt = sub.add_parser("optimize", help="Walk-forward parameter optimization")
    _add_common(p_opt)
    p_opt.add_argument("--risk-pct", type=float, default=CFG.risk_pct)
    p_opt.add_argument("--initial-equity", type=float, default=CFG.initial_equity)
    p_opt.add_argument("--train-window-days", type=int, default=CFG.train_window_days)
    p_opt.add_argument("--test-window-days", type=int, default=CFG.test_window_days)
    p_opt.add_argument("--objective", default=CFG.objective,
                       choices=["sharpe_ratio", "total_return", "profit_factor"])
    p_opt.add_argument("--min-trades", type=int, default=CFG.min_trades)

    return parser


def cmd_pipeline(args) -> None:
    from src.pipeline.run_fcsp_pipeline import run_pipeline, _print_data_quality
    start = _date(args.start)
    end = _date(args.end) if args.end else None
    print(f"Pipeline: BTC/USDT from {start.date()} ...")
    result = run_pipeline(
        start=start, end=end, exchange=args.exchange,
        skip_funding=args.skip_funding, skip_etf=args.skip_etf,
    )
    _print_data_quality(result)
    if args.output and result.signal_df is not None:
        result.signal_df.to_csv(args.output)
        print(f"Signals written to {args.output}")


def cmd_backtest(args) -> None:
    from src.pipeline.run_backtest_pipeline import (
        run_fetch_to_backtest, _print_data_quality, _print_performance, _write_trades_csv
    )
    start = _date(args.start)
    end = _date(args.end) if args.end else None
    print(f"Backtest: BTC/USDT from {start.date()} ...")
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


def cmd_optimize(args) -> None:
    from src.pipeline.run_fcsp_pipeline import run_pipeline, _print_data_quality
    from src.backtesting.walk_forward_optimizer import (
        run_walk_forward_optimization, summarize_folds, DEFAULT_PARAM_GRID,
    )
    start = _date(args.start)
    end = _date(args.end) if args.end else None
    print(f"Walk-forward optimize: BTC/USDT from {start.date()} ...")
    try:
        pipeline_result = run_pipeline(
            start=start, end=end, exchange=args.exchange,
            skip_funding=args.skip_funding, skip_etf=args.skip_etf,
            generate_signals=False,
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    _print_data_quality(pipeline_result)
    print(f"\nRunning walk-forward optimization ({len(DEFAULT_PARAM_GRID)} param combos)...")
    result = run_walk_forward_optimization(
        pipeline_result.merged_data,
        param_grid=DEFAULT_PARAM_GRID,
        train_window_days=args.train_window_days,
        test_window_days=args.test_window_days,
        objective=args.objective,
        min_trades=args.min_trades,
        risk_pct=args.risk_pct,
        initial_equity=args.initial_equity,
    )
    print("\nCombined OOS metrics:")
    for k, v in result.combined_metrics.items():
        print(f"  {k}: {v}")
    print("\nFold summary:")
    print(summarize_folds(result).to_string())


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    dispatch = {"pipeline": cmd_pipeline, "backtest": cmd_backtest, "optimize": cmd_optimize}
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
