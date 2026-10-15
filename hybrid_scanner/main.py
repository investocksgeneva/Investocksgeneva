"""
Hybrid Momentum + Pullback scanner — CLI runner and worked example.

Quick start (from the repository root)::

    # Offline demo on deterministic synthetic data — no network needed
    python -m hybrid_scanner.main --source synthetic --recent 20 --backtest

    # Portfolio-level backtest (shared capital, position & heat limits)
    python -m hybrid_scanner.main --source synthetic --portfolio --plot \\
        --set backtest.max_positions=5 --set backtest.signal_priority=tightest_stop

    # Real data (yfinance), default watchlist, today's signals
    python -m hybrid_scanner.main

    # Hourly chart, custom tickers, half-percent risk, tighter 52w filter
    python -m hybrid_scanner.main --timeframe 1h --tickers NVDA AVGO META \\
        --risk 0.005 --set momentum.high_proximity.max_distance_pct=0.15

    # Full universe from a constituents CSV, export + plots
    python -m hybrid_scanner.main --watchlist sp500.csv --export --plot

Parameters can be changed three ways — pick whichever suits the workflow:
  1. ``--set dotted.path=value`` on the command line (repeatable);
  2. ``--config my_params.json`` (dump defaults with ``--dump-config``);
  3. in code — see :func:`example_parameter_tuning`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from .backtest import simulate, summarize
from .config import DEFAULT_WATCHLIST, ScannerConfig
from .models import EntrySignal, ScanReport
from .notifiers import ConsoleNotifier, CSVExporter, DiscordNotifier, MacNotifier, TelegramNotifier, export_rejections
from .signal_generator import HybridSignalGenerator, rejections_frame, signals_frame
from .utils import drop_incomplete_daily_bar, get_logger, load_universe, make_provider, read_watchlist


# --------------------------------------------------------------------------- #
# Example: tuning parameters in code
# --------------------------------------------------------------------------- #
def example_parameter_tuning() -> ScannerConfig:
    """Three equivalent ways to customise the scanner in Python."""
    # (a) Start from a timeframe preset
    cfg = ScannerConfig.for_timeframe("1d")

    # (b) Mutate nested dataclasses directly — explicit and IDE-completable
    cfg.momentum.trend.mode = "either"               # SMA template OR 8/21/50 EMA stack
    cfg.momentum.high_proximity.max_distance_pct = 0.20
    cfg.pullback.ma_type = "sma"                      # pull back to the 10-SMA instead
    cfg.pullback.ma_period = 10
    cfg.confirmation.triggers = ("bullish_engulfing", "close_above_ma", "rsi_bounce")
    cfg.confirmation.min_triggers = 2                 # demand two confirmations

    # (c) Dotted overrides — ideal for grid searches / optimisers
    cfg = cfg.with_overrides({
        "risk.risk_per_trade_pct": 0.005,
        "risk.stop_method": "tighter",                # min(structure, 1.5 ATR) distance
        "risk.target_r_multiple": 3.0,
        "momentum.oscillators.adx_enabled": True,
    })
    return cfg.validate()


# --------------------------------------------------------------------------- #
# Output formatting
# --------------------------------------------------------------------------- #
def _print_header(title: str) -> None:
    print(f"\n{title}\n{'─' * len(title)}")


def print_report(report: ScanReport, show_rejections: bool = False) -> None:
    _print_header(f"Momentum candidates as of {report.as_of}  ({len(report.momentum_candidates)})")
    if report.momentum_candidates:
        rows = [{"ticker": r.ticker, **{k: v for k, v in r.metrics.items()}} for r in report.momentum_candidates]
        print(_fmt(pd.DataFrame(rows).set_index("ticker")))
    else:
        print("  none")

    _print_header(f"Pending pullback setups — awaiting trigger  ({len(report.pending_setups)})")
    for s in report.pending_setups:
        m = s.metrics
        print(f"  {s.ticker:<6} depth {m.get('depth_pct', 0):.1%}  {m.get('pullback_bars')} bars  "
              f"swing high {s.swing_high:.2f}  pullback low {s.pullback_low:.2f}  MA {s.ma_value:.2f}")
    if not report.pending_setups:
        print("  none")

    print_signals(report.signals, f"ENTRY SIGNALS  ({len(report.signals)})")

    _print_header("Rejections by stage / check")
    rej = rejections_frame(report)
    if rej.empty:
        print("  none")
    else:
        print(rej.groupby(["stage", "check"]).size().rename("count").to_string())
        if show_rejections:
            _print_header("Rejection detail")
            for r in report.rejections:
                print(f"  {r.ticker:<6} [{r.stage}] " + " | ".join(r.rejection_reasons))
    if report.errors:
        _print_header("Data errors")
        for t, e in report.errors.items():
            print(f"  {t}: {e}")
    if report.short_history:
        _print_header(f"Skipped — insufficient history ({len(report.short_history)})")
        for t, e in report.short_history.items():
            print(f"  {t}: {e}")


def print_signals(signals: list[EntrySignal], title: str) -> None:
    _print_header(title)
    if not signals:
        print("  none")
        return
    df = signals_frame(signals)
    cols = ["ticker", "timestamp", "entry_price", "stop_loss", "target_price", "risk_per_share",
            "shares", "dollar_risk", "r_multiple_target", "rr_to_swing_high", "stop_atr_multiple"]
    print(_fmt(df[cols].rename(columns={
        "entry_price": "entry", "stop_loss": "stop", "target_price": "target", "risk_per_share": "risk/sh",
        "r_multiple_target": "R", "rr_to_swing_high": "R→high", "stop_atr_multiple": "stop_ATR"})))
    print()
    for s in signals:
        print(f"  • {s.ticker} {s.timestamp:%Y-%m-%d %H:%M}: {s.setup_type}\n      {s.reason}")


def _fmt(df: pd.DataFrame) -> str:
    with pd.option_context("display.width", 200, "display.max_columns", 30, "display.float_format", "{:,.3f}".format):
        return df.to_string()


def signals_in_window(history: dict[str, list[EntrySignal]], prepared: dict, n_bars: int) -> list[EntrySignal]:
    """Signals whose bar is among each ticker's last ``n_bars`` bars, newest first."""
    out = []
    for t, sigs in history.items():
        idx = prepared[t].df.index
        cutoff = len(idx) - n_bars
        out.extend(s for s in sigs if idx.searchsorted(pd.Timestamp(s.timestamp)) >= cutoff)
    return sorted(out, key=lambda s: s.timestamp, reverse=True)


def _dedupe(signals: list[EntrySignal]) -> list[EntrySignal]:
    seen: set[tuple[str, object]] = set()
    out = []
    for s in signals:
        key = (s.ticker, s.timestamp)
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out


def alert_header(report: ScanReport, signals: list[EntrySignal], window: int, title: str, n_tickers: int) -> str:
    """One-glance summary that leads every alert batch — posted even when
    there are no signals, so a silent channel means a broken job, not a quiet week."""
    as_of = pd.Timestamp(report.as_of).strftime("%Y-%m-%d") if report.as_of is not None else "n/a"
    span = "latest bar" if window <= 1 else f"last {window} bars"
    lines = [
        f"**{title} — {as_of}**",
        f"{n_tickers} tickers scanned · {len(report.momentum_candidates)} momentum candidates · "
        f"{len(report.pending_setups)} pending setups · **{len(signals)} signal(s)** ({span})",
    ]
    if report.pending_setups:
        names = ", ".join(sorted(p.ticker for p in report.pending_setups)[:20])
        lines.append(f"Watch (pullback set up, awaiting trigger): {names}")
    if report.errors:
        names = ", ".join(sorted(report.errors)[:10])
        lines.append(f"⚠️ {len(report.errors)} ticker(s) failed to load: {names}")
    if report.short_history:
        names = ", ".join(sorted(report.short_history)[:10])
        more = f" +{len(report.short_history) - 10} more" if len(report.short_history) > 10 else ""
        lines.append(f"Skipped (new listings, not enough history yet): {names}{more}")
    if signals:
        lines.append("_Levels are as of each signal's bar — re-check price before acting. Not investment advice._")
    else:
        lines.append("No new entry signals.")
    return "\n".join(lines)


def run_portfolio_backtest(gen, cfg, prepared, history, benchmark, export: bool, plot: bool):
    """Run and print the portfolio-level backtest; optionally export/plot."""
    from .portfolio import PortfolioBacktester

    start = min(p.df.index[min(gen.warmup_bars, len(p.df) - 1)] for p in prepared.values())
    res = PortfolioBacktester(cfg).run(prepared, history, benchmark, start)
    bt = cfg.backtest
    _print_header(f"Portfolio backtest  (max {bt.max_positions} positions, heat cap {bt.max_portfolio_heat_pct:.0%}, "
                  f"{cfg.risk.risk_per_trade_pct:.2%} risk/trade, priority={bt.signal_priority})")
    pct = {"total_return", "cagr", "ann_volatility", "max_drawdown", "time_in_market", "avg_gross_exposure",
           "avg_heat", "max_heat", "win_rate", "benchmark_total_return", "benchmark_cagr", "benchmark_max_drawdown"}
    for k, v in res.metrics.items():
        if isinstance(v, float) and k in pct:
            print(f"  {k:<26} {v:>10.2%}")
        elif isinstance(v, float):
            print(f"  {k:<26} {v:>10,.2f}")
        else:
            print(f"  {k:<26} {v:>10}")
    if not res.skipped.empty:
        print("  skipped signals by binding constraint:")
        for reason, n in res.skipped["reason"].value_counts().items():
            print(f"    {reason:<24} {n:>10}")
    if cfg.data.source == "synthetic":
        print("  (synthetic data — validates mechanics only, says nothing about real-market edge)")
    out = Path(cfg.output.signals_csv).parent
    if export:
        out.mkdir(parents=True, exist_ok=True)
        res.equity_curve.to_csv(out / "equity_curve.csv")
        res.trades.to_csv(out / "portfolio_trades.csv", index=False)
        res.skipped.to_csv(out / "portfolio_skipped.csv", index=False)
        gen.log.info("Wrote equity_curve.csv, portfolio_trades.csv, portfolio_skipped.csv to %s", out)
    if plot:
        from .plotting import plot_equity

        path = Path(cfg.output.plot_dir) / "portfolio_equity.png"
        plot_equity(res.equity_curve, benchmark["close"] if benchmark is not None else None, path=path,
                    title=f"Portfolio backtest — {len(prepared)} tickers, {cfg.data.timeframe}")
        gen.log.info("Saved %s", path)
    return res


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="hybrid_scanner", description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_argument_group("universe & data")
    g.add_argument("--tickers", nargs="*", help="tickers to scan (default: built-in watchlist)")
    g.add_argument("--watchlist", help="text file (one ticker per line) or CSV with a symbol column")
    g.add_argument("--timeframe", choices=["1d", "1h"], default="1d")
    g.add_argument("--source", choices=["yfinance", "csv", "synthetic"], default=None)
    g.add_argument("--csv-dir", help="directory for --source csv")
    g.add_argument("--benchmark", help="benchmark ticker (default SPY)")
    g.add_argument("--universe", choices=["sp500"], help="built-in universe (constituents CSV shipped in universes/)")
    g.add_argument("--period", help="history to load, e.g. 2y, 5y, max (yfinance period string)")
    g.add_argument("--refresh", action="store_true", help="ignore the local price cache and re-download")
    g.add_argument("--as-of", help="evaluate as of this date/time instead of the latest bar")

    g = ap.add_argument_group("parameters")
    g.add_argument("--config", help="JSON config file (see --dump-config)")
    g.add_argument("--set", action="append", default=[], metavar="PATH=VALUE",
                   help="override any parameter, e.g. --set pullback.ma_period=10")
    g.add_argument("--equity", type=float, help="account equity for sizing")
    g.add_argument("--risk", type=float, help="risk per trade as a fraction (0.01 = 1%%)")
    g.add_argument("--dump-config", metavar="PATH", help="write the effective config to JSON and exit")
    g.add_argument("--example-tuning", action="store_true", help="run with example_parameter_tuning() config")

    g = ap.add_argument_group("output")
    g.add_argument("--recent", type=int, default=0, metavar="N", help="also list signals fired in the last N bars")
    g.add_argument("--backtest", action="store_true", help="simulate all historical signals and summarise in R")
    g.add_argument("--portfolio", action="store_true",
                   help="portfolio-level backtest: shared capital, max positions, heat cap, equity curve")
    g.add_argument("--export", action="store_true", help="write signals and rejections CSVs")
    g.add_argument("--plot", action="store_true", help="save a PNG of each signal's setup")
    g.add_argument("--notify", nargs="*", choices=["console", "discord", "telegram", "macos"], default=[])
    g.add_argument("--live-alerts", action="store_true", help="actually POST webhooks (default: dry run)")
    g.add_argument("--alert-window", type=int, default=1, metavar="N",
                   help="alert/export signals from the last N bars, not just the latest (weekly job: 5)")
    g.add_argument("--alert-title", default="Hybrid scan", help="title line of the alert header")
    g.add_argument("--track", type=int, default=0, metavar="N",
                   help="follow up on signals from the previous N trading days (target hit, stopped, still valid…)")
    g.add_argument("--output-dir", metavar="DIR", help="write CSVs and charts here instead of ./output")
    g.add_argument("--report", metavar="PATH", help="write a self-contained HTML report (signals, charts, watch list)")
    g.add_argument("--state-file", metavar="PATH",
                   help="remember the last reported bar; if no new bar since (market holiday), exit quietly")
    g.add_argument("--show-rejections", action="store_true", help="print every rejection reason")
    g.add_argument("-v", "--verbose", action="store_true", help="debug logging (per-ticker decisions)")
    return ap


def build_config(args: argparse.Namespace) -> ScannerConfig:
    if args.example_tuning:
        cfg = example_parameter_tuning()
    elif args.config:
        cfg = ScannerConfig.from_json(args.config)
    else:
        cfg = ScannerConfig.for_timeframe(args.timeframe)
    overrides: dict[str, str] = {}
    if args.source:
        overrides["data.source"] = args.source
    if args.period:
        overrides["data.period"] = args.period
    if args.refresh:
        overrides["data.refresh_cache"] = "true"
    if args.csv_dir:
        overrides["data.csv_dir"] = args.csv_dir
    if args.benchmark:
        overrides["data.benchmark"] = args.benchmark
    if args.equity:
        overrides["risk.account_equity"] = str(args.equity)
    if args.risk:
        overrides["risk.risk_per_trade_pct"] = str(args.risk)
    if args.verbose:
        overrides["output.log_level"] = "DEBUG"
    if args.output_dir:
        out = Path(args.output_dir)
        overrides["output.signals_csv"] = str(out / "signals.csv")
        overrides["output.rejections_csv"] = str(out / "rejections.csv")
        overrides["output.plot_dir"] = str(out / "plots")
    for item in args.set:
        if "=" not in item:
            raise SystemExit(f"--set expects PATH=VALUE, got {item!r}")
        k, v = item.split("=", 1)
        overrides[k.strip()] = v.strip()
    return cfg.with_overrides(overrides).validate() if overrides else cfg.validate()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = build_config(args)
    except (ValueError, KeyError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    if args.dump_config:
        cfg.to_json(args.dump_config)
        print(f"Wrote config to {args.dump_config}")
        return 0
    log = get_logger(level=cfg.output.log_level)

    if args.universe:
        tickers = read_watchlist(Path(__file__).parent / "universes" / f"{args.universe}.csv")
    elif args.watchlist:
        tickers = read_watchlist(args.watchlist)
    else:
        tickers = args.tickers or list(DEFAULT_WATCHLIST)
    log.info("Universe: %d tickers", len(tickers))
    provider = make_provider(cfg.data)
    dc = cfg.data
    short_history: dict[str, str] = {}
    data, errors = load_universe(provider, tickers, dc.timeframe, dc.period, dc.min_bars, short_history)
    bench_data, _ = load_universe(provider, [dc.benchmark], dc.timeframe, dc.period)
    benchmark = bench_data.get(dc.benchmark.upper())
    if dc.drop_incomplete_bar and dc.timeframe == "1d" and dc.source != "synthetic":
        trimmed = {t: drop_incomplete_daily_bar(df) for t, df in data.items()}
        n_trimmed = sum(len(trimmed[t]) < len(data[t]) for t in data)
        if n_trimmed:
            log.info("US market still open: ignoring today's unfinished candle (%d tickers) — "
                     "signals use the last completed day", n_trimmed)
        data = trimmed
        if benchmark is not None:
            benchmark = drop_incomplete_daily_bar(benchmark)
    if benchmark is None:
        log.warning("Benchmark %s unavailable — RS falls back to universe rank", dc.benchmark)
    if not data:
        print("No usable data for any ticker. Check the source / network, or try --source synthetic.", file=sys.stderr)
        return 1

    gen = HybridSignalGenerator(cfg, log)
    prepared = gen.prepare_universe(data, benchmark)
    report = gen.scan(data, benchmark, as_of=args.as_of, prepared=prepared)
    report.errors.update(errors)
    report.short_history.update(short_history)

    # Holiday guard: no new bar since the last reported scan means no news.
    bar_key = pd.Timestamp(report.as_of).isoformat() if report.as_of is not None else ""
    state = Path(args.state_file) if args.state_file else None
    if state is not None and state.exists() and state.read_text().strip() == bar_key:
        print(f"No new market data since the last report ({bar_key}) — market holiday? Nothing to do.")
        return 0

    print_report(report, args.show_rejections)

    recent: list[EntrySignal] = []
    windowed: list[EntrySignal] = []
    history: dict[str, list[EntrySignal]] = {}
    if args.recent or args.backtest or args.portfolio or args.alert_window > 1 or args.track:
        for t, p in prepared.items():
            history[t] = gen.signal_history(p)
        if args.recent:
            recent = signals_in_window(history, prepared, args.recent)
            print_signals(recent, f"Signals fired in the last {args.recent} bars  ({len(recent)})")
        if args.alert_window > 1:
            windowed = signals_in_window(history, prepared, args.alert_window)

    if args.backtest:
        trades = pd.concat([simulate(prepared[t].df, s, cfg.backtest) for t, s in history.items() if s] or [pd.DataFrame()])
        _print_header("Backtest summary (R multiples; one position per ticker)")
        stats = summarize(trades) if not trades.empty else {"trades": 0}
        for k, v in stats.items():
            print(f"  {k:<24} {v:,.3f}" if isinstance(v, float) else f"  {k:<24} {v}")
        if dc.source == "synthetic":
            print("  (synthetic data — validates mechanics only, says nothing about real-market edge)")
        if not trades.empty and args.export:
            Path(cfg.output.signals_csv).parent.mkdir(parents=True, exist_ok=True)
            trades.to_csv(Path(cfg.output.signals_csv).with_name("trades.csv"), index=False)

    if args.portfolio:
        run_portfolio_backtest(gen, cfg, prepared, history, benchmark, args.export, args.plot)

    # Alerts cover the latest bar, or every bar in --alert-window (a weekly
    # job uses ~5 so Monday-Thursday signals aren't missed).
    to_alert = windowed if args.alert_window > 1 else report.signals
    if args.export:
        CSVExporter(cfg.output.signals_csv).send(_dedupe(to_alert + recent))
        export_rejections(rejections_frame(report), cfg.output.rejections_csv)
    plots: dict[tuple[str, object], Path] = {}
    if args.plot:
        from .plotting import plot_setup

        out = Path(cfg.output.plot_dir)
        for s in _dedupe(to_alert + recent):
            path = out / f"{s.ticker}_{s.timestamp:%Y%m%d_%H%M}.png"
            plot_setup(prepared[s.ticker], s, path=path)
            plots[(s.ticker, s.timestamp)] = path
            log.info("Saved %s", path)

    tracked = []
    if args.track:
        from .tracking import track_signals

        shown = {(s.ticker, s.timestamp) for s in to_alert}
        earlier = [s for s in signals_in_window(history, prepared, args.track + 1)
                   if (s.ticker, s.timestamp) not in shown]
        tracked = track_signals(earlier, {t: p.df for t, p in prepared.items()})
        _print_header(f"Recent signals — last {args.track} trading days  ({len(tracked)})")
        for r in tracked:
            print(f"  {r.signal.ticker:<6} {r.signal.timestamp:%Y-%m-%d}  entry {r.signal.entry_price:>9.2f}  "
                  f"now {r.last_close:>9.2f}  {r.r_now:+.2f}R  {r.label}")
        if not tracked:
            print("  none")

    report_path = None
    if args.report:
        from .report import write_html_report

        report_path = write_html_report(args.report, report, to_alert, title=args.alert_title,
                                        n_tickers=len(prepared), window=args.alert_window, plots=plots,
                                        recent=tracked, recent_window=args.track)
        log.info("Wrote report %s", report_path)

    dry = not args.live_alerts
    header = alert_header(report, to_alert, args.alert_window, args.alert_title, len(prepared))
    notifiers = []
    try:
        for name in args.notify:
            notifiers.append(_make_notifier(name, cfg, header, dry, report, to_alert, args.alert_title, report_path))
    except ValueError as exc:  # missing webhook credentials
        print(f"Alert configuration error: {exc}", file=sys.stderr)
        return 2
    for notifier in notifiers:
        notifier.send(to_alert)
    failed = [type(n).__name__ for n in notifiers if not getattr(n, "ok", True)]

    if failed:
        print(f"Alert delivery failed: {', '.join(failed)}", file=sys.stderr)
        return 3
    if state is not None:  # only after a fully successful run
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(bar_key)
    return 0


def _make_notifier(name, cfg, header, dry, report, signals, title, report_path):
    if name == "console":
        return ConsoleNotifier()
    if name == "discord":
        return DiscordNotifier(cfg.output.discord_webhook_env, header=header, dry_run=dry)
    if name == "telegram":
        return TelegramNotifier(cfg.output.telegram_token_env, cfg.output.telegram_chat_env, dry_run=dry)
    if name == "macos":
        from .report import summarize_for_notification

        message, subtitle = summarize_for_notification(report, signals)
        as_of = pd.Timestamp(report.as_of).strftime("%Y-%m-%d") if report.as_of is not None else ""
        return MacNotifier(f"{title} — {as_of}", message, subtitle, open_path=report_path)
    raise ValueError(f"unknown notifier {name!r}")


if __name__ == "__main__":
    raise SystemExit(main())
