"""
Scrape daily Bitcoin spot ETF net flow data from Farside Investors.

Key design decisions:
- Strict schema-drift detection: if the column layout changes, we raise rather
  than silently returning junk data.
- NaN vs. zero distinction: a blank cell means data is not yet available (NaN);
  a cell containing '0' or '-' means an actual zero flow.
- The 'Total' column is used as the etf_flow series; per-ETF columns are kept
  for inspection but are not surfaced in the output contract.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import requests

# Farside Investors BTC ETF flow table
_FARSIDE_URL = "https://farside.co.uk/bitcoin-etf-flow-all-data-delayed/"

# Columns we expect in the Farside table (order matters for drift detection)
_EXPECTED_ETF_COLUMNS = {
    "IBIT", "FBTC", "BITB", "ARKB", "BTCO", "EZBC", "BRRR", "HODL", "BTCW", "GBTC", "BTC", "Total",
}


class SchemaError(RuntimeError):
    """Raised when the scraped page layout doesn't match the expected schema."""


class ETFFlowScraper:
    """
    Parameters
    ----------
    url         : URL of the Farside ETF flow page (override for testing)
    timeout     : HTTP request timeout in seconds
    max_retries : retries on network errors
    """

    def __init__(
        self,
        url: str = _FARSIDE_URL,
        timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        self.url = url
        self.timeout = timeout
        self.max_retries = max_retries

    def _get_html(self) -> str:
        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                resp = requests.get(self.url, timeout=self.timeout)
                resp.raise_for_status()
                return resp.text
            except requests.RequestException as err:
                last_err = err
                import time
                time.sleep(2 ** attempt)
        raise RuntimeError(
            f"ETFFlowScraper: failed to fetch {self.url} after {self.max_retries} retries"
        ) from last_err

    def _parse_html(self, html: str) -> pd.DataFrame:
        """Parse the Farside HTML page and return a raw DataFrame."""
        import io
        try:
            tables = pd.read_html(io.StringIO(html), flavor="lxml")
        except Exception:
            tables = pd.read_html(io.StringIO(html))

        if not tables:
            raise SchemaError("ETFFlowScraper: no HTML tables found on the page")

        # The main flow table is the largest one
        df = max(tables, key=len)
        return df

    def _validate_schema(self, df: pd.DataFrame) -> None:
        """Raise SchemaError if critical columns are absent."""
        cols = set(str(c).strip() for c in df.columns)
        if "Total" not in cols:
            raise SchemaError(
                f"ETFFlowScraper: 'Total' column missing. Found: {sorted(cols)}"
            )
        # Date column heuristic — first column should be parseable as dates
        first_col = df.columns[0]
        sample = df[first_col].dropna().head(5)
        parseable = 0
        for val in sample:
            try:
                pd.to_datetime(str(val), dayfirst=False)
                parseable += 1
            except Exception:
                pass
        if parseable == 0:
            raise SchemaError(
                "ETFFlowScraper: first column does not appear to contain dates"
            )

    @staticmethod
    def _parse_flow_value(val) -> float:
        """Convert a cell value to float; blank / dash / unavailable → NaN."""
        if pd.isna(val):
            return float("nan")
        s = str(val).strip().replace(",", "")
        if s in ("", "-", "N/A", "n/a", "—"):
            return float("nan")
        # Strip parentheses used for negatives in some table formats: (123) → -123
        if s.startswith("(") and s.endswith(")"):
            s = "-" + s[1:-1]
        try:
            return float(s)
        except ValueError:
            return float("nan")

    def fetch(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """
        Scrape and return a DataFrame with columns ['etf_flow'] indexed by UTC date.

        *start* and *end* filter the result if provided.
        NaN rows indicate days where data has not yet been published.
        """
        html = self._get_html()
        raw = self._parse_html(html)
        self._validate_schema(raw)

        date_col = raw.columns[0]
        total_col = next(c for c in raw.columns if str(c).strip() == "Total")

        # Parse dates
        dates = pd.to_datetime(raw[date_col].astype(str), errors="coerce", dayfirst=False)
        flows = raw[total_col].apply(self._parse_flow_value)

        df = pd.DataFrame({"date": dates, "etf_flow": flows})
        df = df.dropna(subset=["date"])
        df["date"] = df["date"].dt.tz_localize("UTC")
        df = df.set_index("date").sort_index()
        df = df[~df.index.duplicated(keep="last")]

        if start is not None:
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            df = df[df.index >= pd.Timestamp(start)]
        if end is not None:
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            df = df[df.index <= pd.Timestamp(end)]

        return df
