from datetime import datetime

import pandas as pd
import pytest

from hybrid_scanner.main import main
from hybrid_scanner.models import ScanReport
from hybrid_scanner.report import write_html_report
from hybrid_scanner.tests.test_notifiers import _signal
from hybrid_scanner.tracking import track_signal, track_signals


def _df(rows, start="2026-10-01"):
    """rows: (high, low, close) after an initial signal bar at index 0."""
    idx = pd.date_range(start, periods=len(rows), freq="B")
    return pd.DataFrame({"open": [r[2] for r in rows], "high": [r[0] for r in rows],
                         "low": [r[1] for r in rows], "close": [r[2] for r in rows], "volume": 1.0}, index=idx)


def _sig():  # entry 100, stop 96, target 108 (risk 4) on 2026-10-01
    return _signal("NVDA", day=1)


def test_still_valid_near_entry():
    t = track_signal(_sig(), _df([(101, 99, 100), (101, 98, 100.5), (102, 99, 101)]))
    assert t.status == "valid" and t.r_now == pytest.approx(0.25) and t.bars_since == 2


def test_extended_above_entry():
    t = track_signal(_sig(), _df([(101, 99, 100), (104, 100, 103.5)]))
    assert t.status == "extended" and t.r_now == pytest.approx(0.875)


def test_target_hit_records_date_and_r():
    t = track_signal(_sig(), _df([(101, 99, 100), (105, 100, 104), (109, 103, 107)]))
    assert t.status == "target" and t.r_now == pytest.approx(2.0)
    assert t.event_date == pd.Timestamp("2026-10-05")


def test_stopped_out():
    t = track_signal(_sig(), _df([(101, 99, 100), (100, 95, 95.5)]))
    assert t.status == "stopped" and t.r_now == pytest.approx(-1.0)


def test_stop_and_target_same_bar_counts_as_stop():
    t = track_signal(_sig(), _df([(101, 99, 100), (110, 95, 105)]))
    assert t.status == "stopped"


def test_unknown_signal_bar_skipped_and_sorted_newest_first():
    df = _df([(101, 99, 100)] * 5)
    older, newer = _signal("NVDA", day=1), _signal("NVDA", day=2)
    missing = _signal("NVDA", day=4)  # a Sunday: not a bar
    out = track_signals([older, missing, newer], {"NVDA": df})
    assert [o.signal.timestamp.day for o in out] == [2, 1]


def test_report_section(tmp_path):
    t = track_signal(_sig(), _df([(101, 99, 100), (100, 95, 95.5)]))
    report = ScanReport(as_of=datetime(2026, 10, 5), signals=[], momentum_candidates=[], rejections=[])
    html = write_html_report(tmp_path / "r.html", report, [], title="Scan", n_tickers=1,
                             recent=[t], recent_window=5).read_text()
    assert "Recent signals — last 5 trading days" in html and "Stopped out" in html and "-1.00R" in html
    empty = write_html_report(tmp_path / "e.html", report, [], title="Scan", n_tickers=1,
                              recent=[], recent_window=5).read_text()
    assert "No signals in that period" in empty
    off = write_html_report(tmp_path / "o.html", report, [], title="Scan", n_tickers=1).read_text()
    assert "Recent signals" not in off


def test_cli_track_excludes_todays_signals(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["--source", "synthetic", "--universe", "sp500", "--track", "5",
                 "--report", "r.html"]) == 0
    out = capsys.readouterr().out
    assert "Recent signals — last 5 trading days" in out
    html = (tmp_path / "r.html").read_text()
    assert "Recent signals — last 5 trading days" in html
