"""
FlowConfirmedSwingPullback (FCSP) strategy.

Entry logic — three confluence factors, all checked on the previous closed candle
(strict no-lookahead via shift(1) before comparing to any threshold):

  1. Regime filter   : close > EMA(200)  — only trade in a broad uptrend
  2. Price action    : fast EMA > slow EMA (established uptrend) AND price
                       recently pulled back to within pullback_band of the slow
                       EMA, then bounced (close > ema_slow).
  3. Macro confluence:
       a. Funding signal  — daily aggregated funding rate is <= funding_threshold
                            (negative/neutral rates signal overcrowded shorts →
                            potential squeeze, contrarian bullish)
       b. ETF flow signal — rolling 3-day sum of net ETF inflows is positive

All three factors required when require_both_confluence_legs=True (default).
When False, only factors 2 and 3a are required (price action + funding), making
the strategy usable when ETF flow data is unavailable.

Exit: fast EMA crosses below slow EMA (death cross).  Hard stop and take-profit
are handled by the backtester (ATR-based), not by this class.
"""

from __future__ import annotations

from typing import ClassVar

import numpy as np
import pandas as pd

from .base import SignalType, Strategy


class FlowConfirmedPullback(Strategy):
    required_input_columns: ClassVar[tuple[str, ...]] = (
        "open", "high", "low", "close", "volume",
    )

    def __init__(
        self,
        ema_fast: int = 9,
        ema_slow: int = 21,
        ema_regime: int = 200,
        atr_period: int = 14,
        atr_stop_mult: float = 2.0,
        pullback_band: float = 0.02,       # price within 2% above slow EMA counts as pullback
        pullback_lookback: int = 5,        # bars to look back for a pullback event
        funding_threshold: float = 0.0001, # daily rate; ≤ this is "non-extreme positive"
        etf_flow_window: int = 3,          # rolling days for ETF flow sum
        require_both_confluence_legs: bool = False,
    ) -> None:
        if ema_fast >= ema_slow:
            raise ValueError(f"ema_fast ({ema_fast}) must be < ema_slow ({ema_slow})")
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.ema_regime = ema_regime
        self.atr_period = atr_period
        self.atr_stop_mult = atr_stop_mult
        self.pullback_band = pullback_band
        self.pullback_lookback = pullback_lookback
        self.funding_threshold = funding_threshold
        self.etf_flow_window = etf_flow_window
        self.require_both_confluence_legs = require_both_confluence_legs

    # ------------------------------------------------------------------
    # Indicators
    # ------------------------------------------------------------------

    def _add_emas(self, df: pd.DataFrame) -> pd.DataFrame:
        df["ema_fast"] = df["close"].ewm(span=self.ema_fast, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=self.ema_slow, adjust=False).mean()
        df["ema_regime"] = df["close"].ewm(span=self.ema_regime, adjust=False).mean()
        return df

    def _add_atr(self, df: pd.DataFrame) -> pd.DataFrame:
        high_low = df["high"] - df["low"]
        high_pc = (df["high"] - df["close"].shift(1)).abs()
        low_pc = (df["low"] - df["close"].shift(1)).abs()
        tr = pd.concat([high_low, high_pc, low_pc], axis=1).max(axis=1)
        df["atr"] = tr.ewm(span=self.atr_period, adjust=False).mean()
        return df

    def _add_regime_filter(self, df: pd.DataFrame) -> pd.DataFrame:
        # Shift(1): we see last closed candle's position, not current
        df["regime_bullish"] = df["ema_regime"].shift(1) < df["close"].shift(1)
        return df

    def _add_price_action(self, df: pd.DataFrame) -> pd.DataFrame:
        # Uptrend: fast > slow on the previous candle
        df["in_uptrend"] = df["ema_fast"].shift(1) > df["ema_slow"].shift(1)

        # Pullback: price touched within pullback_band above slow EMA in last N bars
        near_slow = df["close"] <= df["ema_slow"] * (1 + self.pullback_band)
        df["recent_pullback"] = (
            near_slow.shift(1)
            .rolling(window=self.pullback_lookback, min_periods=1)
            .max()
            .astype(bool)
        )

        # Bounce: price is now above the slow EMA (recovered from pullback)
        df["bounce"] = df["close"].shift(1) > df["ema_slow"].shift(1)

        df["price_action_buy"] = df["in_uptrend"] & df["recent_pullback"] & df["bounce"]

        # Exit: fast EMA crossing below slow
        fast_below = df["ema_fast"].shift(1) < df["ema_slow"].shift(1)
        fast_was_above = df["ema_fast"].shift(2) >= df["ema_slow"].shift(2)
        df["price_action_sell"] = fast_below & fast_was_above
        return df

    def _add_funding_signal(self, df: pd.DataFrame) -> pd.DataFrame:
        if "funding_rate" not in df.columns:
            df["funding_signal"] = True  # treat as neutral when data absent
            return df
        df["funding_signal"] = df["funding_rate"].shift(1) <= self.funding_threshold
        return df

    def _add_etf_flow_signal(self, df: pd.DataFrame) -> pd.DataFrame:
        if "etf_flow" not in df.columns:
            df["etf_flow_signal"] = True  # neutral when absent
            return df
        rolling_flow = df["etf_flow"].rolling(window=self.etf_flow_window, min_periods=1).sum()
        df["etf_flow_signal"] = rolling_flow.shift(1) > 0
        return df

    # ------------------------------------------------------------------
    # Signal assembly
    # ------------------------------------------------------------------

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df = self._add_emas(df)
        df = self._add_atr(df)
        df = self._add_regime_filter(df)
        df = self._add_price_action(df)
        df = self._add_funding_signal(df)
        df = self._add_etf_flow_signal(df)

        if self.require_both_confluence_legs:
            macro_ok = df["funding_signal"] & df["etf_flow_signal"]
            buy_cond = df["regime_bullish"] & df["price_action_buy"] & macro_ok
        else:
            # Relaxed: regime + price action + funding only
            buy_cond = df["regime_bullish"] & df["price_action_buy"] & df["funding_signal"]

        signal = pd.Series(SignalType.HOLD, index=df.index, dtype=int)
        signal[buy_cond] = SignalType.BUY
        signal[df["price_action_sell"]] = SignalType.SELL

        # A SELL on the same bar as a BUY → SELL wins (conservative)
        signal[buy_cond & df["price_action_sell"]] = SignalType.SELL

        df["signal"] = signal
        return df

    def stop_price(self, entry: float, atr: float) -> float:
        """Hard stop below entry, computed by the strategy for the backtester."""
        return entry - self.atr_stop_mult * atr

    def __repr__(self) -> str:
        return (
            f"FlowConfirmedPullback(ema_fast={self.ema_fast}, ema_slow={self.ema_slow}, "
            f"atr_stop_mult={self.atr_stop_mult}, atr_period={self.atr_period})"
        )
