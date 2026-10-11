"""
Hybrid signal generator — joins Stage 1, Stage 2 and risk into entry signals.

Pipeline per ticker, per bar::

    data ─► MomentumFilter.compute (vectorised)       ─┐
         └► PullbackDetector.prepare (vectorised)      ├─► PreparedTicker
                                                       ┘
    at bar i:  Stage 1 pass? ─no─► reject("momentum")
                   │yes
               Stage 2 structure + trigger? ─structure only─► pending
                   │yes                    └─no structure──► reject("pullback")
               Risk acceptable & size > 0? ─no─► reject("risk")
                   │yes
               EntrySignal  (validated pydantic model)

The same ``signal_at`` is used by :meth:`scan` (last bar, live) and by
:meth:`signal_history` (every bar, research/backtest), so live and
backtest logic cannot diverge.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .config import ScannerConfig
from .indicators import cross_sectional_rank
from .models import EntrySignal, FilterCheck, PullbackSetup, ScanReport, StageResult
from .momentum_filter import MomentumFilter
from .position_sizing import build_trade_plan
from .pullback_entry import PullbackDetector
from .utils import get_logger, normalize_ohlcv

_TRIGGER_LABELS = {
    "bullish_engulfing": "bullish engulfing",
    "hammer": "hammer",
    "close_above_ma": "close back above MA",
    "micro_high_break": "micro-high break",
    "rsi_bounce": "RSI bounce",
    "stoch_bounce": "stochastic bounce",
}


@dataclass
class PreparedTicker:
    """All pre-computed series for one ticker."""

    ticker: str
    df: pd.DataFrame
    momentum: pd.DataFrame
    pullback: pd.DataFrame
    momentum_specs: list[Any] = field(default_factory=list)


@dataclass
class BarDecision:
    """Full audit trail for a single ticker at a single bar."""

    ticker: str
    timestamp: Any
    signal: EntrySignal | None
    momentum: StageResult
    pullback: PullbackSetup | None = None
    risk: StageResult | None = None

    @property
    def stage_reached(self) -> str:
        if self.signal is not None:
            return "signal"
        if self.risk is not None:
            return "risk"
        if self.pullback is not None:
            return "pending" if self.pullback.metrics.get("structure_ok") else "pullback"
        return "momentum"


class HybridSignalGenerator:
    def __init__(self, config: ScannerConfig | None = None, logger: logging.Logger | None = None) -> None:
        self.cfg = (config or ScannerConfig()).validate()
        self.log = logger or get_logger(level=self.cfg.output.log_level)
        self.momentum = MomentumFilter(self.cfg.momentum, self.cfg.mtf, self.cfg.data.timeframe)
        self.detector = PullbackDetector(self.cfg.pullback, self.cfg.confirmation, self.cfg.risk.atr_period)

    # ------------------------------------------------------------------ #
    # Preparation
    # ------------------------------------------------------------------ #
    def prepare_universe(
        self, data: dict[str, pd.DataFrame], benchmark: pd.DataFrame | None = None
    ) -> dict[str, PreparedTicker]:
        """Compute all features. Cross-sectional RS rank needs the whole
        universe at once, which is why preparation is universe-level."""
        bench_close = normalize_ohlcv(benchmark, "benchmark")["close"] if benchmark is not None else None
        rs_mode = self.momentum.resolve_rs_mode(len(data), bench_close is not None)
        self.log.info("Preparing %d tickers (timeframe=%s, RS mode=%s)", len(data), self.cfg.data.timeframe, rs_mode)

        ranks: pd.DataFrame | None = None
        if rs_mode == "rank" and self.cfg.momentum.relative_strength.enabled:
            scores = pd.DataFrame({t: self.momentum.rs_score(df["close"], bench_close) for t, df in data.items()})
            ranks = cross_sectional_rank(scores)

        prepared: dict[str, PreparedTicker] = {}
        for t, df in data.items():
            try:
                df = normalize_ohlcv(df, t)
                mom = self.momentum.compute(df, bench_close, ranks[t] if ranks is not None else None, rs_mode)
                specs = self.momentum.last_specs
                prepared[t] = PreparedTicker(t, df, mom, self.detector.prepare(df), specs)
            except Exception as exc:  # isolate per-ticker failures
                self.log.warning("prepare: %s failed — %s", t, exc)
        return prepared

    # ------------------------------------------------------------------ #
    # Core decision
    # ------------------------------------------------------------------ #
    def signal_at(self, p: PreparedTicker, i: int = -1, equity: float | None = None,
                  dedupe: bool | None = None) -> BarDecision:
        """Run the full hybrid decision for ``p`` at bar position ``i``.

        ``dedupe`` (default: ``pullback.one_signal_per_pullback``) suppresses
        a signal if an earlier bar of the *same* pullback already signalled.
        """
        dedupe = self.cfg.pullback.one_signal_per_pullback if dedupe is None else dedupe
        t = i if i >= 0 else len(p.df) + i
        ts = p.df.index[t]
        mom = self.momentum.evaluate(p.ticker, p.momentum, t, p.momentum_specs)
        decision = BarDecision(p.ticker, ts, None, mom)
        if not mom.passed:
            return decision

        setup = self.detector.evaluate(p.ticker, p.df, p.pullback, t)
        decision.pullback = setup
        if not setup.passed:
            return decision

        if dedupe:
            # Re-run the (dedupe-free) decision on earlier bars of this pullback.
            for j in range(setup.swing_high_bar + 1, t):
                prev = self.signal_at(p, j, equity, dedupe=False)
                if prev.signal is not None and prev.pullback.swing_high_bar == setup.swing_high_bar:
                    setup.passed = False
                    setup.checks.append(FilterCheck("first_signal_of_pullback", False, float(j - t), "no earlier signal",
                                                    detail=f"already signalled {p.df.index[j]:%Y-%m-%d %H:%M}"))
                    setup.metrics["structure_ok"] = False
                    return decision

        bar = p.df.iloc[t]
        plan, reasons = build_trade_plan(
            self.cfg.risk,
            signal_close=float(bar["close"]), signal_high=float(bar["high"]),
            pullback_low=float(setup.pullback_low), swing_high=setup.swing_high,
            atr=float(p.pullback["atr"].iat[t]), equity=equity,
        )
        if plan is None:
            decision.risk = StageResult(p.ticker, "risk", False, ts,
                                        checks=[FilterCheck("risk", False, None, "acceptable", r) for r in reasons])
            return decision

        decision.signal = EntrySignal(
            ticker=p.ticker,
            timestamp=pd.Timestamp(ts).to_pydatetime(),
            timeframe=self.cfg.data.timeframe,
            setup_type=self._setup_type(setup),
            reason=self._reason(mom, setup, plan.notes),
            entry_price=round(plan.entry, 4),
            stop_loss=round(plan.stop, 4),
            target_price=round(plan.target, 4),
            risk_per_share=round(plan.size.risk_per_share, 4),
            r_multiple_target=round(plan.r_multiple_target, 2),
            rr_to_swing_high=None if plan.rr_to_swing_high is None else round(plan.rr_to_swing_high, 2),
            shares=plan.size.shares,
            position_value=round(plan.size.position_value, 2),
            dollar_risk=round(plan.size.dollar_risk, 2),
            account_risk_pct=round(plan.size.account_risk_pct, 5),
            atr=round(plan.atr, 4),
            stop_atr_multiple=round(plan.stop_atr_multiple, 2),
            triggers=setup.triggers_fired,
            metrics={**{k: _round(v) for k, v in mom.metrics.items()},
                     **{k: _round(v) for k, v in setup.metrics.items() if k != "structure_ok"},
                     "swing_high": _round(setup.swing_high), "pullback_low": _round(setup.pullback_low),
                     "impulse_low": _round(setup.impulse_low),
                     # Bars-ago offsets let plots/brokers locate the structure.
                     "swing_high_bars_ago": t - setup.swing_high_bar,
                     "pullback_low_bars_ago": t - setup.pullback_low_bar,
                     "impulse_low_bars_ago": t - setup.impulse_low_bar},
        )
        return decision

    # ------------------------------------------------------------------ #
    # Public entry points
    # ------------------------------------------------------------------ #
    def scan(
        self,
        data: dict[str, pd.DataFrame],
        benchmark: pd.DataFrame | None = None,
        as_of: str | pd.Timestamp | None = None,
        prepared: dict[str, PreparedTicker] | None = None,
    ) -> ScanReport:
        """Scan the universe on its latest bar (or the last bar <= ``as_of``)."""
        prepared = prepared if prepared is not None else self.prepare_universe(data, benchmark)
        cutoff = pd.Timestamp(as_of) if as_of is not None else None
        signals, candidates, rejections, pending = [], [], [], []
        errors = {t: "preparation failed" for t in data if t not in prepared}

        for t, p in prepared.items():
            i = len(p.df) - 1 if cutoff is None else int(p.df.index.searchsorted(cutoff, side="right")) - 1
            if i < 0:
                errors[t] = f"no bars on or before {cutoff}"
                continue
            d = self.signal_at(p, i)
            self._log_decision(d)
            if d.momentum.passed:
                candidates.append(d.momentum)
            stage = d.stage_reached
            if stage == "signal":
                signals.append(d.signal)
            elif stage == "pending":
                pending.append(d.pullback)
            else:
                rejections.append({"momentum": d.momentum, "pullback": d.pullback, "risk": d.risk}[stage])

        signals.sort(key=lambda s: s.metrics.get("rs_value") or 0, reverse=True)
        as_of_ts = cutoff or max((p.df.index[-1] for p in prepared.values()), default=None)
        self.log.info("Scan %s: %d tickers → %d momentum candidates → %d pending → %d signals",
                      as_of_ts, len(prepared), len(candidates), len(pending), len(signals))
        return ScanReport(as_of_ts, signals, candidates, rejections, pending, errors)

    @property
    def warmup_bars(self) -> int:
        """First bar at which historical signals are considered."""
        return max(self.cfg.data.min_bars // 2, self.cfg.pullback.impulse_lookback + 10)

    def signal_history(self, p: PreparedTicker, start: int | None = None) -> list[EntrySignal]:
        """Every signal the strategy would have generated, bar by bar.

        Stage 1 is vectorised, so we only run the (costlier) Stage 2 logic on
        bars that already passed momentum.
        """
        start = self.warmup_bars if start is None else max(start, 0)
        passed = p.momentum["momentum_pass"].to_numpy()
        out: list[EntrySignal] = []
        for i in range(start, len(p.df)):
            if passed[i]:
                d = self.signal_at(p, i)
                if d.signal is not None:
                    out.append(d.signal)
        return out

    # ------------------------------------------------------------------ #
    # Formatting & logging
    # ------------------------------------------------------------------ #
    def _setup_type(self, setup: PullbackSetup) -> str:
        trig = " + ".join(_TRIGGER_LABELS.get(x, x) for x in setup.triggers_fired)
        return f"Momentum + {self.detector.ma_label} pullback + {trig}"

    def _reason(self, mom: StageResult, setup: PullbackSetup, notes: list[str]) -> str:
        m, s = mom.metrics, setup.metrics
        parts = []
        if m.get("rs_value") is not None:
            parts.append(f"RS {m['rs_value']:.2f}" if abs(m["rs_value"]) < 5 else f"RS rank {m['rs_value']:.0f}")
        if m.get("pct_from_high") is not None:
            parts.append(f"{m['pct_from_high']:.1%} off high")
        parts.append(f"pullback {s['depth_pct']:.1%}" + (f" / fib {s['fib_retrace']:.2f}" if s.get("fib_retrace") else ""))
        parts.append(f"{s['pullback_bars']} bars")
        return "; ".join(parts + notes)

    def _log_decision(self, d: BarDecision) -> None:
        stage = d.stage_reached
        if stage == "signal":
            self.log.info("SIGNAL  %s", d.signal.summary())  # type: ignore[union-attr]
            return
        res = {"momentum": d.momentum, "pullback": d.pullback, "pending": d.pullback, "risk": d.risk}[stage]
        reasons = "; ".join(res.rejection_reasons) if res else ""
        label = "PENDING" if stage == "pending" else f"REJECT[{stage}]"
        self.log.debug("%-16s %s — %s", label, d.ticker, reasons)


def _round(v: Any, nd: int = 4) -> Any:
    return round(v, nd) if isinstance(v, float) else v


def rejections_frame(report: ScanReport) -> pd.DataFrame:
    """Flatten rejections into a tidy frame (one row per failed check)."""
    rows = []
    tagged = [(r, r.stage) for r in report.rejections] + [(r, "pending") for r in report.pending_setups]
    for r, stage in tagged:
        for c in (r.failures or [None]):
            rows.append({
                "ticker": r.ticker, "stage": stage,
                "timestamp": r.timestamp, "check": c.name if c else "", "value": c.value if c else None,
                "threshold": c.threshold if c else "", "detail": c.detail if c else "",
            })
    return pd.DataFrame(rows)


def signals_frame(signals: list[EntrySignal]) -> pd.DataFrame:
    if not signals:
        return pd.DataFrame()
    rows = [s.model_dump(exclude={"metrics"}) | {f"m_{k}": v for k, v in s.metrics.items()} for s in signals]
    df = pd.DataFrame(rows)
    df["triggers"] = df["triggers"].map(lambda x: ",".join(x))
    return df
