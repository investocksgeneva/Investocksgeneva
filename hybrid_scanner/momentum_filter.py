"""
Stage 1 — Momentum / leadership filter.

Trading logic
-------------
We only want to buy pullbacks in stocks that institutions are *already*
accumulating. Pullbacks in laggards are just falling knives with better PR.
A leader, for our purposes:

1. **Is in a Stage-2 uptrend** — price above a rising 50/150/200-SMA stack
   (Minervini trend template) and/or an aligned 8/21/50 EMA stack.
2. **Outperforms the market** — positive excess return vs. SPY, or a high
   percentile rank versus the scanned universe.
3. **Trades near its highs** — within X% of the 52-week high; leaders rarely
   sit 40% off their peak.
4. **Has fresh thrust** — up at least Y% at some point in the last N bars.
5. **Is liquid** (and optionally showed a volume spike on the impulse).
6. **Optionally** shows ADX trend strength, rising MACD histogram, ROC > 0.
7. **Is tightening** — volatility contracting, the VCP "coil".
8. **Higher timeframe agrees** — e.g. weekly close above a rising 10-week MA.

Implementation
--------------
:meth:`MomentumFilter.compute` returns a frame of per-bar metrics and pass
flags; :meth:`MomentumFilter.evaluate` turns one row into an explainable
:class:`~hybrid_scanner.models.StageResult` listing every check.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import indicators as ind
from .config import MomentumConfig, MultiTimeframeConfig
from .models import FilterCheck, StageResult


@dataclass(frozen=True)
class _CheckSpec:
    """Maps a pass-flag column to the metric and threshold shown in logs."""

    name: str
    ok_col: str
    value_col: str | None
    threshold: str


class MomentumFilter:
    def __init__(self, config: MomentumConfig, mtf: MultiTimeframeConfig | None = None, timeframe: str = "1d") -> None:
        self.cfg = config
        self.mtf = mtf
        self.timeframe = timeframe
        self._specs: list[_CheckSpec] = []

    # ------------------------------------------------------------------ #
    # Relative-strength raw score (needed before cross-sectional ranking)
    # ------------------------------------------------------------------ #
    def rs_score(self, close: pd.Series, bench_close: pd.Series | None) -> pd.Series:
        """Raw score used for ranking: weighted multi-horizon return.

        Ranking raw returns vs. ranking excess returns is equivalent on a given
        date (the benchmark term is common to all names), so we rank the
        simpler quantity and need no benchmark for rank mode.
        """
        rs = self.cfg.relative_strength
        return ind.weighted_return(close, rs.lookbacks, rs.weights)

    def resolve_rs_mode(self, universe_size: int, has_benchmark: bool) -> str:
        rs = self.cfg.relative_strength
        if rs.mode != "auto":
            return rs.mode
        if universe_size >= rs.min_universe_for_rank:
            return "rank"
        return "benchmark" if has_benchmark else "rank"

    # ------------------------------------------------------------------ #
    def compute(
        self,
        df: pd.DataFrame,
        bench_close: pd.Series | None = None,
        rs_rank: pd.Series | None = None,
        rs_mode: str = "benchmark",
    ) -> pd.DataFrame:
        """Vectorised Stage-1 features for every bar of ``df``."""
        c = self.cfg
        close, vol = df["close"], df["volume"]
        f = pd.DataFrame(index=df.index)
        specs: list[_CheckSpec] = []

        # 1) Trend template ------------------------------------------------
        t = c.trend
        smas = {p: ind.sma(close, p) for p in {t.sma_fast, t.sma_mid, t.sma_slow, *t.rising_smas}}
        sma_ok = (close > smas[t.sma_fast]) & (close > smas[t.sma_mid]) & (close > smas[t.sma_slow])
        if t.require_sma_stack:
            sma_ok &= (smas[t.sma_fast] > smas[t.sma_mid]) & (smas[t.sma_mid] > smas[t.sma_slow])
        for p in t.rising_smas:
            sma_ok &= ind.is_rising(smas[p], t.slope_lookback)
        ema_ok = ind.ema_stack_aligned(close, t.ema_stack)
        trend_ok = {"sma": sma_ok, "ema_stack": ema_ok, "both": sma_ok & ema_ok, "either": sma_ok | ema_ok}[t.mode]
        f["sma_fast"], f["sma_slow"] = smas[t.sma_fast], smas[t.sma_slow]
        f["pct_above_sma_fast"] = close / smas[t.sma_fast] - 1.0
        f["ok_trend"] = trend_ok.fillna(False)
        specs.append(_CheckSpec(f"trend[{t.mode}]", "ok_trend", "pct_above_sma_fast",
                                f"SMA {t.sma_fast}/{t.sma_mid}/{t.sma_slow} rising" if t.mode != "ema_stack"
                                else f"EMA stack {t.ema_stack}"))

        # 2) Relative strength --------------------------------------------
        rs = c.relative_strength
        if rs.enabled:
            if rs_mode == "rank" and rs_rank is not None:
                f["rs_value"] = rs_rank.reindex(df.index)
                f["ok_rs"] = f["rs_value"] >= rs.min_rank
                specs.append(_CheckSpec("rs_rank", "ok_rs", "rs_value", f">= {rs.min_rank:g} pctile"))
            elif bench_close is not None:
                f["rs_value"] = ind.weighted_excess_return(close, bench_close, rs.lookbacks, rs.weights)
                f["ok_rs"] = f["rs_value"] > rs.min_outperformance
                specs.append(_CheckSpec("rs_vs_benchmark", "ok_rs", "rs_value", f"> {rs.min_outperformance:+.1%}"))
            else:
                f["rs_value"] = np.nan
                f["ok_rs"] = np.nan  # skipped — evaluate() reports it as SKIP
                specs.append(_CheckSpec("relative_strength", "ok_rs", None, "no benchmark/universe"))

        # 3) Proximity to 52-week high -------------------------------------
        hp = c.high_proximity
        if hp.enabled:
            f["pct_from_high"] = ind.pct_from_high(df, hp.lookback_bars)
            f["ok_near_high"] = f["pct_from_high"] <= hp.max_distance_pct
            specs.append(_CheckSpec("near_52w_high", "ok_near_high", "pct_from_high", f"<= {hp.max_distance_pct:.0%} below"))

        # 4) Recent strength ----------------------------------------------
        r = c.recent_strength
        if r.enabled:
            if r.use_max_in_window:
                # Best close in the window vs. the lowest close before it —
                # measures the impulse even if a pullback is under way now.
                low_ref = close.rolling(r.lookback_bars).min()
                hi_ref = close.rolling(r.lookback_bars).max()
                f["recent_return"] = hi_ref / low_ref - 1.0
                # Guard: if the window's max came *before* its min, that's a
                # decline, not an impulse.
                argmax = close.rolling(r.lookback_bars).apply(np.argmax, raw=True)
                argmin = close.rolling(r.lookback_bars).apply(np.argmin, raw=True)
                f.loc[argmax < argmin, "recent_return"] = ind.roc(close, r.lookback_bars)
            else:
                f["recent_return"] = ind.roc(close, r.lookback_bars)
            f["ok_recent"] = f["recent_return"] >= r.min_return_pct
            specs.append(_CheckSpec(f"recent_strength_{r.lookback_bars}b", "ok_recent", "recent_return", f">= {r.min_return_pct:.0%}"))

        # 5) Volume / liquidity -------------------------------------------
        v = c.volume
        if v.enabled:
            f["avg_volume"] = vol.rolling(v.avg_window).mean()
            f["avg_dollar_volume"] = (vol * close).rolling(v.avg_window).mean()
            ok = f["avg_volume"] >= v.min_avg_volume
            if v.min_avg_dollar_volume > 0:
                ok &= f["avg_dollar_volume"] >= v.min_avg_dollar_volume
            f["ok_liquidity"] = ok
            specs.append(_CheckSpec("liquidity", "ok_liquidity", "avg_volume",
                                    f">= {v.min_avg_volume:,.0f} sh & ${v.min_avg_dollar_volume:,.0f}"))
            if v.require_impulse_spike:
                # Spike: an up-close bar with volume > multiple × prior average.
                spike = (vol > v.spike_multiple * f["avg_volume"].shift(1)) & (close > close.shift(1))
                f["spike_count"] = spike.rolling(v.spike_lookback).sum()
                f["ok_volume_spike"] = f["spike_count"] >= 1
                specs.append(_CheckSpec("impulse_volume_spike", "ok_volume_spike", "spike_count",
                                        f">= 1 up-bar at {v.spike_multiple}x vol in {v.spike_lookback}b"))

        # 6) Optional oscillators -----------------------------------------
        o = c.oscillators
        if o.adx_enabled:
            f["adx"] = ind.adx(df, o.adx_period)["adx"]
            f["ok_adx"] = f["adx"] > o.min_adx
            specs.append(_CheckSpec("adx", "ok_adx", "adx", f"> {o.min_adx:g}"))
        if o.macd_enabled:
            hist = ind.macd(close, o.macd_fast, o.macd_slow, o.macd_signal)["hist"]
            f["macd_hist_slope"] = hist - hist.shift(o.macd_slope_bars)
            f["ok_macd"] = f["macd_hist_slope"] > 0
            specs.append(_CheckSpec("macd_hist_slope", "ok_macd", "macd_hist_slope", "> 0"))
        if o.roc_enabled:
            f["roc"] = ind.roc(close, o.roc_period)
            f["ok_roc"] = f["roc"] > o.min_roc
            specs.append(_CheckSpec(f"roc_{o.roc_period}", "ok_roc", "roc", f"> {o.min_roc:g}"))

        # 7) Volatility contraction ---------------------------------------
        vc = c.vcp
        if vc.enabled:
            f["atr_ratio"] = ind.atr_contraction_ratio(df, vc.atr_short, vc.atr_long)
            f["range_tightness"] = ind.range_tightness(close, vc.tightness_window)
            ok = f["atr_ratio"] <= vc.max_atr_ratio
            if vc.max_range_pct > 0:
                ok &= f["range_tightness"] <= vc.max_range_pct
            f["ok_vcp"] = ok
            specs.append(_CheckSpec("vcp_tightness", "ok_vcp", "atr_ratio",
                                    f"ATR{vc.atr_short}/ATR{vc.atr_long} <= {vc.max_atr_ratio:g}, range <= {vc.max_range_pct:.0%}"))

        # 8) Higher-timeframe trend ---------------------------------------
        if self.mtf is not None and self.mtf.enabled:
            rule = self.mtf.htf_rule[self.timeframe]
            period = self.mtf.htf_ma_period[self.timeframe]
            f["ok_htf"] = ind.higher_timeframe_trend(df, rule, period, self.mtf.require_htf_ma_rising)
            specs.append(_CheckSpec(f"htf_trend[{rule}]", "ok_htf", None, f"close > rising {period}-bar HTF SMA"))

        # Aggregate: a skipped check (NaN) neither passes nor fails.
        ok_cols = [s.ok_col for s in specs]
        flags = f[ok_cols].astype("float")
        f["momentum_pass"] = (flags.fillna(1.0) == 1.0).all(axis=1)
        self._specs = specs
        f.attrs["sma_label"] = f"{t.sma_fast} SMA"
        return f

    # ------------------------------------------------------------------ #
    @property
    def last_specs(self) -> list[_CheckSpec]:
        """Check definitions produced by the most recent :meth:`compute`."""
        return list(self._specs)

    def evaluate(self, ticker: str, features: pd.DataFrame, i: int = -1,
                 specs: list[_CheckSpec] | None = None) -> StageResult:
        """Explain the Stage-1 decision at bar position ``i``.

        Pass the ``specs`` captured right after ``compute`` when evaluating
        many tickers, so each is explained with its own check definitions.
        """
        specs = specs if specs is not None else self._specs
        if not specs:
            raise RuntimeError("call compute() before evaluate()")
        row = features.iloc[i]
        checks: list[FilterCheck] = []
        for s in specs:
            raw = row.get(s.ok_col)
            passed = None if raw is None or (isinstance(raw, float) and np.isnan(raw)) else bool(raw)
            val = row.get(s.value_col) if s.value_col else None
            val = None if val is None or pd.isna(val) else float(val)
            checks.append(FilterCheck(s.name, passed, val, s.threshold))
        metrics = {k: (None if pd.isna(row.get(k)) else float(row.get(k)))
                   for k in ("rs_value", "pct_from_high", "recent_return", "atr_ratio", "avg_volume", "adx")
                   if k in features.columns}
        return StageResult(ticker=ticker, stage="momentum", passed=bool(row["momentum_pass"]),
                           timestamp=features.index[i], checks=checks, metrics=metrics)
