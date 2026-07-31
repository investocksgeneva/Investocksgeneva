"""Tests for src/momentum/positions.py and src/momentum/risk_report.py."""

import pytest
from src.momentum.positions import Position, POSITIONS, CAPITAL
from src.momentum.risk_report import generate_report, _sector_counts


# ── Position dataclass ───────────────────────────────────────────────────────

def test_position_notional():
    p = Position("TST", shares=10, entry_price=100.0, stop_price=90.0)
    assert p.notional == pytest.approx(1000.0)


def test_position_stop_risk():
    p = Position("TST", shares=10, entry_price=100.0, stop_price=90.0)
    assert p.stop_risk == pytest.approx(100.0)


def test_position_stop_risk_zero_when_stop_above_entry():
    p = Position("TST", shares=10, entry_price=90.0, stop_price=100.0)
    assert p.stop_risk == 0.0


def test_all_positions_have_positive_stop_risk():
    for p in POSITIONS:
        if "DATA_CHECK" not in " ".join(p.flags):
            assert p.stop_risk > 0, f"{p.ticker} has non-positive stop risk"


def test_all_stops_below_entry():
    for p in POSITIONS:
        assert p.stop_price < p.entry_price, (
            f"{p.ticker}: stop {p.stop_price} >= entry {p.entry_price}"
        )


# ── Sector counts ────────────────────────────────────────────────────────────

def test_sector_counts_keys():
    counts = _sector_counts(POSITIONS)
    assert "Energy-Refiner" in counts
    assert "Healthcare" in counts


def test_sector_counts_energy_refiner_cluster():
    counts = _sector_counts(POSITIONS)
    assert len(counts["Energy-Refiner"]) >= 3, "Expect MPC, PSX, VLO"


def test_sector_counts_healthcare_cluster():
    counts = _sector_counts(POSITIONS)
    assert len(counts["Healthcare"]) >= 3


# ── generate_report ──────────────────────────────────────────────────────────

def test_report_contains_all_tickers():
    report = generate_report()
    for p in POSITIONS:
        assert p.ticker in report, f"{p.ticker} missing from report"


def test_report_flags_lh_earnings():
    report = generate_report()
    assert "LH" in report
    assert "EARNINGS_RISK" in report


def test_report_flags_bxp_data_check():
    report = generate_report()
    assert "BXP" in report
    assert "DATA_CHECK" in report


def test_report_cluster_warning_present():
    report = generate_report()
    assert "[WARN] Cluster" in report


def test_report_shows_totals():
    report = generate_report()
    assert "TOTAL" in report
    assert "Utilisation" in report
    assert "Agg stop-risk" in report


def test_report_custom_capital():
    report = generate_report(capital=50_000.0)
    assert "50,000" in report


def test_report_custom_positions():
    custom = [
        Position("AAA", shares=5, entry_price=100.0, stop_price=90.0, sector="Tech"),
        Position("BBB", shares=5, entry_price=200.0, stop_price=180.0, sector="Tech"),
    ]
    report = generate_report(positions=custom, capital=10_000.0)
    assert "AAA" in report
    assert "BBB" in report
    assert "[WARN] Cluster" not in report  # only 2, below threshold of 3


def test_report_high_concentration_flagged():
    big = [Position("BIG", shares=1000, entry_price=100.0, stop_price=90.0, sector="X")]
    report = generate_report(positions=big, capital=10_000.0)
    assert "High-concentration" in report


def test_total_stop_risk_matches_sum():
    total = sum(p.stop_risk for p in POSITIONS)
    assert total > 0
    report = generate_report()
    # The report prints total stop risk as integer dollars
    assert str(int(total)) in report or f"{total:,.0f}" in report
