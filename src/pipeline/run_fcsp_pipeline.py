"""
FCSP pipeline orchestrator.

Fetches OHLCV, funding rates, and ETF flows, merges them into a single
aligned DataFrame, then runs signal generation.

CLI:
    python -m src.pipeline.run_fcsp_pipeline --start 2024-01-01 --end 2026-07-01
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from ..data.ohlcv_fetcher import OHLCVFetcher
from ..data.funding_rate_fetcher import FundingRateFetcher
from ..data.etf_flow_scraper import ETFFlowScraper
from ..strategies.flow_confirmed_pullback import FlowConfirmedPullback


@dataclass
class PipelineResult:
    merged_data: pd.DataFrame
    ohlcv_rows: int
    funding_nan_count: int
    etf_flow_nan_count: int
    signal_df: Optional[pd.DataFrame] = None


def merge_data(
    ohlcv: pd.DataFrame,
    funding: Optional[pd.DataFrame] = None,
    etf_flows: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Left-join OHLCV with funding rates and ETF flows on the UTC date index.
    OHLCV is the spine — funding and ETF rows that don't align are dropped;
    missing days in funding/ETF result in NaN (forward-filled one step to handle
    weekends or reporting delays, then left as NaN if still missing).
    """
    df = ohlcv.copy()

    if funding is not None and not funding.empty:
        # Normalise both indices to UTC midnight before joining
        df.index = df.index.normalize()
        funding.index = funding.index.normalize()
        df = df.join(funding[["funding_rate"]], how="left")
        df["funding_rate"] = df["funding_rate"].ffill(limit=1)

    if etf_flows is not None and not etf_flows.empty:
        df.index = df.index.normalize()
        etf_flows.index = etf_flows.index.normalize()
        df = df.join(etf_flows[["etf_flow"]], how="left")
        # No forward-fill for ETF flows — daily data, NaN means unpublished

    return df


def run_pipeline(
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    exchange: str = "binance",
    symbol: str = "BTC/USDT",
    perp_symbol: str = "BTC/USDT:USDT",
    timeframe: str = "1d",
    skip_funding: bool = False,
    skip_etf: bool = False,
    generate_signals: bool = True,
    strategy=None,
) -> PipelineResult:
    """
    Full fetch → merge → signal pipeline.

    Raises RuntimeError (propagated from fetchers) if any data source fails.
    Never silently falls back to partial data.
    """
    if start is None:
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    if end is None:
        end = datetime.now(timezone.utc)
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    # --- Fetch OHLCV ---
    ohlcv = OHLCVFetcher(exchange_id=exchange, symbol=symbol, timeframe=timeframe).fetch(start, end)
    if ohlcv.empty:
        raise RuntimeError(f"run_pipeline: no OHLCV data returned for {symbol} from {exchange}")

    # --- Fetch funding rates ---
    funding: Optional[pd.DataFrame] = None
    if not skip_funding:
        funding = FundingRateFetcher(exchange_id=exchange, symbol=perp_symbol).fetch(start, end)

    # --- Scrape ETF flows ---
    etf_flows: Optional[pd.DataFrame] = None
    if not skip_etf:
        etf_flows = ETFFlowScraper().fetch(start, end)

    # --- Merge ---
    merged = merge_data(ohlcv, funding, etf_flows)

    funding_nans = int(merged["funding_rate"].isna().sum()) if "funding_rate" in merged.columns else 0
    etf_nans = int(merged["etf_flow"].isna().sum()) if "etf_flow" in merged.columns else 0

    result = PipelineResult(
        merged_data=merged,
        ohlcv_rows=len(ohlcv),
        funding_nan_count=funding_nans,
        etf_flow_nan_count=etf_nans,
    )

    # --- Signal generation ---
    if generate_signals:
        if strategy is None:
            strategy = FlowConfirmedPullback()
        result.signal_df = strategy(merged)

    return result


def _print_data_quality(result: PipelineResult) -> None:
    print("\nData quality:")
    print(f"  OHLCV rows:              {result.ohlcv_rows}")
    print(f"  Funding rate NaN count:  {result.funding_nan_count}")
    print(f"  ETF flow NaN count:      {result.etf_flow_nan_count}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="TradeForge FCSP pipeline: fetch → merge → signals"
    )
    parser.add_argument("--start", default="2024-01-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="End date YYYY-MM-DD (default: today)")
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="1d")
    parser.add_argument("--skip-funding", action="store_true")
    parser.add_argument("--skip-etf", action="store_true")
    parser.add_argument("--output", default=None, help="CSV path to write signals to")
    args = parser.parse_args()

    start = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc) if args.end else None

    print(f"Running FCSP pipeline: {args.symbol} from {start.date()} ...")
    try:
        result = run_pipeline(
            start=start, end=end, exchange=args.exchange,
            symbol=args.symbol, timeframe=args.timeframe,
            skip_funding=args.skip_funding, skip_etf=args.skip_etf,
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    _print_data_quality(result)

    if result.signal_df is not None and args.output:
        result.signal_df.to_csv(args.output)
        print(f"Signals written to {args.output}")


if __name__ == "__main__":
    main()
