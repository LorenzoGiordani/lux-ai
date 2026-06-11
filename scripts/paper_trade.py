"""Paper trading su dati live — forward test (M2). Zero fondi, zero ordini reali.

Uso: uv run scripts/paper_trade.py <strategia.yaml> BTC,ETH,SOL
Pensato per girare ogni decision_every_h via cron. Ogni run:
1. scarica candele/funding/flow recenti (Binance, stessa fonte del backtest)
2. aggiorna le posizioni aperte (stop/target/time-stop sulle candele trascorse)
3. apre nuove posizioni se il segnale è attivo all'ultima barra chiusa
4. stato in paper/state.json, ogni evento in paper/journal.jsonl

Stesse assunzioni dell'engine: fee taker 4.5bps, slippage 2bps.
"""

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from backtest.engine import DEFAULT_SLIPPAGE, HL_TAKER_FEE
from backtest.signals import SIGNALS
from backtest.strategy import _direction, _eval_rule, load

FAPI = "https://fapi.binance.com"
ROOT = Path(__file__).resolve().parent.parent  # indipendente dal cwd (cron)
STATE_FILE = ROOT / "paper/state.json"
JOURNAL = ROOT / "paper/journal.jsonl"
LOOKBACK_H = 1000  # copre il lookback massimo dei segnali (336+48)


def fetch_live(symbol: str) -> dict:
    pair = f"{symbol}USDT"
    kl = requests.get(f"{FAPI}/fapi/v1/klines", params={
        "symbol": pair, "interval": "1h", "limit": min(LOOKBACK_H, 1000)}, timeout=30).json()
    candles = pd.DataFrame({
        "ts": pd.to_datetime([k[0] for k in kl], unit="ms", utc=True),
        "open": [float(k[1]) for k in kl], "high": [float(k[2]) for k in kl],
        "low": [float(k[3]) for k in kl], "close": [float(k[4]) for k in kl],
        "volume": [float(k[5]) for k in kl]})
    flow = pd.DataFrame({"ts": candles.ts, "volume": candles.volume,
                         "taker_buy": [float(k[9]) for k in kl]})
    fr = requests.get(f"{FAPI}/fapi/v1/fundingRate", params={
        "symbol": pair, "limit": 1000}, timeout=30).json()
    funding = pd.DataFrame({
        "ts": pd.to_datetime([r["fundingTime"] for r in fr], unit="ms", utc=True),
        "rate": [float(r["fundingRate"]) for r in fr]})
    time.sleep(0.1)
    # ultima candela è in corso → si decide sull'ultima CHIUSA
    return {"candles": candles.iloc[:-1].reset_index(drop=True), "flow": flow, "funding": funding}


def log_event(event: dict) -> None:
    event["logged_at"] = datetime.now(timezone.utc).isoformat()
    with JOURNAL.open("a") as f:
        f.write(json.dumps(event, default=str) + "\n")


def update_position(pos: dict, candles: pd.DataFrame, spec: dict, equity: float) -> tuple[dict | None, float]:
    """Controlla stop/target/time-stop sulle candele successive all'ultimo check."""
    new = candles[candles.ts > pd.Timestamp(pos["checked_until"])]
    sign = 1 if pos["direction"] == "long" else -1
    for _, row in new.iterrows():
        hit_stop = (row.low <= pos["stop_px"]) if sign > 0 else (row.high >= pos["stop_px"])
        hit_target = (row.high >= pos["target_px"]) if sign > 0 else (row.low <= pos["target_px"])
        expired = (row.ts - pd.Timestamp(pos["opened_at"])) >= timedelta(hours=spec["exit"]["time_stop_h"])
        reason, px = None, None
        if hit_stop:  # conservativo: stop prima del target nella stessa candela
            reason, px = "stopped", pos["stop_px"] * (1 - sign * DEFAULT_SLIPPAGE)
        elif hit_target:
            reason, px = "target", pos["target_px"] * (1 - sign * DEFAULT_SLIPPAGE)
        elif expired:
            reason, px = "time_stop", row.close * (1 - sign * DEFAULT_SLIPPAGE)
        if reason:
            pnl = pos["size_usd"] * (px / pos["entry_px"] - 1) * sign - pos["size_usd"] * HL_TAKER_FEE
            equity += pnl
            log_event({"type": "close", "strategy": pos["strategy"], "symbol": pos["symbol"],
                       "reason": reason, "exit_px": px, "pnl_usd": round(pnl, 2),
                       "equity": round(equity, 2), "ts": row.ts})
            print(f"  CLOSE {pos['symbol']} {pos['direction']} → {reason}, pnl {pnl:+.2f}$")
            return None, equity
    pos["checked_until"] = str(candles.ts.iloc[-1])
    return pos, equity


def maybe_open(spec: dict, symbol: str, data: dict, equity: float, strategy_id: str) -> dict | None:
    sigs = pd.DataFrame({s["name"]: SIGNALS[s["name"]](data, **s.get("params", {}))
                         for s in spec["signals"]})
    active = _eval_rule(spec["entry"]["rule"], sigs).iloc[-1]
    direction = float(_direction(spec["entry"]["direction"], sigs).iloc[-1])
    if not active or direction == 0:
        return None
    last = data["candles"].iloc[-1]
    sign = 1 if direction > 0 else -1
    stop_pct = float(spec["exit"]["stop_pct"]) / 100
    exposure = min(float(spec["risk"]["max_leverage"]),
                   float(spec["risk"]["risk_per_trade_pct"]) / float(spec["exit"]["stop_pct"]))
    px = last.close * (1 + sign * DEFAULT_SLIPPAGE)
    pos = {
        "strategy": strategy_id, "symbol": symbol,
        "direction": "long" if sign > 0 else "short",
        "entry_px": px, "size_usd": round(exposure * equity, 2),
        "stop_px": px * (1 - sign * stop_pct),
        "target_px": px * (1 + sign * stop_pct * float(spec["exit"]["target_r"])),
        "opened_at": str(last.ts), "checked_until": str(last.ts),
    }
    log_event({"type": "open", **pos,
               "thesis": f"{spec['entry']['rule']} → {spec['entry']['direction']}",
               "signals_last": {c: int(sigs[c].iloc[-1]) for c in sigs.columns}})
    print(f"  OPEN {symbol} {pos['direction']} @ {px:.4g}, size {pos['size_usd']}$, "
          f"stop {pos['stop_px']:.4g}, target {pos['target_px']:.4g}")
    return pos


def main() -> None:
    spec_path, symbols = sys.argv[1], sys.argv[2].split(",")
    if not Path(spec_path).is_absolute():
        spec_path = ROOT / spec_path
    spec = load(spec_path)
    sid = spec["id"]
    STATE_FILE.parent.mkdir(exist_ok=True)
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    st = state.setdefault(sid, {"equity": 10_000.0, "positions": {}})

    print(f"paper run {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC — {sid}, equity {st['equity']:.2f}$")
    max_conc = int(spec["risk"]["max_concurrent_positions"])

    for symbol in symbols:
        try:
            data = fetch_live(symbol)
        except Exception as e:
            print(f"  {symbol}: fetch fallito ({e})", file=sys.stderr)
            continue
        pos = st["positions"].get(symbol)
        if pos:
            pos, st["equity"] = update_position(pos, data["candles"], spec, st["equity"])
            if pos:
                st["positions"][symbol] = pos
            else:
                del st["positions"][symbol]
        if symbol not in st["positions"] and len(st["positions"]) < max_conc:
            new_pos = maybe_open(spec, symbol, data, st["equity"], sid)
            if new_pos:
                st["equity"] -= new_pos["size_usd"] * HL_TAKER_FEE
                st["positions"][symbol] = new_pos

    open_syms = list(st["positions"]) or "nessuna"
    print(f"fine run: equity {st['equity']:.2f}$, posizioni aperte: {open_syms}")
    STATE_FILE.write_text(json.dumps(state, indent=1, default=str))
    log_event({"type": "heartbeat", "strategy": sid, "equity": round(st["equity"], 2),
               "open_positions": len(st["positions"])})


if __name__ == "__main__":
    main()
