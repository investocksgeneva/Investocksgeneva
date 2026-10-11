import numpy as np
import pandas as pd
import pytest

from hybrid_scanner import indicators as ind
from hybrid_scanner.utils import SyntheticProvider


@pytest.fixture(scope="module")
def df():
    return SyntheticProvider(n_bars=400).get_history("TEST")


def test_rsi_bounded(df):
    r = ind.rsi(df["close"]).dropna()
    assert ((r >= 0) & (r <= 100)).all()


def test_rsi_all_gains_is_100():
    s = pd.Series(np.arange(1.0, 40.0))
    assert ind.rsi(s, 14).iloc[-1] == 100.0


def test_atr_matches_manual_wilder(df):
    tr = ind.true_range(df)
    manual = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    pd.testing.assert_series_equal(ind.atr(df, 14), manual, check_names=False)


def test_atr_contraction_is_scale_free(df):
    scaled = df.copy()
    scaled[["open", "high", "low", "close"]] *= 37.0
    a = ind.atr_contraction_ratio(df, 10, 50).dropna()
    b = ind.atr_contraction_ratio(scaled, 10, 50).dropna()
    np.testing.assert_allclose(a.to_numpy(), b.to_numpy(), rtol=1e-9)


@pytest.mark.parametrize("cut", [150, 233, 399])
def test_swing_points_have_no_lookahead(df, cut):
    full = ind.swing_points(df["high"], df["low"], 3).iloc[:cut]
    trunc = ind.swing_points(df["high"].iloc[:cut], df["low"].iloc[:cut], 3)
    pd.testing.assert_frame_equal(full, trunc)


def test_swing_point_detects_obvious_peak():
    high = pd.Series([1, 2, 3, 9, 3, 2, 1, 1, 1.0])
    low = high - 0.5
    piv = ind.swing_points(high, low, 3)
    # Peak at bar 3 is confirmed (and reported) at bar 6.
    assert piv["pivot_high"].iloc[6] == 9
    assert piv["pivot_high_bar"].iloc[6] == 3
    assert piv["pivot_high"].iloc[:6].isna().all()


@pytest.mark.parametrize("cut", [200, 301, 397])
def test_higher_timeframe_trend_has_no_lookahead(df, cut):
    full = ind.higher_timeframe_trend(df, "W-FRI", 10).iloc[:cut]
    trunc = ind.higher_timeframe_trend(df.iloc[:cut], "W-FRI", 10)
    # The final (possibly partial) week legitimately differs in live use;
    # everything before the last week must match exactly.
    last_week_start = df.index[cut - 1] - pd.Timedelta(days=7)
    mask = full.index <= last_week_start
    pd.testing.assert_series_equal(full[mask], trunc[mask])


def _candles(rows):
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=pd.date_range("2025-01-01", periods=len(rows)))


def test_bullish_engulfing():
    df = _candles([[10, 10.2, 9.4, 9.5], [9.4, 10.5, 9.3, 10.3]])
    assert ind.bullish_engulfing(df).tolist() == [False, True]


def test_hammer():
    # Long lower wick, small body near the top.
    df = _candles([[10.0, 10.1, 9.0, 10.05]])
    assert ind.hammer(df).iloc[0]
    # Shooting star (long upper wick) is not a hammer.
    df = _candles([[10.0, 11.0, 9.95, 10.05]])
    assert not ind.hammer(df).iloc[0]


def test_ema_stack():
    up = pd.Series(np.linspace(10, 50, 200))
    assert ind.ema_stack_aligned(up, (8, 21, 50)).iloc[-1]
    assert not ind.ema_stack_aligned(up[::-1].reset_index(drop=True), (8, 21, 50)).iloc[-1]
