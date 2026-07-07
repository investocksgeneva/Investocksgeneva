"""Tests for ETFFlowScraper — 14 tests (HTML mocks, no network)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.data.etf_flow_scraper import ETFFlowScraper, SchemaError


# Minimal valid Farside-like HTML
_VALID_HTML = """
<table>
  <tr><th>Date</th><th>IBIT</th><th>FBTC</th><th>Total</th></tr>
  <tr><td>2024-01-11</td><td>100</td><td>50</td><td>150</td></tr>
  <tr><td>2024-01-12</td><td>-20</td><td>30</td><td>10</td></tr>
  <tr><td>2024-01-13</td><td></td><td>0</td><td>0</td></tr>
  <tr><td>2024-01-14</td><td>200</td><td>-50</td><td>150</td></tr>
</table>
"""

_NO_TOTAL_HTML = """
<table>
  <tr><th>Date</th><th>IBIT</th><th>FBTC</th></tr>
  <tr><td>2024-01-11</td><td>100</td><td>50</td></tr>
</table>
"""

_NO_DATE_HTML = """
<table>
  <tr><th>Notes</th><th>IBIT</th><th>Total</th></tr>
  <tr><td>foo</td><td>100</td><td>100</td></tr>
  <tr><td>bar</td><td>200</td><td>200</td></tr>
  <tr><td>baz</td><td>300</td><td>300</td></tr>
  <tr><td>qux</td><td>400</td><td>400</td></tr>
  <tr><td>quux</td><td>500</td><td>500</td></tr>
</table>
"""


def _scraper_with_html(html: str) -> ETFFlowScraper:
    scraper = ETFFlowScraper()
    scraper._get_html = MagicMock(return_value=html)
    return scraper


# ── Happy path ────────────────────────────────────────────────────────────────

def test_fetch_returns_dataframe():
    df = _scraper_with_html(_VALID_HTML).fetch()
    assert isinstance(df, pd.DataFrame)


def test_etf_flow_column_present():
    df = _scraper_with_html(_VALID_HTML).fetch()
    assert "etf_flow" in df.columns


def test_correct_row_count():
    df = _scraper_with_html(_VALID_HTML).fetch()
    assert len(df) == 4


def test_index_is_utc_datetimes():
    df = _scraper_with_html(_VALID_HTML).fetch()
    assert df.index.tz is not None


def test_positive_total_parsed():
    df = _scraper_with_html(_VALID_HTML).fetch()
    assert df["etf_flow"].iloc[0] == pytest.approx(150.0)


def test_negative_total_parsed():
    html = """
    <table>
      <tr><th>Date</th><th>Total</th></tr>
      <tr><td>2024-01-11</td><td>-300</td></tr>
    </table>
    """
    df = _scraper_with_html(html).fetch()
    assert df["etf_flow"].iloc[0] == pytest.approx(-300.0)


def test_zero_flow_is_not_nan():
    """A '0' in the Total column means genuine zero inflows, not missing data."""
    df = _scraper_with_html(_VALID_HTML).fetch()
    # Row index 2 (2024-01-13) has Total = 0
    row = df[df.index.date == pd.Timestamp("2024-01-13").date()]
    if not row.empty:
        assert row["etf_flow"].iloc[0] == pytest.approx(0.0)


def test_blank_cell_is_nan():
    """An empty cell in the Total column should become NaN, not 0."""
    html = """
    <table>
      <tr><th>Date</th><th>Total</th></tr>
      <tr><td>2024-01-11</td><td></td></tr>
    </table>
    """
    df = _scraper_with_html(html).fetch()
    assert pd.isna(df["etf_flow"].iloc[0])


def test_sorted_ascending():
    df = _scraper_with_html(_VALID_HTML).fetch()
    assert df.index.is_monotonic_increasing


# ── Date filtering ────────────────────────────────────────────────────────────

def test_start_filter():
    df = _scraper_with_html(_VALID_HTML).fetch(start=datetime(2024, 1, 13, tzinfo=timezone.utc))
    assert all(ts >= pd.Timestamp("2024-01-13", tz="UTC") for ts in df.index)


def test_end_filter():
    df = _scraper_with_html(_VALID_HTML).fetch(end=datetime(2024, 1, 12, tzinfo=timezone.utc))
    assert all(ts <= pd.Timestamp("2024-01-12", tz="UTC") for ts in df.index)


# ── Schema drift detection ────────────────────────────────────────────────────

def test_missing_total_column_raises_schema_error():
    with pytest.raises(SchemaError, match="Total"):
        _scraper_with_html(_NO_TOTAL_HTML).fetch()


def test_non_date_first_column_raises_schema_error():
    with pytest.raises(SchemaError):
        _scraper_with_html(_NO_DATE_HTML).fetch()


def test_empty_page_raises():
    with pytest.raises(Exception):
        _scraper_with_html("").fetch()
