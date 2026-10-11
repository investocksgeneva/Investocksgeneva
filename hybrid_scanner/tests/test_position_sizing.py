import pytest

from hybrid_scanner.config import RiskConfig
from hybrid_scanner.position_sizing import build_trade_plan, position_size


def test_fixed_fractional_size():
    ps = position_size(100_000, 0.01, entry=50.0, stop=48.0)
    assert ps.shares == 500  # $1,000 / $2
    assert ps.dollar_risk == pytest.approx(1000.0)
    assert ps.capped_by == "risk"


def test_max_position_cap():
    ps = position_size(100_000, 0.01, entry=100.0, stop=99.5, max_position_pct=0.25)
    assert ps.shares == 250 and ps.capped_by == "max_position"
    assert ps.dollar_risk < 1000


@pytest.mark.parametrize("entry,stop", [(50, 50), (50, 51), (-1, 0.5)])
def test_invalid_levels_raise(entry, stop):
    with pytest.raises(ValueError):
        position_size(100_000, 0.01, entry, stop)


def test_structure_stop_and_target():
    cfg = RiskConfig(stop_buffer_atr=0.2, target_r_multiple=2.0)
    plan, why = build_trade_plan(cfg, signal_close=100, signal_high=101, pullback_low=96, swing_high=106, atr=2.0)
    assert not why
    assert plan.stop == pytest.approx(95.6)
    assert plan.target == pytest.approx(100 + 2 * 4.4)
    assert plan.rr_to_swing_high == pytest.approx(6 / 4.4)


def test_wide_stop_rejected():
    cfg = RiskConfig(max_stop_atr=2.0)
    plan, why = build_trade_plan(cfg, signal_close=100, signal_high=101, pullback_low=90, swing_high=110, atr=2.0)
    assert plan is None and "ATR" in why[0]


def test_tight_stop_widened_to_noise_floor():
    cfg = RiskConfig(min_stop_atr=0.5, stop_buffer_atr=0.0)
    plan, _ = build_trade_plan(cfg, signal_close=100, signal_high=101, pullback_low=99.9, swing_high=105, atr=2.0)
    assert plan.stop == pytest.approx(99.0)
    assert plan.notes
