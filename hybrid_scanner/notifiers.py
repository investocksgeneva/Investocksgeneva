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
    def __init__(self, dry_run: bool = True, timeout: float = 10.0) -> None:
        self.dry_run = dry_run
        self.timeout = timeout

    def _post(self, url: str, payload: dict) -> None:
        if self.dry_run:
            log.info("[dry-run] %s payload: %s", type(self).__name__, json.dumps(payload)[:300])
            return
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310 (URL from env)
                log.info("%s: HTTP %s", type(self).__name__, resp.status)
        except Exception as exc:  # alerting must never crash the scanner
            log.error("%s failed: %s", type(self).__name__, exc)


class DiscordNotifier(_WebhookNotifier):
    def __init__(self, webhook_env: str = "DISCORD_WEBHOOK_URL", **kw) -> None:
        super().__init__(**kw)
        self.url = os.environ.get(webhook_env, "")
        if not self.url and not self.dry_run:
            raise ValueError(f"Set {webhook_env} to enable Discord alerts")

    def send(self, signals: Sequence[EntrySignal]) -> None:
        for s in signals:
            self._post(self.url, {"content": format_signal(s)[:1990]})  # Discord 2000-char cap


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


def export_rejections(df: pd.DataFrame, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    log.info("Wrote %d rejection rows to %s", len(df), path)
