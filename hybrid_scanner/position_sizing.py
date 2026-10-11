"""
Risk-based position sizing, stops and targets.

Philosophy: *risk is decided before size*. We fix the dollar amount we are
willing to lose (equity × risk%), measure the distance to a stop that the
chart — not our wallet — dictates, and let the share count fall out:

    shares = floor( (equity × risk%) / (entry − stop) )

capped so no single position exceeds ``max_position_pct`` of equity. A tight
stop therefore buys more shares, a wide one fewer; every trade risks ~1R.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .config import RiskConfig


@dataclass
class PositionSize:
    shares: int
    risk_per_share: float
    dollar_risk: float
    position_value: float
    account_risk_pct: float
    capped_by: str  # "risk" | "max_position" | "lot_size"


def position_size(
    equity: float,
    risk_pct: float,
    entry: float,
    stop: float,
    max_position_pct: float = 1.0,
    lot_size: int = 1,
) -> PositionSize:
    """Fixed-fractional sizing.

    Raises ``ValueError`` for nonsensical inputs (stop >= entry, non-positive
    equity) rather than returning a silently wrong number.
    """
    if equity <= 0:
        raise ValueError("equity must be positive")
    if not 0 < risk_pct < 1:
        raise ValueError("risk_pct must be a fraction in (0, 1)")
    if entry <= 0 or stop <= 0 or stop >= entry:
        raise ValueError(f"invalid long levels: entry={entry}, stop={stop}")

    rps = entry - stop
    budget = equity * risk_pct
    by_risk = budget / rps
    by_notional = equity * max_position_pct / entry
    raw = min(by_risk, by_notional)
    capped_by = "risk" if by_risk <= by_notional else "max_position"
    shares = int(math.floor(raw / lot_size) * lot_size)
    if shares == 0 and raw > 0:
        capped_by = "lot_size"
    return PositionSize(
        shares=shares,
        risk_per_share=rps,
        dollar_risk=shares * rps,
        position_value=shares * entry,
        account_risk_pct=shares * rps / equity,
        capped_by=capped_by,
    )


@dataclass
class TradePlan:
    entry: float
    stop: float
    target: float
    atr: float
    stop_atr_multiple: float
    r_multiple_target: float
    rr_to_swing_high: float | None
    size: PositionSize
    stop_method_used: str
    notes: list[str]


def build_trade_plan(
    cfg: RiskConfig,
    *,
    signal_close: float,
    signal_high: float,
    pullback_low: float,
    swing_high: float | None,
    atr: float,
    equity: float | None = None,
) -> tuple[TradePlan | None, list[str]]:
    """Derive entry/stop/target/size from a confirmed setup.

    Returns ``(plan, rejection_reasons)``; ``plan`` is ``None`` when risk is
    unacceptable — e.g. the logical stop is more than ``max_stop_atr`` ATRs
    away, which usually means the pullback was too volatile to trade well.
    """
    notes: list[str] = []
    if atr <= 0 or math.isnan(atr):
        return None, ["ATR unavailable"]

    entry = signal_close if cfg.entry_method == "close" else signal_high + cfg.entry_buffer_atr * atr

    structure_stop = pullback_low - cfg.stop_buffer_atr * atr
    atr_stop = entry - cfg.atr_stop_multiple * atr
    stop = {
        "structure": structure_stop,
        "atr": atr_stop,
        "tighter": max(structure_stop, atr_stop),
        "wider": min(structure_stop, atr_stop),
    }[cfg.stop_method]

    # Noise floor: a stop inside normal daily wiggle gets hit randomly.
    if entry - stop < cfg.min_stop_atr * atr:
        stop = entry - cfg.min_stop_atr * atr
        notes.append(f"stop widened to {cfg.min_stop_atr} ATR noise floor")

    rps = entry - stop
    stop_atr = rps / atr
    if stop_atr > cfg.max_stop_atr:
        return None, [f"stop distance {stop_atr:.2f} ATR > max {cfg.max_stop_atr} ATR"]

    r_target = entry + cfg.target_r_multiple * rps
    if cfg.target_method == "r_multiple" or swing_high is None:
        target = r_target
    elif cfg.target_method == "swing_high":
        target = swing_high
    else:  # "max"
        target = max(r_target, swing_high)
    if target <= entry:
        return None, [f"target {target:.2f} not above entry {entry:.2f}"]

    rr_high = (swing_high - entry) / rps if swing_high is not None else None
    if cfg.min_rr_to_swing_high is not None and (rr_high is None or rr_high < cfg.min_rr_to_swing_high):
        return None, [f"R:R to prior high {rr_high if rr_high is None else round(rr_high, 2)} < {cfg.min_rr_to_swing_high}"]

    size = position_size(equity or cfg.account_equity, cfg.risk_per_trade_pct, entry, stop,
                         cfg.max_position_pct, cfg.lot_size)
    if size.shares <= 0:
        return None, [f"position size rounds to 0 shares (risk/share {rps:.2f})"]
    if size.capped_by == "max_position":
        notes.append(f"size capped at {cfg.max_position_pct:.0%} of equity")

    return TradePlan(
        entry=entry, stop=stop, target=target, atr=atr, stop_atr_multiple=stop_atr,
        r_multiple_target=(target - entry) / rps, rr_to_swing_high=rr_high, size=size,
        stop_method_used=cfg.stop_method, notes=notes,
    ), []
