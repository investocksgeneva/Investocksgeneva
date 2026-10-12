"""
Helpers: logging, data providers, validation, watchlists.

Data access is behind a tiny :class:`DataProvider` protocol. The scanner
never imports yfinance directly, so swapping in Polygon, Interactive Brokers,
Alpaca, or a TradingView webhook buffer means writing one class with a
``get_history`` method — nothing else changes.
"""

from __future__ import annotations

import logging
import sys
import zlib
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Iterable, Protocol, runtime_checkable

import numpy as np
import pandas as pd

from .config import DataConfig

REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")


# --------------------------------------------------------------------------- #
# Errors & logging
# --------------------------------------------------------------------------- #
class DataError(Exception):
    """Raised when market data is missing, malformed, or insufficient."""


def get_logger(name: str = "hybrid_scanner", level: str | int = "INFO") -> logging.Logger:
    """Idempotent logger setup (safe to call from notebooks repeatedly)."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%H:%M:%S"))
        logger.addHandler(handler)
        logger.propagate = False
    logger.setLevel(level)
    return logger


log = get_logger()


# --------------------------------------------------------------------------- #
# US market session
# --------------------------------------------------------------------------- #
NEW_YORK = ZoneInfo("America/New_York")
#: Daily bars are treated as final this long after the 16:00 ET close, giving
#: the data vendor time to publish the official closing prints.
DAILY_BAR_FINAL_AT = time(16, 30)


def _now_ny(now: datetime | None = None) -> datetime:
    now = now or datetime.now(tz=NEW_YORK)
    return now.astimezone(NEW_YORK) if now.tzinfo else now.replace(tzinfo=NEW_YORK)


def last_daily_close(now: datetime | None = None) -> datetime:
    """Most recent moment a US daily bar became final (16:30 ET), as an aware
    datetime. Weekends/holidays just point at an earlier, still-valid cutoff."""
    ny = _now_ny(now)
    cutoff = ny.replace(hour=DAILY_BAR_FINAL_AT.hour, minute=DAILY_BAR_FINAL_AT.minute, second=0, microsecond=0)
    return cutoff if ny >= cutoff else cutoff - timedelta(days=1)


def drop_incomplete_daily_bar(df: pd.DataFrame, now: datetime | None = None) -> pd.DataFrame:
    """Drop today's still-forming daily bar while the US session is open.

    Yahoo serves a "today" daily bar from the first trade of the session. A
    hammer or engulfing candle read at 11:00 New York time can be gone by the
    close, so signals must only ever see completed bars — live and in
    backtests alike. Before 16:30 ET, a last bar dated today is removed.
    """
    if df.empty:
        return df
    ny = _now_ny(now)
    last = pd.Timestamp(df.index[-1])
    if last.date() == ny.date() and ny.time() < DAILY_BAR_FINAL_AT:
        return df.iloc[:-1]
    return df


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def normalize_ohlcv(df: pd.DataFrame, ticker: str = "?") -> pd.DataFrame:
    """Return a clean OHLCV frame: lowercase columns, sorted tz-naive index,
    no duplicate timestamps, no non-positive prices.

    Timezones are dropped (converted to exchange-local wall time first) so
    daily/weekly resampling aligns with trading sessions rather than UTC.
    """
    if df is None or df.empty:
        raise DataError(f"{ticker}: no data")
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):  # yfinance multi-ticker layout
        out.columns = out.columns.get_level_values(0)
    out.columns = [str(c).lower().replace(" ", "_") for c in out.columns]
    if "adj_close" in out.columns and "close" not in out.columns:
        out["close"] = out["adj_close"]
    missing = [c for c in REQUIRED_COLUMNS if c not in out.columns]
    if missing:
        raise DataError(f"{ticker}: missing columns {missing}")
    out = out[list(REQUIRED_COLUMNS)]

    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index)
    if out.index.tz is not None:
        out.index = out.index.tz_localize(None)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out = out.apply(pd.to_numeric, errors="coerce").dropna(subset=["open", "high", "low", "close"])
    out["volume"] = out["volume"].fillna(0.0)
    out = out[(out[["open", "high", "low", "close"]] > 0).all(axis=1)]
    # Repair occasional vendor glitches where high/low don't bracket open/close.
    out["high"] = out[["open", "high", "low", "close"]].max(axis=1)
    out["low"] = out[["open", "high", "low", "close"]].min(axis=1)
    if out.empty:
        raise DataError(f"{ticker}: no valid rows after cleaning")
    return out


def require_bars(df: pd.DataFrame, n: int, ticker: str = "?") -> None:
    if len(df) < n:
        raise DataError(f"{ticker}: {len(df)} bars < required {n}")


# --------------------------------------------------------------------------- #
# Providers
# --------------------------------------------------------------------------- #
@runtime_checkable
class DataProvider(Protocol):
    """Anything that can return normalized OHLCV history for a ticker."""

    def get_history(self, ticker: str, timeframe: str, period: str) -> pd.DataFrame: ...


class YFinanceProvider:
    """Yahoo Finance via ``yfinance`` (free, rate-limited, fine for EOD scans).

    Prices are split/dividend adjusted (``auto_adjust=True``), which is what
    you want for indicator continuity. Remember that Yahoo hourly history is
    limited to ~730 days.
    """

    def __init__(self, batch_size: int = 100, retry_failed: bool = True, download=None) -> None:
        if download is None:
            try:
                import yfinance as yf
            except ImportError as exc:  # pragma: no cover - environment specific
                raise ImportError("pip install yfinance  — or use --source csv/synthetic") from exc
            download = yf.download
        self.batch_size = batch_size
        self.retry_failed = retry_failed
        #: Injectable for tests; defaults to ``yfinance.download``.
        self._download = download

    def get_history(self, ticker: str, timeframe: str, period: str) -> pd.DataFrame:
        return self.get_many([ticker], timeframe, period)[ticker]

    def get_many(self, tickers: Iterable[str], timeframe: str, period: str) -> dict[str, pd.DataFrame]:
        """Batched, threaded download — dramatically faster than per-ticker
        calls for a full-universe scan.

        Tickers that fail are retried once **without threads**. yfinance's
        threaded downloads share an on-disk SQLite timezone cache, and
        concurrent writers intermittently fail with ``database is locked`` —
        dropping a random ticker or two per run. Serial retry removes the
        contention; tickers that are genuinely unavailable fail again cheaply.
        """
        tickers = list(dict.fromkeys(tickers))
        result: dict[str, pd.DataFrame] = {}
        for i in range(0, len(tickers), self.batch_size):
            batch = tickers[i : i + self.batch_size]
            result.update(self._fetch(batch, timeframe, period, threads=True, quiet=self.retry_failed))
        missing = [t for t in tickers if t not in result]
        if missing and self.retry_failed:
            log.info("yfinance: retrying %d failed ticker(s) serially: %s", len(missing), ", ".join(missing[:20]))
            recovered = self._fetch(missing, timeframe, period, threads=False, quiet=False)
            if recovered:
                log.info("yfinance: recovered %d on retry", len(recovered))
            result.update(recovered)
        return result

    def _fetch(self, batch: list[str], timeframe: str, period: str, threads: bool, quiet: bool) -> dict[str, pd.DataFrame]:
        out: dict[str, pd.DataFrame] = {}
        try:
            raw = self._download(
                batch, period=period, interval=timeframe, auto_adjust=True,
                group_by="ticker", progress=False, threads=threads,
            )
        except Exception as exc:  # network / vendor errors: report, don't abort the universe
            log.warning("yfinance: batch download failed: %s", exc)
            return out
        if raw is None or raw.empty:
            return out
        for t in batch:
            try:
                multi = isinstance(raw.columns, pd.MultiIndex)
                if multi and t not in raw.columns.get_level_values(0):
                    raise DataError(f"{t}: no data")
                frame = raw[t] if multi else raw
                out[t] = normalize_ohlcv(frame.dropna(how="all"), t)
            except (DataError, KeyError) as exc:
                # First pass failures will be retried; only log the final outcome.
                (log.debug if quiet else log.warning)("yfinance: %s", exc)
        return out


class CSVProvider:
    """Reads ``{csv_dir}/{TICKER}.csv`` (or ``{TICKER}_{timeframe}.csv``).

    Expected columns: a date/datetime column (first column or named
    ``date``/``datetime``/``timestamp``) plus OHLCV. Handy for vendor exports
    and for reproducible research snapshots.
    """

    def __init__(self, csv_dir: str | Path) -> None:
        self.dir = Path(csv_dir)

    def get_history(self, ticker: str, timeframe: str, period: str = "") -> pd.DataFrame:
        for name in (f"{ticker}_{timeframe}.csv", f"{ticker}.csv"):
            path = self.dir / name
            if path.exists():
                df = pd.read_csv(path)
                date_col = next((c for c in df.columns if c.lower() in {"date", "datetime", "timestamp", "time"}), df.columns[0])
                df = df.set_index(pd.to_datetime(df.pop(date_col)))
                return normalize_ohlcv(df, ticker)
        raise DataError(f"{ticker}: no CSV found in {self.dir}")


class SyntheticProvider:
    """Deterministic synthetic OHLCV for offline demos and tests.

    Each ticker gets a reproducible random walk (seeded from its name) made of
    alternating *impulse* legs (positive drift, heavier volume) and
    *pullback* legs (negative drift, lighter volume) — the exact rhythm the
    strategy is designed to trade. Drift varies by ticker, so the universe
    naturally contains leaders and laggards.

    This is a plumbing fixture, **not** evidence of edge: any backtest result
    on synthetic data says nothing about real markets.
    """

    def __init__(self, n_bars: int = 600, end: str | pd.Timestamp | None = None, seed_offset: int = 0) -> None:
        self.n_bars = n_bars
        self.end = pd.Timestamp(end) if end is not None else pd.Timestamp("2026-10-09")
        self.seed_offset = seed_offset

    def get_history(self, ticker: str, timeframe: str = "1d", period: str = "") -> pd.DataFrame:
        rng = np.random.default_rng(zlib.crc32(ticker.encode()) + self.seed_offset)
        n = self.n_bars
        is_bench = ticker.upper() in {"SPY", "QQQ", "IWM"}
        # Per-ticker character: trend strength and volatility.
        trend = 0.0004 if is_bench else rng.uniform(-0.0008, 0.0022)
        vol = 0.010 if is_bench else rng.uniform(0.014, 0.026)

        rets = np.empty(n)
        vol_mult = np.empty(n)
        i = 0
        while i < n:
            up_len = int(rng.integers(10, 26))
            dn_len = int(rng.integers(4, 11))
            rets[i : i + up_len] = rng.normal(trend + 0.6 * vol * 0.25, vol, size=min(up_len, n - i))
            vol_mult[i : i + up_len] = rng.uniform(1.05, 1.5)
            i += up_len
            if i >= n:
                break
            rets[i : i + dn_len] = rng.normal(trend - 0.7 * vol * 0.4, vol * 0.8, size=min(dn_len, n - i))
            vol_mult[i : i + dn_len] = rng.uniform(0.55, 0.85)
            i += dn_len

        close = 50.0 * rng.uniform(0.6, 3.0) * np.exp(np.cumsum(rets))
        open_ = np.r_[close[0], close[:-1]] * (1 + rng.normal(0, vol * 0.25, n))
        span = np.abs(rng.normal(0, vol * 0.6, (2, n)))
        high = np.maximum(open_, close) * (1 + span[0])
        low = np.minimum(open_, close) * (1 - span[1])
        base_vol = 3e7 if is_bench else rng.uniform(1.5e6, 2e7)
        volume = base_vol * vol_mult * rng.lognormal(0, 0.25, n)

        freq = "h" if timeframe == "1h" else "B"
        idx = pd.date_range(end=self.end, periods=n, freq=freq)
        df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=idx)
        return normalize_ohlcv(df, ticker)


class CachedProvider:
    """Disk cache in front of any provider.

    For a 500-name universe this turns a multi-minute, rate-limited download
    into a sub-second load on repeat runs, and freezes the exact data a
    result was produced from (reproducibility). Files older than
    ``max_age_hours`` are refetched; ``refresh=True`` forces a refetch.
    """

    def __init__(self, inner: DataProvider, cache_dir: str | Path, max_age_hours: float = 12.0,
                 refresh: bool = False) -> None:
        self.inner = inner
        self.dir = Path(cache_dir)
        self.max_age_s = max_age_hours * 3600.0
        self.refresh = refresh

    def _path(self, ticker: str, timeframe: str, period: str) -> Path:
        return self.dir / f"{ticker}_{timeframe}_{period}.csv"

    def _load(self, path: Path) -> pd.DataFrame | None:
        import time as _time

        if self.refresh or not path.exists():
            return None
        mtime = path.stat().st_mtime
        if _time.time() - mtime > self.max_age_s:
            return None
        # A file saved before the latest US close may hold a still-forming
        # bar from mid-session; refetch so the final close is used.
        if mtime < last_daily_close().timestamp():
            return None
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        return normalize_ohlcv(df, path.stem)

    def _store(self, path: Path, df: pd.DataFrame) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(path)

    def get_history(self, ticker: str, timeframe: str, period: str) -> pd.DataFrame:
        return self.get_many([ticker], timeframe, period)[ticker]

    def get_many(self, tickers: Iterable[str], timeframe: str, period: str) -> dict[str, pd.DataFrame]:
        out: dict[str, pd.DataFrame] = {}
        missing: list[str] = []
        for t in tickers:
            cached = self._load(self._path(t, timeframe, period))
            if cached is None:
                missing.append(t)
            else:
                out[t] = cached
        if missing:
            log.info("cache: %d hits, fetching %d from %s", len(out), len(missing), type(self.inner).__name__)
            if hasattr(self.inner, "get_many"):
                fetched = self.inner.get_many(missing, timeframe, period)  # type: ignore[attr-defined]
            else:
                fetched = {}
                for t in missing:
                    try:
                        fetched[t] = self.inner.get_history(t, timeframe, period)
                    except Exception as exc:
                        log.warning("fetch: %s — %s", t, exc)
            for t, df in fetched.items():
                self._store(self._path(t, timeframe, period), df)
                out[t] = df
        return out


def make_provider(cfg: DataConfig) -> DataProvider:
    if cfg.source == "yfinance":
        inner: DataProvider = YFinanceProvider()
    elif cfg.source == "csv":
        return CSVProvider(cfg.csv_dir)
    elif cfg.source == "synthetic":
        return SyntheticProvider()
    else:
        raise ValueError(f"Unknown data source {cfg.source!r}")
    if cfg.cache_dir:
        return CachedProvider(inner, cfg.cache_dir, cfg.cache_max_age_hours, cfg.refresh_cache)
    return inner


def load_universe(
    provider: DataProvider,
    tickers: Iterable[str],
    timeframe: str,
    period: str,
    min_bars: int = 0,
    short_history: dict[str, str] | None = None,
) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    """Fetch many tickers; return ``(data, errors)`` instead of raising, so a
    single bad symbol never aborts a 3,000-name scan.

    Tickers with fewer than ``min_bars`` bars are excluded either way. Pass a
    ``short_history`` dict to have them recorded there instead of in
    ``errors``: a recent IPO or spin-off lacking 52 weeks of history is
    expected, not a data failure, and lumping the two together trains users
    to ignore the error count.
    """
    tickers = list(dict.fromkeys(t.strip().upper() for t in tickers if t.strip()))
    data: dict[str, pd.DataFrame] = {}
    errors: dict[str, str] = {}
    if hasattr(provider, "get_many"):
        data = provider.get_many(tickers, timeframe, period)  # type: ignore[attr-defined]
        errors.update({t: "no data returned" for t in tickers if t not in data})
    else:
        for t in tickers:
            try:
                data[t] = provider.get_history(t, timeframe, period)
            except Exception as exc:  # provider errors are heterogeneous
                errors[t] = str(exc)
    short_sink = short_history if short_history is not None else errors
    for t in list(data):
        if len(data[t]) < min_bars:
            short_sink[t] = f"{len(data[t])} bars < required {min_bars}"
            del data[t]
    for t, e in errors.items():
        log.warning("data: %s — %s", t, e)
    if short_history:
        log.info("data: %d ticker(s) skipped for insufficient history (new listings/spin-offs): %s",
                 len(short_history), ", ".join(sorted(short_history)))
    return data, errors


def read_watchlist(path: str | Path) -> list[str]:
    """One ticker per line (or comma separated); ``#`` starts a comment.

    A CSV with a ``symbol``/``ticker`` column (e.g. an S&P 500 constituents
    export) also works — that's the path to a full-universe scan.
    """
    path = Path(path)
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
        col = next((c for c in df.columns if c.lower() in {"symbol", "ticker"}), df.columns[0])
        return [str(s).strip().upper().replace(".", "-") for s in df[col].dropna()]
    out: list[str] = []
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0]
        out.extend(tok.strip().upper() for tok in line.replace(",", " ").split() if tok.strip())
    return out
