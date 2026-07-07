"""
Position sizing and portfolio-level risk checks.

Deliberately decoupled from signal generation — sizing logic lives here, not in
strategies or the backtester, so it can be unit-tested independently.
"""

from __future__ import annotations

from dataclasses import dataclass


def fixed_fractional_size(
    capital: float,
    risk_pct: float,
    entry_price: float,
    stop_price: float,
) -> float:
    """
    Return the number of units (BTC) to buy such that if the stop is hit the
    loss equals exactly risk_pct * capital.

    Parameters
    ----------
    capital     : current available capital in USDT
    risk_pct    : fraction of capital to risk per trade (e.g. 0.01 = 1 %)
    entry_price : fill price in USDT
    stop_price  : hard stop price in USDT (must be < entry_price for a long)

    Returns
    -------
    float : position size in BTC (> 0), or 0 if inputs are degenerate.
    """
    if entry_price <= 0 or stop_price <= 0:
        return 0.0
    risk_per_unit = entry_price - stop_price
    if risk_per_unit <= 0:
        return 0.0
    risk_capital = capital * risk_pct
    return risk_capital / risk_per_unit


@dataclass
class PortfolioExposure:
    open_risk_usdt: float   # total $ at risk across all open positions
    open_value_usdt: float  # total notional value of open positions


def portfolio_risk_check(
    exposure: PortfolioExposure,
    capital: float,
    max_portfolio_risk: float = 0.05,
    max_portfolio_exposure: float = 0.30,
) -> bool:
    """
    Return True if opening another position is safe given current exposure.

    Parameters
    ----------
    exposure            : current portfolio exposure summary
    capital             : total capital (deployed + cash) in USDT
    max_portfolio_risk  : max fraction of capital at risk simultaneously (default 5 %)
    max_portfolio_exposure : max notional fraction of capital deployed (default 30 %)
    """
    if capital <= 0:
        return False
    risk_ok = (exposure.open_risk_usdt / capital) < max_portfolio_risk
    exposure_ok = (exposure.open_value_usdt / capital) < max_portfolio_exposure
    return risk_ok and exposure_ok
