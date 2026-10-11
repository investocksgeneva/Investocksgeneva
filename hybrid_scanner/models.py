"""
Typed result objects shared across the pipeline.

Two tools for two jobs:
  * ``dataclass`` for internal, high-volume intermediate results (cheap).
  * ``pydantic`` for :class:`EntrySignal`, the public contract that leaves the
    system (CSV, webhooks, a future broker adapter). Validation there catches
    logic bugs — e.g. a stop above entry — before they become orders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


@dataclass
class FilterCheck:
    """Outcome of one rule. ``passed=None`` means the check was skipped."""

    name: str
    passed: bool | None
    value: float | None = None
    threshold: str = ""
    detail: str = ""

    def describe(self) -> str:
        v = "n/a" if self.value is None else f"{self.value:.4g}"
        status = "SKIP" if self.passed is None else ("PASS" if self.passed else "FAIL")
        extra = f" ({self.detail})" if self.detail else ""
        return f"[{status}] {self.name}: {v} vs {self.threshold}{extra}"


@dataclass
class StageResult:
    """Common shape for Stage 1 / Stage 2 / risk results."""

    ticker: str
    stage: str
    passed: bool
    timestamp: Any = None
    checks: list[FilterCheck] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def failures(self) -> list[FilterCheck]:
        return [c for c in self.checks if c.passed is False]

    @property
    def rejection_reasons(self) -> list[str]:
        return [c.describe() for c in self.failures]


@dataclass
class PullbackSetup(StageResult):
    """Stage 2 result with the pullback geometry needed for stops/targets."""

    swing_high: float | None = None
    swing_high_bar: int | None = None
    impulse_low: float | None = None
    impulse_low_bar: int | None = None
    pullback_low: float | None = None
    pullback_low_bar: int | None = None
    ma_value: float | None = None
    triggers_fired: list[str] = field(default_factory=list)


class EntrySignal(BaseModel):
    """A fully specified, risk-sized long entry suggestion."""

    ticker: str
    timestamp: datetime
    timeframe: str
    setup_type: str
    reason: str

    entry_price: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    target_price: float = Field(gt=0)
    risk_per_share: float = Field(gt=0)
    r_multiple_target: float = Field(gt=0)
    rr_to_swing_high: float | None = None

    shares: int = Field(ge=0)
    position_value: float = Field(ge=0)
    dollar_risk: float = Field(ge=0)
    account_risk_pct: float = Field(ge=0)

    atr: float = Field(gt=0)
    stop_atr_multiple: float
    triggers: list[str]
    metrics: dict[str, float | int | str | None] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _sane_prices(self) -> "EntrySignal":
        if not self.stop_loss < self.entry_price < self.target_price:
            raise ValueError(
                f"{self.ticker}: require stop < entry < target, got "
                f"{self.stop_loss:.2f} / {self.entry_price:.2f} / {self.target_price:.2f}"
            )
        return self

    def summary(self) -> str:
        return (
            f"{self.ticker:<6} {self.timestamp:%Y-%m-%d %H:%M}  "
            f"entry {self.entry_price:>9.2f}  stop {self.stop_loss:>9.2f}  "
            f"target {self.target_price:>9.2f}  risk/sh {self.risk_per_share:>7.2f}  "
            f"size {self.shares:>6}  ({self.r_multiple_target:.1f}R)  — {self.setup_type}"
        )


@dataclass
class ScanReport:
    """Everything a single scan produces, for printing, export, or alerting."""

    as_of: Any
    signals: list[EntrySignal]
    momentum_candidates: list[StageResult]
    rejections: list[StageResult]
    #: Valid pullback structure in a momentum name, but no trigger yet —
    #: tomorrow's alert list.
    pending_setups: list[StageResult] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)
