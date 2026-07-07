"""Abstract base class and shared types for all TradeForge strategies."""

from __future__ import annotations

import abc
from enum import IntEnum
from typing import ClassVar

import pandas as pd


class SignalType(IntEnum):
    SELL = -1
    HOLD = 0
    BUY = 1


# Columns every strategy's output DataFrame must contain.
REQUIRED_OUTPUT_COLUMNS: tuple[str, ...] = ("signal",)


class Strategy(abc.ABC):
    """
    Base class for all TradeForge strategies.

    Subclasses implement generate_signals(df) which accepts a merged OHLCV +
    macro DataFrame and returns that same DataFrame with at minimum a 'signal'
    column (values from SignalType).  All indicator columns added during signal
    generation must be derived exclusively from data available at or before each
    row's timestamp — no lookahead.
    """

    # Subclasses declare which columns they expect in the input DataFrame.
    required_input_columns: ClassVar[tuple[str, ...]] = (
        "open", "high", "low", "close", "volume",
    )

    @abc.abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Return df with a 'signal' column added (and any intermediate indicator
        columns).  The input DataFrame must not be mutated — return a copy.
        """

    def validate_input(self, df: pd.DataFrame) -> None:
        missing = [c for c in self.required_input_columns if c not in df.columns]
        if missing:
            raise ValueError(f"{type(self).__name__} missing input columns: {missing}")

    def validate_output(self, df: pd.DataFrame) -> None:
        missing = [c for c in REQUIRED_OUTPUT_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"{type(self).__name__} generate_signals() missing output columns: {missing}")
        invalid = df["signal"].dropna()[~df["signal"].dropna().isin([s.value for s in SignalType])]
        if not invalid.empty:
            raise ValueError(f"{type(self).__name__} produced invalid signal values: {invalid.unique().tolist()}")

    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        self.validate_input(df)
        result = self.generate_signals(df)
        self.validate_output(result)
        return result
