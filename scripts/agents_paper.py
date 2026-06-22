"""Executor paper per le decisioni della pipeline agenti (account "agents-v1").

Ogni run (cron, insieme a paper_trade):
1. aggiorna le posizioni aperte (stop/target/time-stop su candele reali)
2. ingerisce le decisioni nuove da paper/decisions.jsonl (stage final,
   risk verdict approve/reduce, hard_check passed) e apre le posizioni

Balance fittizio 10k$, dati e prezzi reali. Stesse fee/slippage dell'engine.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backtest.engine import DEFAULT_SLIPPAGE, HL_TAKER_FEE
from pipeline.live import fetch_live
from scripts.paper_trade import JOURNAL, STATE_FILE, log_event, update_position

# Default = desk storico. Override via --account/--target-r per varianti di sola
# ESECUZIONE che riusano le STESSE decisioni (zero chiamate LLM extra): es.
# agents-rr2-v1 esegue le decisioni di agents-v1 forzando RR=2.0. Le decisioni del
# desk agents non portano campo "strategy" → d.get("strategy", ACCOUNT) le matcha
# per qualsiasi account; i desk con tag proprio (es. geopolitics-v1) restano esclusi.
ACCOUNT = "agents-v1"
TARGET_R = None             # None = usa il target_r proposto dall'LLM (comportamento storico)
DECISIONS = ROOT / "paper/decisions.jsonl"
MAX_CONCURRENT = 3


def pending_decisions(after_ts: str) -> list[dict]:
    if not DECISIONS.exists():
        return []
    out = []
    for line in DECISIONS.read_text().splitlines():
        d = json.loads(line)
        if d.get("stage") != "final" or d.get("logged_at", "") <= after_ts:
            continue
        if d.get("strategy", ACCOUNT) != ACCOUNT:   # ignora decisioni di altri desk (es. geopolitics-v1)
            continue
        p = d.get("proposal", {})
        risk = d.get("risk", {})
        if p.get("action") != "trade" or risk.get("verdict") not in ("approve", "reduce"):
            continue
        out.append(d)
    return out


def open_from_decision(d: dict, equity: float) -> dict | None:
    p = d["proposal"]
    symbol = p["symbol"]
    try:
        data = fetch_live(symbol, lookback_h=50)
    except Exception as e:
        print(f"  {symbol}: fetch fallito ({e})", file=sys.stderr)
        return None
    last = data["candles"].iloc[-1]
    sign = 1 if p["direction"] == "long" else -1
    stop_pct = float(p["stop_pct"]) / 100
    mult = float(d["risk"].get("size_multiplier", 1.0))
    exposure = min(float(p["leverage"]), float(p["risk_pct"]) * mult / float(p["stop_pct"]))
    px = float(last.close) * (1 + sign * DEFAULT_SLIPPAGE)
    target_r = TARGET_R if TARGET_R is not None else float(p["target_r"])   # override RR (variante A/B)
    pos = {
        "strategy": ACCOUNT, "symbol": symbol, "direction": p["direction"],
        "entry_px": px, "size_usd": round(exposure * equity, 2),
        "stop_px": px * (1 - sign * stop_pct),
        "target_px": px * (1 + sign * stop_pct * target_r),
        "opened_at": str(last.ts), "checked_until": str(last.ts),
        "time_stop_h": int(p["time_stop_h"]),
        "thesis": p["thesis"], "invalidation": p["invalidation"],
        "decision_ts": d["logged_at"],
    }
    log_event({"type": "open", **pos})
    print(f"  OPEN {symbol} {p['direction']} @ {px:.4g}, size {pos['size_usd']}$ "
          f"(risk verdict: {d['risk']['verdict']} ×{mult})")
    return pos


def main() -> None:
    global ACCOUNT, TARGET_R
    ap = argparse.ArgumentParser(description="Executor paper decisioni desk agenti")
    ap.add_argument("--account", default=ACCOUNT, help="account paper (default agents-v1)")
    ap.add_argument("--target-r", type=float, default=None,
                    help="forza l'RR all'esecuzione (variante A/B; default = RR proposto dall'LLM)")
    args = ap.parse_args()
    ACCOUNT, TARGET_R = args.account, args.target_r

    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    st = state.setdefault(ACCOUNT, {"equity": 10_000.0, "positions": {}, "last_decision_ts": ""})
    print(f"agents paper run {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC — equity {st['equity']:.2f}$")

    # 1. aggiorna posizioni aperte
    for symbol in list(st["positions"]):
        pos = st["positions"][symbol]
        try:
            data = fetch_live(symbol, lookback_h=200)
        except Exception as e:
            print(f"  {symbol}: fetch fallito ({e})", file=sys.stderr)
            continue
        pos, st["equity"] = update_position(pos, data["candles"], pos["time_stop_h"],
                                            st["equity"], data.get("forming"))
        if pos:
            st["positions"][symbol] = pos
        else:
            del st["positions"][symbol]

    # 2. esegui decisioni nuove
    for d in pending_decisions(st["last_decision_ts"]):
        st["last_decision_ts"] = max(st["last_decision_ts"], d["logged_at"])
        symbol = d["proposal"]["symbol"]
        if symbol in st["positions"] or len(st["positions"]) >= MAX_CONCURRENT:
            log_event({"type": "skip", "strategy": ACCOUNT, "symbol": symbol,
                       "reason": "posizione esistente o max concorrenti"})
            continue
        pos = open_from_decision(d, st["equity"])
        if pos:
            st["equity"] -= pos["size_usd"] * HL_TAKER_FEE
            st["positions"][symbol] = pos

    print(f"fine run: equity {st['equity']:.2f}$, posizioni: {list(st['positions']) or 'nessuna'}")
    STATE_FILE.write_text(json.dumps(state, indent=1, default=str))
    log_event({"type": "heartbeat", "strategy": ACCOUNT, "equity": round(st["equity"], 2),
               "open_positions": len(st["positions"])})


if __name__ == "__main__":
    main()
