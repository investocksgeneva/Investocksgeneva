"""Local (Mac) run support: notifier command, HTML report, holiday state file."""
from datetime import datetime

import pandas as pd

from hybrid_scanner.main import main
from hybrid_scanner.models import ScanReport
from hybrid_scanner.notifiers import MacNotifier
from hybrid_scanner.report import summarize_for_notification, write_html_report
from hybrid_scanner.tests.test_notifiers import _signal


def test_mac_notifier_passes_text_as_arguments(monkeypatch):
    monkeypatch.setattr("hybrid_scanner.notifiers.shutil.which", lambda name: None)
    calls = []
    n = MacNotifier('Scan "today"', "2 signal(s): PANW, APH", "Watch: NVDA", runner=lambda cmd, **kw: calls.append(cmd),
                    platform="darwin")
    n.send([])
    cmd = calls[0]
    assert cmd[0] == "osascript" and n.ok
    # User text arrives only as trailing argv items — never inside the -e script source.
    script = " ".join(cmd[1:cmd.index("end run") + 1])
    assert "PANW" not in script and '"today"' not in script
    assert cmd[-3:] == ["2 signal(s): PANW, APH", 'Scan "today"', "Watch: NVDA"]


def test_mac_notifier_uses_terminal_notifier_with_report_link(monkeypatch, tmp_path):
    monkeypatch.setattr("hybrid_scanner.notifiers.shutil.which", lambda name: "/opt/homebrew/bin/terminal-notifier")
    calls = []
    report = tmp_path / "report.html"
    n = MacNotifier("T", "M", "S", open_path=report, runner=lambda cmd, **kw: calls.append(cmd), platform="darwin")
    n.send([])
    assert "-open" in calls[0] and calls[0][calls[0].index("-open") + 1] == report.resolve().as_uri()


def test_mac_notifier_failure_is_counted(monkeypatch):
    monkeypatch.setattr("hybrid_scanner.notifiers.shutil.which", lambda name: None)

    def boom(cmd, **kw):
        raise FileNotFoundError("osascript")

    n = MacNotifier("T", "M", runner=boom, platform="darwin")
    n.send([])
    assert not n.ok


def test_mac_notifier_noop_off_macos():
    calls = []
    n = MacNotifier("T", "M", runner=lambda cmd, **kw: calls.append(cmd), platform="linux")
    n.send([])
    assert calls == [] and n.ok


def _report(**kw):
    return ScanReport(as_of=datetime(2026, 10, 9), signals=[], momentum_candidates=[], rejections=[], **kw)


def test_html_report_contents_and_escaping(tmp_path):
    sig = _signal("PANW")
    sig.reason = "<script>alert(1)</script>"
    path = write_html_report(tmp_path / "r.html", _report(errors={"CDNS": "no data"}), [sig],
                             title="Hybrid scan", n_tickers=503)
    html = path.read_text()
    assert "Hybrid scan — 2026-10-09" in html and "PANW" in html and "Entry <b>100.00</b>" in html
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html
    assert "Failed to load:</b> CDNS" in html
    assert "prefers-color-scheme: dark" in html  # follows system appearance


def test_html_report_without_signals(tmp_path):
    html = write_html_report(tmp_path / "r.html", _report(), [], title="Scan", n_tickers=10).read_text()
    assert "No new entry signals" in html


def test_notification_summary():
    msg, sub = summarize_for_notification(_report(), [_signal("PANW"), _signal("APH")])
    assert msg == "2 signal(s): PANW, APH" and "momentum candidates" in sub
    msg, _ = summarize_for_notification(_report(), [])
    assert msg == "No new entry signals"


def test_cli_output_dir_report_and_holiday_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    args = ["--source", "synthetic", "--alert-window", "60", "--export", "--plot", "--notify", "macos",
            "--output-dir", "out/day1", "--report", "out/day1/report.html", "--state-file", "state.txt"]
    assert main(args) == 0
    assert (tmp_path / "out/day1/report.html").exists()
    assert (tmp_path / "out/day1/signals.csv").exists()
    assert list((tmp_path / "out/day1/plots").glob("*.png"))
    assert pd.Timestamp((tmp_path / "state.txt").read_text())  # last reported bar recorded
    # Same data again (= market holiday): quiet exit, nothing written.
    args2 = [a.replace("day1", "day2") for a in args]
    assert main(args2) == 0
    assert not (tmp_path / "out/day2").exists()
