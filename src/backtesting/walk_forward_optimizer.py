"""
Walk-forward optimizer for FlowConfirmedPullback parameters.

Design principles (stated, not buried):
- Folds: train window selects best params in-sample; test window evaluates
  those params out-of-sample on the immediately following period.
  The aggregated OOS result is the number to trust — in-sample results are
  not surfaced in the final output.
- Signal masking: signals before a fold's test window start are forced to HOLD,
  so indicators can warm up without risking a trade crossing fold boundaries.
- Equity chaining: each fold's test starts with the previous fold's ending equity,
  producing a compounding, continuous OOS equity curve.
- min_trades: combos producing fewer than this many in-sample trades are
  disqualified regardless of their score — avoids winning on n=1 luck.
  Falls back to default parameters if no combo qualifies in a fold.
- Grid scope: ema_fast, ema_slow, atr_stop_mult, atr_period.
  ema_fast < ema_slow enforced at grid construction.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Callable, Optional

import pandas as pd

from ..strategies.base import SignalType
from ..strategies.flow_confirmed_pullback import FlowConfirmedPullback
from .backtester import BacktestResult, compute_metrics, run_backtest

# Default grid: 3×3×3×2 = 54 combos after ema_fast < ema_slow filter
DEFAULT_PARAM_GRID: list[dict] = [
    {"ema_fast": f, "ema_slow": s, "atr_stop_mult": m, "atr_period": p}
    for f, s, m, p in itertools.product(
        [5, 9, 12],
        [15, 21, 26],
        [1.5, 2.0, 2.5],
        [10, 14],
    )
    if f < s
]

# Default params used as fallback when no combo clears min_trades
DEFAULT_PARAMS: dict = {"ema_fast": 9, "ema_slow": 21, "atr_stop_mult": 2.0, "atr_period": 14}


@dataclass
class FoldRecord:
    fold_index: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    best_params: dict
    in_sample_score: float
    oos_metrics: dict
    used_fallback: bool
    candidates_qualified: int


@dataclass
class WalkForwardResult:
    folds: list[FoldRecord] = field(default_factory=list)
    combined_equity: pd.Series = field(default_factory=pd.Series)
    combined_metrics: dict = field(default_factory=dict)
    param_grid: list[dict] = field(default_factory=list)


def generate_folds(
    data: pd.DataFrame,
    train_window_days: int,
    test_window_days: int,
) -> list[tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp]]:
    """
    Return non-overlapping (train_start, train_end, test_start, test_end) tuples
    that tile forward through *data*.
    """
    if data.empty:
        return []

    folds = []
    index = data.index
    start = index[0]
    end = index[-1]

    cursor = start + timedelta(days=train_window_days)
    while cursor + timedelta(days=test_window_days) <= end + timedelta(days=1):
        train_start = start  # expanding window from the very beginning
        train_end = cursor - timedelta(days=1)
        test_start = cursor
        test_end = cursor + timedelta(days=test_window_days) - timedelta(days=1)
        folds.append((train_start, train_end, test_start, test_end))
        cursor += timedelta(days=test_window_days)

    return folds


def evaluate_params_on_window(
    data: pd.DataFrame,
    params: dict,
    risk_pct: float = 0.01,
    initial_equity: float = 100_000.0,
    objective: str = "sharpe_ratio",
    min_trades: int = 3,
    costs: float = 0.001,
) -> tuple[float, int]:
    """
    Run a full backtest with *params* on *data* and return (score, trade_count).
    Returns (-inf, 0) if trade_count < min_trades.
    """
    strategy = FlowConfirmedPullback(**params)
    result = run_backtest(
        data, strategy, risk_pct=risk_pct, initial_equity=initial_equity, costs=costs
    )
    n_trades = len(result.trades)
    if n_trades < min_trades:
        return float("-inf"), n_trades

    metrics = compute_metrics(result)
    score = metrics.get(objective, float("-inf"))
    if score != score:  # NaN
        score = float("-inf")
    return score, n_trades


def _mask_signals_before(signal_df: pd.DataFrame, cutoff: pd.Timestamp) -> pd.Series:
    """Return a Signal Series where any signal before *cutoff* is forced to HOLD."""
    signals = signal_df["signal"].copy()
    signals[signals.index < cutoff] = SignalType.HOLD
    return signals


def run_walk_forward_optimization(
    data: pd.DataFrame,
    param_grid: Optional[list[dict]] = None,
    train_window_days: int = 180,
    test_window_days: int = 60,
    objective: str = "sharpe_ratio",
    min_trades: int = 3,
    risk_pct: float = 0.01,
    costs: float = 0.001,
    initial_equity: float = 100_000.0,
) -> WalkForwardResult:
    """
    Run the full walk-forward optimization and return a WalkForwardResult.

    The combined_metrics field reflects the chained, out-of-sample performance
    only — this is the number to trust for strategy evaluation.
    """
    if param_grid is None:
        param_grid = DEFAULT_PARAM_GRID

    folds = generate_folds(data, train_window_days, test_window_days)
    if not folds:
        return WalkForwardResult(param_grid=param_grid)

    fold_records: list[FoldRecord] = []
    oos_equity_pieces: list[pd.Series] = []
    running_equity = initial_equity

    for fold_idx, (tr_start, tr_end, te_start, te_end) in enumerate(folds):
        train_data = data[(data.index >= tr_start) & (data.index <= tr_end)]
        test_data = data[(data.index >= te_start) & (data.index <= te_end)]

        if train_data.empty or test_data.empty:
            continue

        # ------ In-sample: grid search ------
        best_score = float("-inf")
        best_params = DEFAULT_PARAMS.copy()
        used_fallback = True
        candidates_qualified = 0
        best_in_sample_score = float("-inf")

        for params in param_grid:
            score, n = evaluate_params_on_window(
                train_data, params,
                risk_pct=risk_pct, initial_equity=initial_equity,
                objective=objective, min_trades=min_trades, costs=costs,
            )
            if score > float("-inf"):
                candidates_qualified += 1
            if score > best_score:
                best_score = score
                best_params = params
                used_fallback = False
                best_in_sample_score = score

        if used_fallback:
            best_params = DEFAULT_PARAMS.copy()
            best_in_sample_score = float("nan")

        # ------ Out-of-sample: apply best params on test window ------
        # Include warmup data (full dataset up to test end) to feed indicators,
        # but mask signals before test_start to prevent cross-boundary trades.
        warmup_data = data[data.index <= te_end]
        strategy = FlowConfirmedPullback(**best_params)
        full_signal_df = strategy(warmup_data)
        masked_signals = _mask_signals_before(full_signal_df, te_start)

        test_result = run_backtest(
            warmup_data, strategy=strategy,
            risk_pct=risk_pct, initial_equity=running_equity,
            costs=costs,
            precomputed_signals=masked_signals,
        )

        # Trim equity curve to the test window only
        oos_curve = test_result.equity_curve[
            (test_result.equity_curve.index >= te_start) &
            (test_result.equity_curve.index <= te_end)
        ]

        if not oos_curve.empty:
            running_equity = float(oos_curve.iloc[-1])
            oos_equity_pieces.append(oos_curve)

        oos_trades = [
            t for t in test_result.trades
            if t.entry_time >= te_start
        ]
        oos_result = BacktestResult(
            trades=oos_trades,
            equity_curve=oos_curve,
            initial_equity=float(oos_curve.iloc[0]) if not oos_curve.empty else running_equity,
        )
        oos_metrics = compute_metrics(oos_result)

        fold_records.append(FoldRecord(
            fold_index=fold_idx,
            train_start=tr_start,
            train_end=tr_end,
            test_start=te_start,
            test_end=te_end,
            best_params=best_params,
            in_sample_score=best_in_sample_score,
            oos_metrics=oos_metrics,
            used_fallback=used_fallback,
            candidates_qualified=candidates_qualified,
        ))

    # ------ Aggregate combined OOS performance ------
    if oos_equity_pieces:
        combined_equity = pd.concat(oos_equity_pieces).sort_index()
        combined_equity = combined_equity[~combined_equity.index.duplicated(keep="last")]
    else:
        combined_equity = pd.Series(dtype=float)

    all_oos_trades = [t for fold in fold_records for t in []]  # trades stored in fold_records
    combined_result = BacktestResult(
        trades=[],
        equity_curve=combined_equity,
        initial_equity=initial_equity,
    )
    combined_metrics = compute_metrics(combined_result)

    return WalkForwardResult(
        folds=fold_records,
        combined_equity=combined_equity,
        combined_metrics=combined_metrics,
        param_grid=param_grid,
    )


def summarize_folds(result: WalkForwardResult) -> pd.DataFrame:
    """Return a per-fold summary DataFrame for inspection."""
    rows = []
    for f in result.folds:
        row = {
            "fold": f.fold_index,
            "train_start": f.train_start.date(),
            "train_end": f.train_end.date(),
            "test_start": f.test_start.date(),
            "test_end": f.test_end.date(),
            "best_params": str(f.best_params),
            "in_sample_score": f.in_sample_score,
            "candidates_qualified": f.candidates_qualified,
            "used_fallback": f.used_fallback,
            **{f"oos_{k}": v for k, v in f.oos_metrics.items()},
        }
        rows.append(row)
    return pd.DataFrame(rows).set_index("fold") if rows else pd.DataFrame()
