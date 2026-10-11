"""
Stage 2 — Swing / pullback entry detection and confirmation.

Trading logic
-------------
Inside a confirmed leader we wait for a *constructive* pause:

    price
      │            H  ← swing high (end of impulse)
      │          ╱  ╲
      │        ╱     ╲   ╱  ← trigger bar (confirmation)
      │      ╱        ╲_╱
      │    ╱           P  ← pullback low: near rising MA, higher than L
      │  L  ← impulse low (start of the leg)
      └──────────────────────────── time

A good pullback:
  * retraces modestly — 3–12% from H, or 38.2–50% of the L→H leg;
  * drifts into a *rising* short-term MA (10-SMA / 20-EMA / VWAP) without
    closing decisively below it;
  * happens on **lighter volume** than the impulse (no distribution);
  * keeps the higher-low structure (P stays above the prior swing low).

Then we need evidence buyers are back — a *trigger* on the current bar:
bullish engulfing, hammer, a close back above the MA, a break of the
pullback's micro high, or an RSI / Stochastic hook up from oversold.

Without a trigger the setup is reported as *pending* — useful for building
tomorrow's watchlist and placing alerts.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import indicators as ind
from .config import ConfirmationConfig, PullbackConfig
from .models import FilterCheck, PullbackSetup


class PullbackDetector:
    def __init__(self, pullback: PullbackConfig, confirmation: ConfirmationConfig, atr_period: int = 14) -> None:
        self.pb = pullback
        self.cf = confirmation
        self.atr_period = atr_period

    @property
    def ma_label(self) -> str:
        return f"{self.pb.ma_period}{self.pb.ma_type.upper()}" if self.pb.ma_type != "vwap" else "VWAP"

    # ------------------------------------------------------------------ #
    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Pre-compute every causal series Stage 2 needs (once per ticker)."""
        pb, cf = self.pb, self.cf
        out = pd.DataFrame(index=df.index)
        out["pb_ma"] = ind.moving_average(df, pb.ma_type, pb.ma_period, pb.vwap_anchor)
        out["atr"] = ind.atr(df, self.atr_period)
        out["engulfing"] = ind.bullish_engulfing(df, cf.engulfing_require_prior_red)
        out["hammer"] = ind.hammer(df, cf.hammer_min_lower_wick_body, cf.hammer_max_upper_wick_body,
                                   cf.hammer_close_top_fraction)
        out["rsi"] = ind.rsi(df["close"], cf.rsi_period)
        st = ind.stochastic(df, cf.stoch_k, cf.stoch_d, cf.stoch_smooth)
        out["stoch_k"], out["stoch_d"] = st["k"], st["d"]
        piv = ind.swing_points(df["high"], df["low"], pb.swing_order)
        out["pivot_low"], out["pivot_low_bar"] = piv["pivot_low"], piv["pivot_low_bar"]
        out.attrs["ma_label"] = self.ma_label
        return out

    # ------------------------------------------------------------------ #
    def evaluate(self, ticker: str, df: pd.DataFrame, prep: pd.DataFrame, i: int = -1) -> PullbackSetup:
        """Assess the pullback setup and triggers at bar position ``i``."""
        pb, cf = self.pb, self.cf
        n = len(df)
        t = i if i >= 0 else n + i
        res = PullbackSetup(ticker=ticker, stage="pullback", passed=False, timestamp=df.index[t])

        hi = df["high"].to_numpy(float)
        lo = df["low"].to_numpy(float)
        cl = df["close"].to_numpy(float)
        vo = df["volume"].to_numpy(float)
        ma = prep["pb_ma"].to_numpy(float)
        atr = prep["atr"].to_numpy(float)

        lb = pb.impulse_lookback
        if t < lb + pb.ma_slope_lookback or np.isnan(ma[t]) or np.isnan(atr[t]) or atr[t] <= 0:
            res.checks.append(FilterCheck("history", False, float(t), f">= {lb + pb.ma_slope_lookback} bars"))
            return res

        # --- Locate swing high H (most recent max in the lookback window) ---
        win = hi[t - lb : t + 1]
        h = t - lb + (len(win) - 1 - int(np.argmax(win[::-1])))
        H = hi[h]
        age = t - h
        res.checks.append(FilterCheck("pullback_age", pb.min_pullback_bars <= age <= pb.max_pullback_bars,
                                      float(age), f"{pb.min_pullback_bars}-{pb.max_pullback_bars} bars since swing high"))
        res.swing_high, res.swing_high_bar = float(H), int(h)
        res.ma_value = float(ma[t])
        if age < 1:
            return res  # at a new high — no pullback to analyse

        # --- Impulse low L (lowest low in the window *before* H) ---
        s = max(0, h - lb)
        l_idx = s + int(np.argmin(lo[s : h + 1]))
        L = lo[l_idx]
        # --- Pullback low P (lowest low after H, including today) ---
        p_idx = h + 1 + int(np.argmin(lo[h + 1 : t + 1]))
        P = lo[p_idx]
        res.impulse_low, res.impulse_low_bar = float(L), int(l_idx)
        res.pullback_low, res.pullback_low_bar = float(P), int(p_idx)

        # --- Depth ---
        depth = (H - P) / H
        fib = (H - P) / (H - L) if H > L else np.nan
        pct_ok = pb.min_depth_pct <= depth <= pb.max_depth_pct
        fib_ok = bool(pb.fib_min - pb.fib_tolerance <= fib <= pb.fib_max + pb.fib_tolerance) if not np.isnan(fib) else False
        depth_ok = {"percent": pct_ok, "fib": fib_ok, "either": pct_ok or fib_ok, "both": pct_ok and fib_ok}[pb.depth_mode]
        res.checks.append(FilterCheck(
            f"pullback_depth[{pb.depth_mode}]", depth_ok, float(depth),
            f"{pb.min_depth_pct:.0%}-{pb.max_depth_pct:.0%} or fib {pb.fib_min:.3f}-{pb.fib_max:.3f}",
            detail=f"fib={fib:.2f}",
        ))

        # --- Rising MA and proximity ---
        ma_rising = ma[t] > ma[t - pb.ma_slope_lookback]
        res.checks.append(FilterCheck(f"{self.ma_label}_rising", bool(ma_rising),
                                      float(ma[t] / ma[t - pb.ma_slope_lookback] - 1), f"> 0 over {pb.ma_slope_lookback}b"))
        seg = slice(h + 1, t + 1)
        closest = np.nanmin((lo[seg] - ma[seg]) / atr[seg])
        res.checks.append(FilterCheck(f"tagged_{self.ma_label}", bool(closest <= pb.ma_proximity_atr), float(closest),
                                      f"low within {pb.ma_proximity_atr} ATR of MA"))
        below = (cl[t] - ma[t]) / atr[t]
        res.checks.append(FilterCheck("not_broken_down", bool(below >= -pb.max_close_below_ma_atr), float(below),
                                      f"close >= MA - {pb.max_close_below_ma_atr} ATR"))

        # --- Volume dry-up (exclude the trigger bar: expansion there is good) ---
        if pb.volume_check_enabled:
            pb_vol = vo[h + 1 : t].mean() if age >= 2 else vo[t]
            imp_vol = vo[l_idx : h + 1].mean()
            ratio = pb_vol / imp_vol if imp_vol > 0 else np.inf
            res.checks.append(FilterCheck("pullback_volume_dryup", bool(ratio <= pb.max_volume_ratio), float(ratio),
                                          f"<= {pb.max_volume_ratio:.2f}x impulse volume"))

        # --- Higher-low structure ---
        if pb.higher_low_check_enabled:
            prior_low, src = self._prior_swing_low(prep, t, h)
            ref = prior_low if prior_low is not None else L
            res.checks.append(FilterCheck("higher_low_intact", bool(P > ref), float(P),
                                          f"> prior swing low {ref:.2f}", detail=src))

        structure_ok = all(c.passed is not False for c in res.checks)

        # --- Confirmation triggers ---
        fired = [name for name in cf.triggers if self._trigger(name, t, h, df, prep)]
        res.triggers_fired = fired
        missing_req = [r for r in cf.required_triggers if r not in fired]
        trig_ok = len(fired) >= cf.min_triggers and not missing_req
        res.checks.append(FilterCheck("confirmation", trig_ok, float(len(fired)),
                                      f">= {cf.min_triggers} of {list(cf.triggers)}",
                                      detail=f"fired={fired}" + (f" missing_required={missing_req}" if missing_req else "")))

        res.passed = structure_ok and trig_ok
        res.metrics = {
            "depth_pct": float(depth), "fib_retrace": None if np.isnan(fib) else float(fib),
            "pullback_bars": int(age), "dist_to_ma_atr": float(below), "atr": float(atr[t]),
            "structure_ok": structure_ok,
        }
        return res

    # ------------------------------------------------------------------ #
    @staticmethod
    def _prior_swing_low(prep: pd.DataFrame, t: int, h: int) -> tuple[float | None, str]:
        """Most recent swing low that (a) formed before the swing high and
        (b) was already *confirmed* by bar ``t`` — no future knowledge."""
        bars = prep["pivot_low_bar"].to_numpy(float)[: t + 1]
        prices = prep["pivot_low"].to_numpy(float)[: t + 1]
        mask = ~np.isnan(bars) & (bars < h)
        if not mask.any():
            return None, "no confirmed pivot; using impulse low"
        k = np.flatnonzero(mask)[-1]
        return float(prices[k]), f"pivot @bar {int(bars[k])}"

    def _trigger(self, name: str, t: int, h: int, df: pd.DataFrame, prep: pd.DataFrame) -> bool:
        cf = self.cf
        cl, hi, lo = df["close"].iat[t], df["high"].to_numpy(float), df["low"].iat[t]
        ma, ma_prev = prep["pb_ma"].iat[t], prep["pb_ma"].iat[t - 1]
        if name == "bullish_engulfing":
            return bool(prep["engulfing"].iat[t])
        if name == "hammer":
            return bool(prep["hammer"].iat[t])
        if name == "close_above_ma":
            crossed = df["close"].iat[t - 1] <= ma_prev
            wick = cf.ma_reclaim_allow_wick and lo <= ma
            return bool(cl > ma and (crossed or wick))
        if name == "micro_high_break":
            start = max(h + 1, t - cf.micro_high_lookback)
            if start >= t:
                return False
            ref = hi[start:t].max()
            px = cl if cf.micro_high_use_close else hi[t]
            return bool(px > ref)
        if name == "rsi_bounce":
            r = prep["rsi"].to_numpy(float)
            if t - 1 <= h:
                return False
            touched = np.nanmin(r[h + 1 : t]) <= cf.rsi_oversold
            return bool(touched and r[t] > cf.rsi_oversold and r[t] > r[t - 1])
        if name == "stoch_bounce":
            k, d = prep["stoch_k"].to_numpy(float), prep["stoch_d"].to_numpy(float)
            touched = np.nanmin(k[h + 1 : t + 1]) <= cf.stoch_oversold
            return bool(touched and k[t] > d[t] and k[t - 1] <= d[t - 1])
        raise ValueError(f"Unknown trigger {name!r}")
