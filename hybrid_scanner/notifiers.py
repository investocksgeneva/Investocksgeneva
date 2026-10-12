"""
Signal export and alerting.

Every sink implements one method, ``send(signals)``. Webhook notifiers run
in ``dry_run`` mode by default — they format and log the payload but make
no network call — so nothing leaves your machine until you deliberately
switch them on. Credentials are read from environment variables, never from
config files.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Protocol, Sequence

import pandas as pd

from .models import EntrySignal
from .utils import get_logger

log = get_logger()


class Notifier(Protocol):
    def send(self, signals: Sequence[EntrySignal]) -> None: ...


def format_signal(s: EntrySignal) -> str:
    """Human-readable alert body (Markdown-friendly)."""
    return (
        f"**{s.ticker}** LONG — {s.setup_type}\n"
        f"Entry {s.entry_price:.2f} | Stop {s.stop_loss:.2f} | Target {s.target_price:.2f} "
        f"({s.r_multiple_target:.1f}R)\n"
        f"Risk/share {s.risk_per_share:.2f} ({s.stop_atr_multiple:.2f} ATR) | "
        f"Size {s.shares} sh (${s.position_value:,.0f}, risk ${s.dollar_risk:,.0f})\n"
        f"{s.reason} | {s.timestamp:%Y-%m-%d %H:%M} {s.timeframe}"
    )


class ConsoleNotifier:
    def send(self, signals: Sequence[EntrySignal]) -> None:
        for s in signals:
            print(format_signal(s), end="\n\n")


class CSVExporter:
    """Appends signals to a CSV (creating it with a header on first write)."""

    def __init__(self, path: str | Path, append: bool = True) -> None:
        self.path = Path(path)
        self.append = append

    def send(self, signals: Sequence[EntrySignal]) -> None:
        if not signals:
            return
        from .signal_generator import signals_frame

        self.path.parent.mkdir(parents=True, exist_ok=True)
        df = signals_frame(list(signals))
        exists = self.path.exists() and self.append
        df.to_csv(self.path, mode="a" if exists else "w", header=not exists, index=False)
        log.info("Wrote %d signals to %s", len(df), self.path)


class _WebhookNotifier:
    #: Discord's edge rejects urllib's default User-Agent (HTTP 403, error 1010).
    USER_AGENT = "hybrid-scanner/0.1 (+https://github.com/investocksgeneva/Investocksgeneva)"

    def __init__(self, dry_run: bool = True, timeout: float = 10.0, max_retries: int = 3) -> None:
        self.dry_run = dry_run
        self.timeout = timeout
        self.max_retries = max_retries
        self.failures = 0
        #: Every payload sent (or that would be sent in dry-run) — for tests/auditing.
        self.payloads: list[dict] = []

    @property
    def ok(self) -> bool:
        return self.failures == 0

    def _post(self, url: str, payload: dict) -> bool:
        """POST JSON; honour HTTP 429 ``retry_after``. Never raises — alerting
        must not crash a scan — but counts failures so callers can exit non-zero."""
        self.payloads.append(payload)
        if self.dry_run:
            log.info("[dry-run] %s payload: %s", type(self).__name__, json.dumps(payload)[:300])
            return True
        body = json.dumps(payload).encode()
        headers = {"Content-Type": "application/json", "User-Agent": self.USER_AGENT}
        for attempt in range(self.max_retries + 1):
            req = urllib.request.Request(url, data=body, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310 (URL from env)
                    log.info("%s: HTTP %s", type(self).__name__, resp.status)
                    return True
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and attempt < self.max_retries:
                    wait = _retry_after(exc)
                    log.warning("%s: rate limited, retrying in %.1fs", type(self).__name__, wait)
                    time.sleep(wait)
                    continue
                log.error("%s failed: HTTP %s %s", type(self).__name__, exc.code, exc.reason)
            except Exception as exc:  # network errors, timeouts
                log.error("%s failed: %s", type(self).__name__, exc)
            break
        self.failures += 1
        return False


def _retry_after(exc: urllib.error.HTTPError) -> float:
    try:
        return min(float(json.loads(exc.read().decode() or "{}").get("retry_after", 1.0)), 60.0)
    except (ValueError, AttributeError):
        return 1.0


class DiscordNotifier(_WebhookNotifier):
    """Posts a header plus signals batched into as few messages as fit.

    Batching keeps a busy S&P 500 week to a handful of requests (Discord
    allows ~5 webhook calls per 2 s). ``allowed_mentions`` is empty so a
    ticker or reason string can never ping ``@everyone``.
    """

    LIMIT = 1900  # Discord hard cap is 2000 characters per message

    def __init__(self, webhook_env: str = "DISCORD_WEBHOOK_URL", header: str | None = None,
                 pause: float = 0.5, **kw) -> None:
        super().__init__(**kw)
        self.url = os.environ.get(webhook_env, "")
        self.header = header
        self.pause = pause
        if not self.url and not self.dry_run:
            raise ValueError(f"Set the {webhook_env} environment variable to enable Discord alerts")

    def send(self, signals: Sequence[EntrySignal]) -> None:
        blocks = [format_signal(s)[: self.LIMIT] for s in signals]
        if self.header:
            blocks.insert(0, self.header[: self.LIMIT])
        for i, message in enumerate(_pack(blocks, self.LIMIT)):
            if i and not self.dry_run:
                time.sleep(self.pause)
            self._post(self.url, {"content": message, "allowed_mentions": {"parse": []}})


def _pack(blocks: Sequence[str], limit: int, sep: str = "\n\n") -> list[str]:
    """Greedily join blocks into messages no longer than ``limit``."""
    out: list[str] = []
    cur = ""
    for b in blocks:
        candidate = f"{cur}{sep}{b}" if cur else b
        if len(candidate) <= limit:
            cur = candidate
        else:
            if cur:
                out.append(cur)
            cur = b
    if cur:
        out.append(cur)
    return out


class TelegramNotifier(_WebhookNotifier):
    def __init__(self, token_env: str = "TELEGRAM_BOT_TOKEN", chat_env: str = "TELEGRAM_CHAT_ID", **kw) -> None:
        super().__init__(**kw)
        self.token = os.environ.get(token_env, "")
        self.chat_id = os.environ.get(chat_env, "")
        if not (self.token and self.chat_id) and not self.dry_run:
            raise ValueError(f"Set {token_env} and {chat_env} to enable Telegram alerts")

    def send(self, signals: Sequence[EntrySignal]) -> None:
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        for s in signals:
            self._post(url, {"chat_id": self.chat_id, "text": format_signal(s), "parse_mode": "Markdown"})


class MacNotifier:
    """macOS notification-centre pop-up.

    Uses ``terminal-notifier`` when installed (clicking the banner opens the
    HTML report), otherwise the built-in ``osascript``. Text is passed as
    AppleScript *arguments*, never spliced into the script source, so a
    ticker or reason string can't break or inject AppleScript.

    Off macOS it logs and does nothing (so the CLI works everywhere).
    """

    def __init__(self, title: str, message: str, subtitle: str = "", open_path: str | Path | None = None,
                 runner=subprocess.run, platform: str | None = None) -> None:
        self.title, self.message, self.subtitle = title, message, subtitle
        self.open_path = Path(open_path).resolve() if open_path else None
        self._run = runner
        self.platform = platform or sys.platform
        self.failures = 0
        self.commands: list[list[str]] = []

    @property
    def ok(self) -> bool:
        return self.failures == 0

    def command(self) -> list[str]:
        tn = shutil.which("terminal-notifier")
        if tn:
            cmd = [tn, "-title", self.title, "-message", self.message, "-group", "hybrid-scanner"]
            if self.subtitle:
                cmd += ["-subtitle", self.subtitle]
            if self.open_path:
                cmd += ["-open", self.open_path.as_uri()]
            return cmd
        script = ["on run argv",
                  "display notification (item 1 of argv) with title (item 2 of argv) subtitle (item 3 of argv)",
                  "end run"]
        cmd = ["osascript"]
        for line in script:
            cmd += ["-e", line]
        return cmd + [self.message, self.title, self.subtitle]

    def send(self, signals: Sequence[EntrySignal]) -> None:
        if self.platform != "darwin":
            log.info("[macos notifier] not on macOS — would show: %s | %s | %s", self.title, self.message, self.subtitle)
            return
        cmd = self.command()
        self.commands.append(cmd)
        try:
            self._run(cmd, check=True, capture_output=True, timeout=20)
        except Exception as exc:  # missing binary, permission, timeout
            log.error("macOS notification failed: %s", exc)
            self.failures += 1


def export_rejections(df: pd.DataFrame, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    log.info("Wrote %d rejection rows to %s", len(df), path)
