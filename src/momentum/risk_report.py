"""
Momentum equity risk report.

Computes aggregate stop-risk, utilisation, and flags sector concentration
and per-position warnings.

Usage:
    python -m src.momentum.risk_report
"""

from __future__ import annotations
from typing import List, Dict
from .positions import POSITIONS, CAPITAL, AGGREGATE_STOP_RISK_LIMIT_PCT, Position

# Sectors with >=3 positions trigger a correlation warning
CLUSTER_WARN_THRESHOLD = 3


def _sector_counts(positions: List[Position]) -> Dict[str, List[str]]:
    counts: Dict[str, List[str]] = {}
    for p in positions:
        counts.setdefault(p.sector, []).append(p.ticker)
    return counts


def generate_report(positions: List[Position] = POSITIONS, capital: float = CAPITAL) -> str:
    lines: List[str] = []

    # ── Header ──────────────────────────────────────────────────────────────
    lines.append("=" * 70)
    lines.append("MOMENTUM EQUITY RISK REPORT")
    lines.append(f"Capital: ${capital:,.0f}")
    lines.append("=" * 70)

    # ── Position table ───────────────────────────────────────────────────────
    lines.append(
        f"\n{'Ticker':<7} {'Shares':>6} {'Entry':>8} "
        f"{'Stop':>8} {'Notional':>10} {'Risk $':>8}"
    )
    lines.append("-" * 56)

    total_notional = 0.0
    total_stop_risk = 0.0

    for p in positions:
        notional = p.notional
        risk = p.stop_risk
        total_notional += notional
        total_stop_risk += risk
        lines.append(
            f"{p.ticker:<7} {p.shares:>6} "
            f"{p.entry_price:>8.2f} {p.stop_price:>8.2f} "
            f"${notional:>9,.0f} ${risk:>7,.0f}"
        )

    lines.append("-" * 56)
    utilisation_pct = (total_notional / capital) * 100
    stop_risk_pct = (total_stop_risk / capital) * 100
    lines.append(f"{'TOTAL':<7} {'':>6} {'':>8} {'':>8} "
                 f"${total_notional:>9,.0f} ${total_stop_risk:>7,.0f}")
    lines.append("")
    lines.append(f"Utilisation  : ${total_notional:,.0f} / ${capital:,.0f} = {utilisation_pct:.1f}%")
    lines.append(f"Agg stop-risk: ${total_stop_risk:,.0f} = {stop_risk_pct:.2f}% of equity")

    # ── Utilisation warning ──────────────────────────────────────────────────
    lines.append("")
    if utilisation_pct > 98:
        lines.append(f"[WARN] Utilisation {utilisation_pct:.1f}% > 98% — leave buffer for fills and margin.")
    else:
        lines.append(f"[OK]   Utilisation {utilisation_pct:.1f}%")

    if stop_risk_pct > AGGREGATE_STOP_RISK_LIMIT_PCT * 100:
        lines.append(
            f"[WARN] Aggregate stop-risk {stop_risk_pct:.2f}% exceeds "
            f"{AGGREGATE_STOP_RISK_LIMIT_PCT*100:.0f}% guideline — consider trimming."
        )
    else:
        lines.append(f"[OK]   Aggregate stop-risk {stop_risk_pct:.2f}% within limit.")

    # ── Sector concentration ─────────────────────────────────────────────────
    sector_map = _sector_counts(positions)
    lines.append("")
    lines.append("── Sector breakdown ──")
    for sector, tickers in sorted(sector_map.items(), key=lambda x: -len(x[1])):
        tag = f"[WARN] Cluster ({len(tickers)} positions)" if len(tickers) >= CLUSTER_WARN_THRESHOLD else "[OK]  "
        lines.append(f"  {tag}  {sector}: {', '.join(tickers)}")

    # ── Per-position flags ───────────────────────────────────────────────────
    flagged = [p for p in positions if p.flags]
    if flagged:
        lines.append("")
        lines.append("── Position flags ──")
        for p in flagged:
            for flag in p.flags:
                lines.append(f"  [{p.ticker}] {flag}")

    # ── Trim suggestions (positions > 3% of capital) ─────────────────────────
    high_concentration = [p for p in positions if p.notional / capital > 0.03]
    if high_concentration:
        lines.append("")
        lines.append("── High-concentration positions (notional > 3% of capital) ──")
        for p in sorted(high_concentration, key=lambda x: -x.notional):
            lines.append(
                f"  {p.ticker}: ${p.notional:,.0f} ({p.notional/capital*100:.1f}%) "
                f"— consider trimming 1-2 shares if risk budget is tight."
            )

    lines.append("")
    lines.append("=" * 70)
    lines.append("Disclaimer: Research tool only. Verify all prices before trading.")
    lines.append("=" * 70)

    return "\n".join(lines)


def main() -> None:
    print(generate_report())


if __name__ == "__main__":
    main()
