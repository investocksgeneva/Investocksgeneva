"""
Paper trading loop — runs against live Binance prices, no real orders placed.
State is persisted in paper_state.json so it survives restarts.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from .config import CFG
from .data import fetch_latest_price, fetch_ohlcv
from .indicators import add_signals, current_emas

STATE_FILE = Path("paper_state.json")


def _load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "capital": CFG.initial_capital,
        "position": None,
        "trades": [],
    }


def _save_state(state: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


def _fmt(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%d %H:%M UTC")


def run_loop() -> None:
    print(f"[paper] Starting paper trader — {CFG.symbol} {CFG.timeframe}")
    print(f"[paper] EMA {CFG.ema_fast}/{CFG.ema_slow}  SL={CFG.stop_loss_pct*100:.0f}%  TP={CFG.take_profit_pct*100:.0f}%")
    print(f"[paper] Poll every {CFG.poll_interval_seconds}s. Ctrl-C to stop.\n")

    state = _load_state()

    while True:
        try:
            now = datetime.now(timezone.utc)
            df = fetch_ohlcv(days=30)
            df = add_signals(df)
            ema_f, ema_s = current_emas(df)
            signal = int(df["signal"].iloc[-1])
            price = fetch_latest_price()

            capital: float = state["capital"]
            pos = state["position"]

            status = "LONG" if pos else "FLAT"
            print(
                f"[{_fmt(now)}] {CFG.symbol} ${price:,.2f}  "
                f"EMA{CFG.ema_fast}={ema_f:,.0f}  EMA{CFG.ema_slow}={ema_s:,.0f}  "
                f"signal={signal:+d}  status={status}  capital=${capital:,.2f}"
            )

            if pos:
                # Check stop / TP
                hit_sl = price <= pos["stop_loss"]
                hit_tp = price >= pos["take_profit"]

                if hit_sl or hit_tp:
                    reason = "STOP_LOSS" if hit_sl else "TAKE_PROFIT"
                    exit_price = pos["stop_loss"] if hit_sl else pos["take_profit"]
                    btc = pos["size"]
                    pnl = (exit_price - pos["entry_price"]) * btc
                    state["capital"] += btc * exit_price
                    trade_record = {**pos, "exit_price": exit_price, "exit_time": str(now), "pnl": pnl, "reason": reason}
                    state["trades"].append(trade_record)
                    state["position"] = None
                    print(f"  >> {reason}  exit=${exit_price:,.2f}  P&L={pnl:+.2f} USDT")
                elif signal == -1:
                    pnl = (price - pos["entry_price"]) * pos["size"]
                    state["capital"] += pos["size"] * price
                    trade_record = {**pos, "exit_price": price, "exit_time": str(now), "pnl": pnl, "reason": "SIGNAL_EXIT"}
                    state["trades"].append(trade_record)
                    state["position"] = None
                    print(f"  >> SIGNAL_EXIT (death cross)  exit=${price:,.2f}  P&L={pnl:+.2f} USDT")

            if not state["position"] and signal == 1:
                usdt = state["capital"] * CFG.position_size_pct
                btc = usdt / price
                state["capital"] -= usdt
                state["position"] = {
                    "entry_price": price,
                    "entry_time": str(now),
                    "size": btc,
                    "stop_loss": price * (1 - CFG.stop_loss_pct),
                    "take_profit": price * (1 + CFG.take_profit_pct),
                }
                print(f"  >> BUY  {btc:.6f} BTC @ ${price:,.2f}  SL=${state['position']['stop_loss']:,.2f}  TP=${state['position']['take_profit']:,.2f}")

            _save_state(state)

        except KeyboardInterrupt:
            print("\n[paper] Stopped by user.")
            _save_state(state)
            break
        except Exception as exc:
            print(f"[paper] Error: {exc}")

        time.sleep(CFG.poll_interval_seconds)
