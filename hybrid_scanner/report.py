"""
Self-contained HTML scan report.

One file, no external assets: charts are embedded as base64 PNGs, styling is
inline, and it follows the system light/dark setting. Opens in any browser,
survives being emailed or archived, and needs no server.
"""

from __future__ import annotations

import base64
import html
from pathlib import Path
from typing import Iterable

import pandas as pd

from .models import EntrySignal, ScanReport

_CSS = """
:root { --bg:#fcfcfb; --fg:#0b0b0b; --muted:#52514e; --line:#e6e5e0; --card:#ffffff;
        --accent:#2a78d6; --good:#0ca30c; --bad:#d03b3b; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#1a1a19; --fg:#f0efec; --muted:#c3c2b7; --line:#383835; --card:#232322;
          --accent:#3987e5; --good:#3fbf3f; --bad:#e66767; } }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
       font:15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }
main { max-width:1100px; margin:0 auto; padding:24px 16px 64px; }
h1 { font-size:24px; margin:0 0 4px; } h2 { font-size:18px; margin:32px 0 8px; }
.sub { color:var(--muted); margin:0 0 16px; }
.kpis { display:flex; flex-wrap:wrap; gap:12px; margin:16px 0; }
.kpi { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:10px 14px; min-width:140px; }
.kpi b { display:block; font-size:22px; } .kpi span { color:var(--muted); font-size:13px; }
table { border-collapse:collapse; width:100%; font-size:14px; }
th, td { text-align:left; padding:6px 8px; border-bottom:1px solid var(--line); white-space:nowrap; }
th { color:var(--muted); font-weight:600; } td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; }
.scroll { overflow-x:auto; }
.card { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:16px; margin:16px 0; }
.card h3 { margin:0 0 4px; font-size:17px; } .card p { margin:4px 0; color:var(--muted); }
.levels { display:flex; flex-wrap:wrap; gap:16px; margin:8px 0; font-variant-numeric:tabular-nums; }
.stop { color:var(--bad); } .target { color:var(--good); }
img { max-width:100%; height:auto; border-radius:6px; margin-top:8px; }
.note { color:var(--muted); font-size:13px; }
.empty { color:var(--muted); font-style:italic; }
"""


def _e(x: object) -> str:
    return html.escape("" if x is None else str(x))


def _img(path: Path | None) -> str:
    if path is None or not Path(path).exists():
        return ""
    data = base64.b64encode(Path(path).read_bytes()).decode()
    return f'<img alt="setup chart" src="data:image/png;base64,{data}">'


def _fmt(v: object, spec: str = ",.2f") -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "–"
    return format(v, spec) if isinstance(v, (int, float)) else _e(v)


def write_html_report(
    path: str | Path,
    report: ScanReport,
    signals: list[EntrySignal],
    *,
    title: str,
    n_tickers: int,
    window: int = 1,
    plots: dict[tuple[str, object], Path] | None = None,
) -> Path:
    """Write the report and return its path."""
    plots = plots or {}
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    as_of = pd.Timestamp(report.as_of).strftime("%Y-%m-%d") if report.as_of is not None else "n/a"
    span = "latest bar" if window <= 1 else f"last {window} bars"

    parts: list[str] = [
        f"<h1>{_e(title)} — {as_of}</h1>",
        f'<p class="sub">Generated {pd.Timestamp.now():%Y-%m-%d %H:%M} · signals from the {span}</p>',
        '<div class="kpis">',
        f'<div class="kpi"><b>{n_tickers}</b><span>tickers scanned</span></div>',
        f'<div class="kpi"><b>{len(report.momentum_candidates)}</b><span>momentum candidates</span></div>',
        f'<div class="kpi"><b>{len(report.pending_setups)}</b><span>pending setups</span></div>',
        f'<div class="kpi"><b>{len(signals)}</b><span>entry signals</span></div>',
        "</div>",
        "<h2>Entry signals</h2>",
    ]
    if signals:
        parts.append('<p class="note">Levels are as of each signal\'s bar — re-check the live price before acting. '
                     "Not investment advice.</p>")
        for s in signals:
            rr = f" · {s.rr_to_swing_high:.2f}R to prior high" if s.rr_to_swing_high is not None else ""
            parts += [
                '<div class="card">',
                f"<h3>{_e(s.ticker)} — {_e(s.setup_type)}</h3>",
                f"<p>{s.timestamp:%Y-%m-%d} · {_e(s.reason)}</p>",
                '<div class="levels">',
                f"<span>Entry <b>{s.entry_price:,.2f}</b></span>",
                f'<span class="stop">Stop <b>{s.stop_loss:,.2f}</b></span>',
                f'<span class="target">Target <b>{s.target_price:,.2f}</b> ({s.r_multiple_target:.1f}R)</span>',
                f"<span>Risk/share {s.risk_per_share:,.2f} ({s.stop_atr_multiple:.2f} ATR)</span>",
                f"<span>Size <b>{s.shares}</b> sh · ${s.position_value:,.0f} · risk ${s.dollar_risk:,.0f}{rr}</span>",
                "</div>",
                _img(plots.get((s.ticker, s.timestamp))),
                "</div>",
            ]
    else:
        parts.append('<p class="empty">No new entry signals.</p>')

    parts.append("<h2>Watch list — pullback set up, awaiting a trigger</h2>")
    if report.pending_setups:
        rows = "".join(
            f"<tr><td>{_e(p.ticker)}</td><td class='num'>{_fmt(p.metrics.get('depth_pct'), '.1%')}</td>"
            f"<td class='num'>{_fmt(p.metrics.get('pullback_bars'), 'd')}</td>"
            f"<td class='num'>{_fmt(p.swing_high)}</td><td class='num'>{_fmt(p.pullback_low)}</td>"
            f"<td class='num'>{_fmt(p.ma_value)}</td></tr>"
            for p in report.pending_setups
        )
        parts.append('<div class="scroll"><table><tr><th>Ticker</th><th class="num">Depth</th><th class="num">Bars</th>'
                     '<th class="num">Swing high</th><th class="num">Pullback low</th><th class="num">MA</th></tr>'
                     f"{rows}</table></div>")
    else:
        parts.append('<p class="empty">None.</p>')

    parts.append("<h2>Momentum candidates</h2>")
    if report.momentum_candidates:
        cands = sorted(report.momentum_candidates, key=lambda r: -(r.metrics.get("rs_value") or 0))
        rows = "".join(
            f"<tr><td>{_e(c.ticker)}</td><td class='num'>{_fmt(c.metrics.get('rs_value'), '.0f')}</td>"
            f"<td class='num'>{_fmt(c.metrics.get('pct_from_high'), '.1%')}</td>"
            f"<td class='num'>{_fmt(c.metrics.get('recent_return'), '.1%')}</td>"
            f"<td class='num'>{_fmt(c.metrics.get('atr_ratio'), '.2f')}</td></tr>"
            for c in cands
        )
        parts.append('<div class="scroll"><table><tr><th>Ticker</th><th class="num">RS</th>'
                     '<th class="num">Off 52w high</th><th class="num">Recent move</th>'
                     f'<th class="num">ATR ratio</th></tr>{rows}</table></div>')
    else:
        parts.append('<p class="empty">None.</p>')

    issues: list[str] = []
    if report.errors:
        issues.append("<p><b>Failed to load:</b> " + _e(", ".join(sorted(report.errors))) + "</p>")
    if report.short_history:
        issues.append("<p><b>Skipped (new listings, not enough history):</b> "
                      + _e(", ".join(sorted(report.short_history))) + "</p>")
    if issues:
        parts += ["<h2>Data notes</h2>", *issues]

    doc = ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
           "<meta name='viewport' content='width=device-width, initial-scale=1'>"
           f"<title>{_e(title)} {as_of}</title><style>{_CSS}</style></head>"
           f"<body><main>{''.join(parts)}</main></body></html>")
    path.write_text(doc, encoding="utf-8")
    return path


def summarize_for_notification(report: ScanReport, signals: Iterable[EntrySignal]) -> tuple[str, str]:
    """(message, subtitle) for a desktop notification — short by design."""
    sigs = list(signals)
    if sigs:
        names = ", ".join(dict.fromkeys(s.ticker for s in sigs))
        message = f"{len(sigs)} signal(s): {names}"
    else:
        message = "No new entry signals"
    watch = ", ".join(sorted(p.ticker for p in report.pending_setups)[:6])
    subtitle = f"Watch: {watch}" if watch else f"{len(report.momentum_candidates)} momentum candidates"
    if report.errors:
        subtitle += f" · ⚠️ {len(report.errors)} failed to load"
    return message, subtitle
