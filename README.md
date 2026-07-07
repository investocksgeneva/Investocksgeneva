# InvestocksGeneva

A lightweight CLI stock portfolio tracker with live prices and P&L, built with Python and Yahoo Finance data.
Supports any ticker on Yahoo Finance — including Swiss exchange stocks like `NESN.SW`, `NOVN.SW`, and `ROG.SW`.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Show your portfolio with live prices and P&L
python portfolio.py show

# Add a position: ticker, number of shares, purchase price
python portfolio.py add NESN.SW 10 95.50
python portfolio.py add AAPL 5 180.00
python portfolio.py add NOVN.SW 20 88.30

# Remove all lots for a ticker
python portfolio.py remove NESN.SW
```

### Example output

```
Ticker      Shares      Buy @      Now @          Cost        Value        P&L       %
------------------------------------------------------------------------------------------
NESN.SW      10.00      95.50      98.20        955.00       982.00      +27.00   +2.8%
AAPL          5.00     180.00     195.50        900.00       977.50      +77.50   +8.6%
------------------------------------------------------------------------------------------
TOTAL                                          1855.00      1959.50     +104.50   +5.6%
```

## Portfolio data

Positions are stored locally in `portfolio.json` (excluded from git via `.gitignore`).

## Supported markets

Any ticker supported by Yahoo Finance works out of the box:

| Market | Suffix | Example |
|--------|--------|---------|
| Swiss Exchange (SIX) | `.SW` | `NESN.SW` |
| US markets | _(none)_ | `AAPL`, `MSFT` |
| London Stock Exchange | `.L` | `SHEL.L` |
| Euronext Paris | `.PA` | `MC.PA` |
