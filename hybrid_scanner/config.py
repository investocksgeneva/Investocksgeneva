"""
Central configuration for the Hybrid Momentum + Pullback scanner.

Design notes
------------
* Every threshold used anywhere in the pipeline lives here. Modules receive a
  config object and never invent numbers of their own.
* Configuration is a tree of plain dataclasses: cheap to construct, easy to
  diff, trivially serialisable to/from JSON, and IDE-friendly.
* All lookbacks are expressed in **bars**, not calendar days. That makes the
  same logic valid on daily and hourly data; :meth:`ScannerConfig.for_timeframe`
  rescales the handful of parameters whose *meaning* is calendar-based
  (e.g. "52-week high", "average daily volume").
* Overrides use dotted paths so you can tune from a CLI, a notebook, or an
  optimiser without touching code::

      cfg = ScannerConfig().with_overrides({
          "momentum.high_proximity.max_distance_pct": 0.15,
          "pullback.ma_type": "sma",
          "risk.risk_per_trade_pct": 0.005,
      })
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields, is_dataclass, replace
from pathlib import Path
from typing import Any, Literal, Mapping

Timeframe = Literal["1d", "1h"]
MAType = Literal["sma", "ema", "vwap"]
TrendMode = Literal["sma", "ema_stack", "both", "either"]
RSMode = Literal["benchmark", "rank", "auto"]
DepthMode = Literal["percent", "fib", "either", "both"]
StopMethod = Literal["structure", "atr", "tighter", "wider"]
EntryMethod = Literal["close", "breakout"]
TargetMethod = Literal["r_multiple", "swing_high", "max"]

#: Every confirmation trigger the pullback module knows how to evaluate.
ALL_TRIGGERS: tuple[str, ...] = (
    "bullish_engulfing",
    "hammer",
    "close_above_ma",
    "micro_high_break",
    "rsi_bounce",
    "stoch_bounce",
)


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
@dataclass
class DataConfig:
    """Where data comes from and how much of it we need."""

    timeframe: Timeframe = "1d"
    source: Literal["yfinance", "csv", "synthetic"] = "yfinance"
    #: yfinance-style period string. Hourly data on Yahoo is capped at ~730d.
    period: str = "2y"
    csv_dir: str = "data"
    benchmark: str = "SPY"
    #: Minimum bars required before a ticker is evaluated at all. Needs to
    #: cover the longest lookback (200-SMA + slope window) to avoid NaN logic.
    min_bars: int = 260
    #: Trading-session bars per day. Used only to rescale calendar-based
    #: parameters for intraday timeframes (US RTH on Yahoo 1h = 7 bars).
    bars_per_day: int = 1
    #: Local cache for downloaded history ("" disables). Re-runs on a
    #: 500-name universe load from disk instead of re-downloading.
    cache_dir: str = "data/cache"
    cache_max_age_hours: float = 12.0
    refresh_cache: bool = False


# --------------------------------------------------------------------------- #
# Stage 1 — Momentum / leadership
# --------------------------------------------------------------------------- #
@dataclass
class TrendConfig:
    """Trend-template rules (Minervini-style SMA stack and/or EMA stack)."""

    #: "sma" = price above rising 50 & 150/200; "ema_stack" = 8 > 21 > 50 EMA;
    #: "both" requires both; "either" accepts whichever passes.
    mode: TrendMode = "sma"
    sma_fast: int = 50
    sma_mid: int = 150
    sma_slow: int = 200
    #: Require 50 > 150 > 200 (full stack), not just price above each.
    require_sma_stack: bool = True
    #: A moving average is "rising" if it is higher than N bars ago.
    slope_lookback: int = 20
    #: Which SMAs must be rising. The 200-SMA rising for ~1 month is the
    #: classic Stage-2 definition.
    rising_smas: tuple[int, ...] = (50, 200)
    ema_stack: tuple[int, ...] = (8, 21, 50)


@dataclass
class RelativeStrengthConfig:
    """Leadership vs. the market or vs. the scanned universe."""

    enabled: bool = True
    #: "benchmark": stock return minus benchmark return over each lookback.
    #: "rank": cross-sectional percentile of a weighted RS score (IBD-like).
    #: "auto": rank when the universe is large enough, else benchmark.
    mode: RSMode = "auto"
    lookbacks: tuple[int, ...] = (20, 50)
    weights: tuple[float, ...] = (0.5, 0.5)
    #: Benchmark mode: weighted excess return must exceed this (0 = beat SPY).
    min_outperformance: float = 0.0
    #: Rank mode: minimum percentile (0–100).
    min_rank: float = 70.0
    #: Ranks across fewer names than this are statistically meaningless.
    min_universe_for_rank: int = 20


@dataclass
class HighProximityConfig:
    """Leaders trade near their highs, not in the bargain bin."""

    enabled: bool = True
    lookback_bars: int = 252  # ~52 weeks of daily bars
    max_distance_pct: float = 0.25


@dataclass
class RecentStrengthConfig:
    """Price must have actually *moved* recently (fresh impulse)."""

    enabled: bool = True
    lookback_bars: int = 20
    min_return_pct: float = 0.05
    #: Use the max return in the window (so a pullback in progress doesn't
    #: erase the impulse that preceded it) rather than point-to-point.
    use_max_in_window: bool = True


@dataclass
class VolumeConfig:
    """Liquidity, plus optional evidence of institutional demand."""

    enabled: bool = True
    avg_window: int = 50
    min_avg_volume: float = 500_000
    #: Optional dollar-volume floor (price × volume). 0 disables.
    min_avg_dollar_volume: float = 10_000_000
    #: Require at least one volume spike during the recent impulse.
    require_impulse_spike: bool = False
    spike_multiple: float = 1.5
    spike_lookback: int = 30


@dataclass
class OscillatorConfig:
    """Optional trend-strength confirmations (each independently toggled)."""

    adx_enabled: bool = False
    adx_period: int = 14
    min_adx: float = 25.0

    macd_enabled: bool = False
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    #: Histogram must be higher than N bars ago (positive slope).
    macd_slope_bars: int = 3

    roc_enabled: bool = False
    roc_period: int = 20
    min_roc: float = 0.0


@dataclass
class VCPConfig:
    """Simple volatility-contraction (VCP-style) tightness check.

    Two measures, both scale-free:
      * ATR ratio  = ATR(short) / ATR(long)  — < 1 means volatility is shrinking.
      * Range tightness = (max close − min close) / close over a short window.
    """

    enabled: bool = True
    atr_short: int = 10
    atr_long: int = 50
    max_atr_ratio: float = 1.0
    tightness_window: int = 10
    #: Maximum closing range as a fraction of price. 0 disables this half.
    max_range_pct: float = 0.15


@dataclass
class MomentumConfig:
    """Stage 1 container."""

    trend: TrendConfig = field(default_factory=TrendConfig)
    relative_strength: RelativeStrengthConfig = field(default_factory=RelativeStrengthConfig)
    high_proximity: HighProximityConfig = field(default_factory=HighProximityConfig)
    recent_strength: RecentStrengthConfig = field(default_factory=RecentStrengthConfig)
    volume: VolumeConfig = field(default_factory=VolumeConfig)
    oscillators: OscillatorConfig = field(default_factory=OscillatorConfig)
    vcp: VCPConfig = field(default_factory=VCPConfig)


# --------------------------------------------------------------------------- #
# Stage 2 — Pullback & confirmation
# --------------------------------------------------------------------------- #
@dataclass
class PullbackConfig:
    """Geometry of a constructive pullback inside an uptrend."""

    ma_type: MAType = "ema"
    ma_period: int = 20
    #: VWAP anchoring: "session" resets each day (intraday), "rolling" uses
    #: the last `ma_period` bars (sensible on daily data).
    vwap_anchor: Literal["session", "rolling"] = "rolling"
    #: The pullback MA must itself be rising over this many bars.
    ma_slope_lookback: int = 5

    #: Window in which we look for the swing high that started the pullback
    #: and the impulse low that preceded it.
    impulse_lookback: int = 40
    min_pullback_bars: int = 2
    max_pullback_bars: int = 15

    #: Proximity: at least one pullback bar's low came within this many ATRs
    #: of the MA (or pierced it).
    ma_proximity_atr: float = 0.75
    #: Invalidation: the signal bar may not close more than this many ATRs
    #: *below* the MA — that's a breakdown, not a pullback.
    max_close_below_ma_atr: float = 0.5

    depth_mode: DepthMode = "either"
    min_depth_pct: float = 0.03
    max_depth_pct: float = 0.12
    fib_min: float = 0.382
    fib_max: float = 0.50
    #: Small tolerance so a 0.51 retrace isn't rejected on rounding alone.
    fib_tolerance: float = 0.03

    #: Pullback average volume must be <= this fraction of impulse volume.
    volume_check_enabled: bool = True
    max_volume_ratio: float = 0.9

    #: Bars on each side required to confirm a swing pivot. A pivot at bar i
    #: becomes *known* only at bar i + swing_order (no look-ahead).
    swing_order: int = 3
    higher_low_check_enabled: bool = True

    #: Emit at most one signal per pullback (same swing high). Without this,
    #: a setup that keeps confirming on consecutive bars generates duplicate
    #: alerts and double-counts trades in a backtest.
    one_signal_per_pullback: bool = True


@dataclass
class ConfirmationConfig:
    """Which reversal triggers count, and how many must fire."""

    triggers: tuple[str, ...] = ("bullish_engulfing", "hammer", "close_above_ma", "micro_high_break")
    min_triggers: int = 1
    #: Triggers that must *always* fire (in addition to min_triggers).
    required_triggers: tuple[str, ...] = ()

    # Candle geometry
    hammer_min_lower_wick_body: float = 2.0
    hammer_max_upper_wick_body: float = 0.75
    hammer_close_top_fraction: float = 0.4  # close in top 40% of range
    engulfing_require_prior_red: bool = True

    #: close_above_ma: accept "wick through MA, close above" as well as a strict
    #: close-below → close-above cross.
    ma_reclaim_allow_wick: bool = True

    micro_high_lookback: int = 3
    micro_high_use_close: bool = True

    rsi_period: int = 14
    #: In strong uptrends RSI rarely reaches 30; 40–45 is the practical
    #: "oversold" zone for pullbacks (range-shift concept).
    rsi_oversold: float = 40.0

    stoch_k: int = 14
    stoch_d: int = 3
    stoch_smooth: int = 3
    stoch_oversold: float = 25.0


# --------------------------------------------------------------------------- #
# Risk, sizing, targets
# --------------------------------------------------------------------------- #
@dataclass
class RiskConfig:
    account_equity: float = 100_000.0
    risk_per_trade_pct: float = 0.01
    #: Hard cap on any single position's notional as a fraction of equity.
    max_position_pct: float = 0.25
    lot_size: int = 1

    entry_method: EntryMethod = "close"
    #: For "breakout" entries: buy-stop this many ATRs above the signal high.
    entry_buffer_atr: float = 0.05

    atr_period: int = 14
    stop_method: StopMethod = "structure"
    #: Structure stop sits this many ATRs below the pullback low.
    stop_buffer_atr: float = 0.2
    atr_stop_multiple: float = 1.5

    #: Reject if the stop is wider than this many ATRs (risk unacceptable).
    max_stop_atr: float = 2.5
    #: If the stop is tighter than this, widen it (noise protection).
    min_stop_atr: float = 0.5

    target_method: TargetMethod = "r_multiple"
    target_r_multiple: float = 2.0
    #: Optional: reject if reward-to-risk measured to the prior swing high is
    #: below this. None disables.
    min_rr_to_swing_high: float | None = None


# --------------------------------------------------------------------------- #
# Multi-timeframe, backtest, output
# --------------------------------------------------------------------------- #
@dataclass
class MultiTimeframeConfig:
    """Higher-timeframe trend filter built by resampling the trading TF."""

    enabled: bool = True
    #: Pandas resample rule per trading timeframe.
    htf_rule: dict[str, str] = field(default_factory=lambda: {"1d": "W-FRI", "1h": "1D"})
    #: HTF moving-average length per trading timeframe
    #: (10-week ≈ 50-day; 20-day for hourly charts).
    htf_ma_period: dict[str, int] = field(default_factory=lambda: {"1d": 10, "1h": 20})
    require_htf_ma_rising: bool = True


@dataclass
class BacktestConfig:
    #: Fill on the next bar's open (realistic) rather than the signal close.
    fill_next_open: bool = True
    max_hold_bars: int = 20
    one_position_per_ticker: bool = True
    #: Round-trip cost in R is hard to generalise; use per-share commission.
    commission_per_share: float = 0.0
    slippage_pct: float = 0.0005

    # --- Portfolio-level simulation (portfolio.py) ---------------------- #
    #: Starting capital; None uses risk.account_equity.
    initial_capital: float | None = None
    #: Concurrent position limit — the real constraint on a swing book.
    max_positions: int = 10
    #: Portfolio "heat": total initial risk of open positions as a fraction
    #: of equity. 6% at 1%/trade ≈ six full-risk positions at once.
    max_portfolio_heat_pct: float = 0.06
    #: Gross exposure / equity. 1.0 = cash account, no margin.
    max_gross_exposure: float = 1.0
    #: When signals outnumber free slots, take the best first by:
    #: "rs_value" (strongest leader), "rr_to_swing_high" (most room),
    #: "tightest_stop" (smallest stop in ATR), or "fifo" (ticker order).
    signal_priority: str = "rs_value"
    #: Size off current equity (compounding) rather than starting capital.
    compound: bool = True
    #: A position cut below this fraction of its full-risk size by heat or
    #: buying-power limits is skipped rather than taken as a token position.
    min_size_fraction: float = 0.25
    risk_free_rate: float = 0.0


@dataclass
class OutputConfig:
    log_level: str = "INFO"
    signals_csv: str = "output/signals.csv"
    rejections_csv: str = "output/rejections.csv"
    plot_dir: str = "output/plots"
    #: Webhook URLs are read from the environment by default so secrets
    #: never land in config files or version control.
    discord_webhook_env: str = "DISCORD_WEBHOOK_URL"
    telegram_token_env: str = "TELEGRAM_BOT_TOKEN"
    telegram_chat_env: str = "TELEGRAM_CHAT_ID"


# --------------------------------------------------------------------------- #
# Root
# --------------------------------------------------------------------------- #
@dataclass
class ScannerConfig:
    data: DataConfig = field(default_factory=DataConfig)
    momentum: MomentumConfig = field(default_factory=MomentumConfig)
    pullback: PullbackConfig = field(default_factory=PullbackConfig)
    confirmation: ConfirmationConfig = field(default_factory=ConfirmationConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    mtf: MultiTimeframeConfig = field(default_factory=MultiTimeframeConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

    # ------------------------------------------------------------------ #
    def validate(self) -> "ScannerConfig":
        """Fail fast on configurations that would silently produce nonsense."""
        errors: list[str] = []
        unknown = set(self.confirmation.triggers) - set(ALL_TRIGGERS)
        unknown |= set(self.confirmation.required_triggers) - set(ALL_TRIGGERS)
        if unknown:
            errors.append(f"unknown confirmation triggers: {sorted(unknown)}")
        if self.confirmation.min_triggers > len(self.confirmation.triggers):
            errors.append("confirmation.min_triggers exceeds number of enabled triggers")
        rs = self.momentum.relative_strength
        if len(rs.lookbacks) != len(rs.weights):
            errors.append("relative_strength.lookbacks and weights must have equal length")
        pb = self.pullback
        if not 0 < pb.min_depth_pct < pb.max_depth_pct:
            errors.append("pullback depth bounds must satisfy 0 < min < max")
        if not 0 < pb.fib_min < pb.fib_max < 1:
            errors.append("fib bounds must satisfy 0 < fib_min < fib_max < 1")
        if pb.min_pullback_bars > pb.max_pullback_bars:
            errors.append("pullback.min_pullback_bars > max_pullback_bars")
        if pb.max_pullback_bars >= pb.impulse_lookback:
            errors.append("pullback.max_pullback_bars must be < impulse_lookback")
        r = self.risk
        if not 0 < r.risk_per_trade_pct <= 0.05:
            errors.append("risk.risk_per_trade_pct should be in (0, 0.05]")
        if r.min_stop_atr >= r.max_stop_atr:
            errors.append("risk.min_stop_atr must be < max_stop_atr")
        bt = self.backtest
        if bt.signal_priority not in {"rs_value", "rr_to_swing_high", "tightest_stop", "fifo"}:
            errors.append(f"backtest.signal_priority {bt.signal_priority!r} not recognised")
        if bt.max_positions < 1 or bt.max_portfolio_heat_pct <= 0 or bt.max_gross_exposure <= 0:
            errors.append("backtest.max_positions, max_portfolio_heat_pct, max_gross_exposure must be positive")
        if self.data.timeframe not in self.mtf.htf_rule:
            errors.append(f"mtf.htf_rule has no entry for timeframe {self.data.timeframe!r}")
        if errors:
            raise ValueError("Invalid ScannerConfig:\n  - " + "\n  - ".join(errors))
        return self

    # ------------------------------------------------------------------ #
    @classmethod
    def for_timeframe(cls, timeframe: Timeframe, **kwargs: Any) -> "ScannerConfig":
        """Preset that rescales calendar-meaning parameters for the timeframe.

        Bar-count parameters (MA lengths, pullback windows) are deliberately
        *not* rescaled: a 20-EMA pullback on an hourly chart is a legitimate,
        widely used setup in its own right. What must change are quantities
        that are really about calendar time or per-bar liquidity.
        """
        cfg = cls(**kwargs)
        if timeframe == "1d":
            return cfg
        if timeframe != "1h":
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        bpd = 7  # Yahoo US RTH hourly bars per session
        cfg.data = replace(cfg.data, timeframe="1h", period="730d", bars_per_day=bpd)
        m = cfg.momentum
        # "52-week high" — cap to what ~2y of hourly history can reasonably supply.
        m.high_proximity = replace(m.high_proximity, lookback_bars=252 * bpd)
        # Liquidity thresholds are per-bar; divide the daily floors.
        m.volume = replace(
            m.volume,
            min_avg_volume=m.volume.min_avg_volume / bpd,
            min_avg_dollar_volume=m.volume.min_avg_dollar_volume / bpd,
        )
        # Intraday swings are smaller; loosen percent depth accordingly.
        cfg.pullback = replace(cfg.pullback, min_depth_pct=0.015, max_depth_pct=0.06, vwap_anchor="session")
        cfg.data.min_bars = max(cfg.data.min_bars, cfg.momentum.trend.sma_slow + cfg.momentum.trend.slope_lookback + 10)
        return cfg

    # ------------------------------------------------------------------ #
    def with_overrides(self, overrides: Mapping[str, Any]) -> "ScannerConfig":
        """Return a deep copy with dotted-path overrides applied.

        Values are coerced to the type of the existing field where possible,
        so CLI strings like ``"0.15"`` or ``"true"`` work.
        """
        new = ScannerConfig.from_dict(self.to_dict())
        for path, value in overrides.items():
            parts = path.split(".")
            node: Any = new
            for p in parts[:-1]:
                if not hasattr(node, p):
                    raise KeyError(f"Unknown config section {p!r} in {path!r}")
                node = getattr(node, p)
            leaf = parts[-1]
            if not hasattr(node, leaf):
                raise KeyError(f"Unknown config key {leaf!r} in {path!r}")
            setattr(node, leaf, _coerce(value, getattr(node, leaf)))
        return new

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "ScannerConfig":
        return _build(cls, d)

    def to_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def from_json(cls, path: str | Path) -> "ScannerConfig":
        return cls.from_dict(json.loads(Path(path).read_text()))


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _build(klass: type, data: Mapping[str, Any]) -> Any:
    """Recursively construct nested dataclasses from a plain dict."""
    kwargs: dict[str, Any] = {}
    defaults = klass()
    for f in fields(klass):
        if f.name not in data:
            continue
        val = data[f.name]
        current = getattr(defaults, f.name)
        if is_dataclass(current) and isinstance(val, Mapping):
            kwargs[f.name] = _build(type(current), val)
        elif isinstance(current, tuple) and isinstance(val, (list, tuple)):
            kwargs[f.name] = tuple(val)
        else:
            kwargs[f.name] = val
    return klass(**kwargs)


def _coerce(value: Any, current: Any) -> Any:
    """Coerce a (possibly string) override to the type of the current value."""
    if not isinstance(value, str):
        return tuple(value) if isinstance(current, tuple) and isinstance(value, list) else value
    if isinstance(current, bool):
        if value.lower() in {"1", "true", "yes", "on"}:
            return True
        if value.lower() in {"0", "false", "no", "off"}:
            return False
        raise ValueError(f"Cannot interpret {value!r} as bool")
    if isinstance(current, int):
        return int(value)
    if isinstance(current, float) or current is None:
        if value.lower() in {"none", "null"}:
            return None
        try:
            return float(value)
        except ValueError:
            return value
    if isinstance(current, tuple):
        items = [v.strip() for v in value.split(",") if v.strip()]
        if current and isinstance(current[0], (int, float)):
            caster = type(current[0])
            return tuple(caster(v) for v in items)
        return tuple(items)
    return value


DEFAULT_WATCHLIST: tuple[str, ...] = (
    "NVDA", "AVGO", "META", "MSFT", "AAPL", "AMZN", "GOOGL", "NFLX", "TSLA", "AMD",
    "CRWD", "PLTR", "ANET", "LLY", "COST", "UBER", "NOW", "PANW", "SHOP", "MELI",
)
