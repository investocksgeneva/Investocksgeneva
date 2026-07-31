"""
Momentum position data for the FlowConfirmed equity scan.

Source: Momentum reminder scan — capital $100k, scale factor ~0.565 applied.
Recommended shares are post-scale (ready to enter).
Update entry_price / stop_price to live market values before trading.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict


CAPITAL = 100_000.0
AGGREGATE_STOP_RISK_LIMIT_PCT = 0.10  # warn above 10%
CONCENTRATION_WARN_PCT = 0.03          # warn per-position notional above 3%

# Sectors with >= this many positions trigger a correlation cluster warning
CLUSTER_WARN_THRESHOLD = 3


@dataclass
class Position:
    ticker: str
    shares: int           # recommended post-scale shares
    entry_price: float
    stop_price: float
    sector: str = ""
    flags: List[str] = field(default_factory=list)

    @property
    def notional(self) -> float:
        return self.shares * self.entry_price

    @property
    def stop_risk(self) -> float:
        """Dollar risk if stop is hit = (entry - stop) * shares."""
        return max(0.0, (self.entry_price - self.stop_price) * self.shares)


# ---------------------------------------------------------------------------
# Post-scale positions from the Momentum reminder scan.
# Entry prices are estimates — update with live prices before entering.
# Stops are from the scan; BXP stop is flagged for manual verification.
# ---------------------------------------------------------------------------

POSITIONS: List[Position] = [
    # ticker     shares  entry    stop      sector
    Position("MPC",    9, 164.50, 152.10, "Energy-Refiner"),
    Position("DVA",   14, 168.80, 157.30, "Healthcare"),
    Position("PRU",   34,  98.40,  90.10, "Insurance"),
    Position("PSX",   13, 131.20, 120.50, "Energy-Refiner"),
    Position("MET",   43,  79.60,  72.80, "Insurance"),
    Position("VLO",   14, 131.90, 121.20, "Energy-Refiner"),
    Position("HST",  146,  17.00,  15.50, "REIT"),
    Position("AAPL",  20, 201.00, 186.20, "Technology"),
    Position("DGX",   24, 145.30, 134.10, "Healthcare"),
    Position(
        "LH", 18, 210.60, 194.30, "Healthcare",
        flags=[
            "EARNINGS_RISK: Verify LH earnings date before entering — "
            "earnings release is a binary event that overrides technical setup."
        ],
    ),
    Position("AIZ",   14, 180.50, 166.80, "Insurance"),
    Position("SOLV",  32,  57.30,  52.40, "Healthcare"),
    Position("CPAY",   7, 329.10, 303.20, "Financials"),
    Position("VTRS", 357,   9.80,   8.90, "Healthcare"),
    Position("BAC",  136,  41.60,  38.20, "Financials"),
    Position("ROST",  28, 152.40, 140.30, "Consumer"),
    Position("AMP",   12, 440.20, 405.50, "Financials"),
    Position(
        "BXP", 80,  74.20,  68.50, "REIT",
        flags=[
            "DATA_CHECK: Source scan showed stop = '5,734' — looks like notional "
            "was accidentally placed in the stop column. Expected stop ~$68-70 for BXP ~$74. "
            "Verify against your scan before entering."
        ],
    ),
    Position("GEN",  190,  26.00,  23.70, "Technology"),
    Position("RTX",   29, 131.40, 121.10, "Industrials"),
]
