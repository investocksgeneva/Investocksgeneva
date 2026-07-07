"""
InvestocksGeneva — CLI stock portfolio tracker.
Supports any ticker on Yahoo Finance (incl. Swiss: NOVN.SW, NESN.SW, ROG.SW).
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    print("yfinance not installed. Run: pip install yfinance")
    sys.exit(1)

PORTFOLIO_FILE = Path("portfolio.json")


def load_portfolio() -> dict:
    if PORTFOLIO_FILE.exists():
        with open(PORTFOLIO_FILE) as f:
            return json.load(f)
    return {"positions": []}


def save_portfolio(portfolio: dict) -> None:
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(portfolio, f, indent=2)


def add_position(ticker: str, shares: float, buy_price: float) -> None:
    portfolio = load_portfolio()
    portfolio["positions"].append(
        {
            "ticker": ticker.upper(),
            "shares": shares,
            "buy_price": buy_price,
            "added": datetime.utcnow().isoformat(),
        }
    )
    save_portfolio(portfolio)
    print(f"Added {shares} x {ticker.upper()} @ {buy_price:.2f}")


def remove_position(ticker: str) -> None:
    portfolio = load_portfolio()
    before = len(portfolio["positions"])
    portfolio["positions"] = [
        p for p in portfolio["positions"] if p["ticker"] != ticker.upper()
    ]
    if len(portfolio["positions"]) < before:
        save_portfolio(portfolio)
        print(f"Removed all positions for {ticker.upper()}")
    else:
        print(f"No position found for {ticker.upper()}")


def fetch_price(ticker: str) -> float | None:
    try:
        data = yf.Ticker(ticker).fast_info
        price = data.get("last_price") or data.get("regularMarketPrice")
        return float(price) if price else None
    except Exception:
        return None


def show_portfolio() -> None:
    portfolio = load_portfolio()
    positions = portfolio.get("positions", [])
    if not positions:
        print("Portfolio is empty. Use 'add <TICKER> <shares> <buy_price>' to start.")
        return

    tickers = list({p["ticker"] for p in positions})
    prices = {t: fetch_price(t) for t in tickers}

    total_cost = 0.0
    total_value = 0.0

    header = f"{'Ticker':<10} {'Shares':>8} {'Buy @':>10} {'Now @':>10} {'Cost':>12} {'Value':>12} {'P&L':>10} {'%':>7}"
    print("\n" + header)
    print("-" * len(header))

    for pos in positions:
        ticker = pos["ticker"]
        shares = pos["shares"]
        buy_price = pos["buy_price"]
        current = prices.get(ticker)

        cost = shares * buy_price
        total_cost += cost

        if current is not None:
            value = shares * current
            pnl = value - cost
            pct = (pnl / cost) * 100 if cost else 0.0
            total_value += value
            print(
                f"{ticker:<10} {shares:>8.2f} {buy_price:>10.2f} {current:>10.2f} "
                f"{cost:>12.2f} {value:>12.2f} {pnl:>+10.2f} {pct:>+6.1f}%"
            )
        else:
            total_value += cost
            print(
                f"{ticker:<10} {shares:>8.2f} {buy_price:>10.2f} {'N/A':>10} "
                f"{cost:>12.2f} {'N/A':>12} {'N/A':>10} {'N/A':>7}"
            )

    print("-" * len(header))
    total_pnl = total_value - total_cost
    total_pct = (total_pnl / total_cost) * 100 if total_cost else 0.0
    print(
        f"{'TOTAL':<10} {' ':>8} {' ':>10} {' ':>10} "
        f"{total_cost:>12.2f} {total_value:>12.2f} {total_pnl:>+10.2f} {total_pct:>+6.1f}%"
    )
    print()


def print_help() -> None:
    print(
        """
InvestocksGeneva — commands:
  show                              Show portfolio with live prices and P&L
  add <TICKER> <shares> <price>     Add a position  (e.g. add NESN.SW 10 95.50)
  remove <TICKER>                   Remove all lots for a ticker
  help                              Show this message
"""
    )


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("help", "--help", "-h"):
        print_help()
    elif args[0] == "show":
        show_portfolio()
    elif args[0] == "add" and len(args) == 4:
        add_position(args[1], float(args[2]), float(args[3]))
    elif args[0] == "remove" and len(args) == 2:
        remove_position(args[1])
    else:
        print(f"Unknown command: {' '.join(args)}")
        print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
