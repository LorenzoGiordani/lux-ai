"""Backfill delle posizioni tradeable perse dal bug del symbol non mappato.

Contesto: il desk geopolitico emetteva decisioni su commodity usando il simbolo
"nudo" dell'LLM (CL, NG, NATGAS...) ma Hyperliquid richiede il qualificatore di
venue (xyz:CL, xyz:NATGAS). fetch_live("CL") falliva → la posizione non veniva
mai aperta, pur essendo stata approvata dal risk gate. Questo script ricostruisce
QUELLE posizioni usando la STESSA logica di open_from_decision (entry su prezzo
reale della candela di decisione + slippage, stop/target/sizing identici) e le
inserisce in journal + state, così non si perde il giro storico.

Onestà:
- entry/stop/target/size sono ricalcolati 1:1 dalla logica del desk, NON inventati;
- il prezzo e' la candela reale Hyperliquid al timestamp della decisione;
- se stop/target/time-stop sono gia' scattati sulle candele successive, la
  posizione viene chiusa al prezzo reale di quel momento (P&L onesto);
- ogni evento e' marcato backfill=True per tracciabilita' e idempotenza.

Idempotente: se ri-eseguito salta le posizioni gia' backfillate (cerca open con
lo stesso decision_ts nel journal).
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest.engine import DEFAULT_SLIPPAGE, HL_TAKER_FEE
from pipeline.live import atomic_write_text, fetch_live_cached
from scripts.paper_trade import JOURNAL, STATE_FILE

ACCOUNT = "geopolitics-v1"

# Mappatura simbolo emesso dall'LLM -> symbol Hyperliquid reale (commodity su dex
# builder HIP-3). Le crypto core (BTC, ETH...) non hanno prefisso. Servira' anche
# al desk geopolitics una volta fixato il mapping simbolo->venue.
LLM_TO_HL = {
    "CL": "xyz:CL",        # WTI crude oil
    "NG": "xyz:NATGAS",    # natural gas (Henry Hub)
    "NATGAS": "xyz:NATGAS",
    "WTI": "xyz:CL",
    "BRENT": "xyz:BRENTOIL",
}


def hl_symbol(sym: str) -> str:
    """Simbolo canonico -> nome Hyperliquid. Crypto core invariato, commodity mappata."""
    return LLM_TO_HL.get(sym, sym)


def already_backfilled(decision_ts: str, hl_sym: str) -> bool:
    """Idempotenza: una open backfill con questo decision_ts esiste gia' nel journal?"""
    if not JOURNAL.exists():
        return False
    for line in JOURNAL.read_text().splitlines():
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (e.get("type") == "open" and e.get("backfill")
                and e.get("decision_ts") == decision_ts and e.get("symbol") == hl_sym):
            return True
    return False


def simulate_exit(candles, entry_ts, direction, stop_px, target_px, time_stop_h):
    """Ricalcola se/quando la posizione sarebbe uscita (stop/target/time) sulle
    candele POST-entry reali. Ritorna (exit_px, reason, exit_ts) o None se ancora aperta."""
    sign = 1 if direction == "long" else -1
    post = candles[candles["ts"] >= entry_ts]
    if post.empty:
        return None
    hit_stop = hit_target = None
    for _, r in post.iterrows():
        lo, hi = float(r["low"]), float(r["high"])
        if lo <= stop_px and hit_stop is None:
            hit_stop = r["ts"]
        if hi >= target_px and hit_target is None:
            hit_target = r["ts"]
    last_ts = post.iloc[-1]["ts"]
    hours = (last_ts - entry_ts).total_seconds() / 3600
    # target vince se toccato prima (o per primo) dello stop
    if hit_target is not None and (hit_stop is None or hit_target <= hit_stop):
        return target_px, "target", hit_target
    if hit_stop is not None and (hit_target is None or hit_stop < hit_target):
        return stop_px, "stop", hit_stop
    if hours >= time_stop_h:
        return float(post.iloc[-1]["close"]), "time_stop", last_ts
    return None  # ancora aperta


def backfill_position(decision: dict, state: dict) -> str:
    """Ricostruisce UNA posizione persa. Ritorna una riga di log descrittiva."""
    from pipeline.live import canonical_symbol
    p = decision["proposal"]
    risk = decision["risk"]
    sym_raw = p["symbol"]
    sym = canonical_symbol(sym_raw)
    hl = hl_symbol(sym)

    if already_backfilled(decision["logged_at"], hl):
        return f"  SKIP {hl} ({decision['logged_at'][:16]}): gia' backfillata"

    candles = fetch_live_cached(hl, lookback_h=3000)["candles"]
    # entry alla candela chiusa PIU' VICINA e <= decision_ts (fill realistico:
    # la decisione e' presa intra-hour, fill alla chiusura dell'ora)
    dec_ts = pd_ts(decision["logged_at"])
    entry_row = candles[candles["ts"] <= dec_ts]
    if entry_row.empty:
        return f"  SKIP {hl}: nessuna candela <= {decision['logged_at'][:16]}"
    last = entry_row.iloc[-1]
    entry_ts = last["ts"]

    sign = 1 if p["direction"] == "long" else -1
    stop_pct = float(p["stop_pct"]) / 100
    mult = float(risk.get("size_multiplier", 1.0))
    equity = float(state[ACCOUNT]["equity"])
    exposure = min(float(p["leverage"]), float(p["risk_pct"]) * mult / float(p["stop_pct"]))
    px = float(last["close"]) * (1 + sign * DEFAULT_SLIPPAGE)   # stesso slippage del desk
    pos = {
        "strategy": ACCOUNT, "symbol": hl, "direction": p["direction"],
        "entry_px": round(px, 6),
        "size_usd": round(exposure * equity, 2),
        "stop_px": round(px * (1 - sign * stop_pct), 6),
        "target_px": round(px * (1 + sign * stop_pct * float(p["target_r"])), 6),
        "opened_at": str(entry_ts), "checked_until": str(entry_ts),
        "time_stop_h": int(p.get("time_stop_h") or 96),
        "thesis": p["thesis"], "invalidation": p.get("invalidation", ""),
        "decision_ts": decision["logged_at"],
    }
    open_event = {"type": "open", "backfill": True, "backfill_reason":
                  "symbol LLM non mappato a venue HL (CL/NG->xyz:...), fetch_live falliva",
                  **pos}
    log_event_with(open_event, decision["logged_at"])

    # e' gia' uscita su candele reali successive?
    ex = simulate_exit(candles, entry_ts, p["direction"], pos["stop_px"],
                       pos["target_px"], pos["time_stop_h"])
    if ex is None:
        # ancora aperta: entra nello state come posizione viva
        state[ACCOUNT]["positions"][hl] = {
            "strategy": ACCOUNT, "symbol": hl, "direction": p["direction"],
            "entry_px": pos["entry_px"], "size_usd": pos["size_usd"],
            "stop_px": pos["stop_px"], "target_px": pos["target_px"],
            "opened_at": pos["opened_at"], "checked_until": str(entry_ts),
            "time_stop_h": pos["time_stop_h"], "thesis": pos["thesis"],
            "invalidation": pos["invalidation"], "decision_ts": decision["logged_at"],
        }
        unreal = sign * (float(candles.iloc[-1]["close"]) / px - 1) * pos["size_usd"]
        return (f"  OPEN {hl} {p['direction']} @ {px:.4g} size {pos['size_usd']}$ "
                f"(ancora aperta, unrealized ~${unreal:+.2f})")
    # chiusa: close event + realizza P&L nell'equity
    exit_px, reason, exit_ts = ex
    pnl = sign * (exit_px / px - 1) * pos["size_usd"] - pos["size_usd"] * HL_TAKER_FEE
    state[ACCOUNT]["equity"] = round(equity + pnl, 6)
    close_event = {
        "type": "close", "backfill": True, "strategy": ACCOUNT, "symbol": hl,
        "reason": reason, "exit_px": round(exit_px, 6), "frac": 1.0, "remaining": 0.0,
        "pnl_usd": round(pnl, 2), "equity": state[ACCOUNT]["equity"],
        "ts": str(exit_ts),
    }
    log_event_with(close_event, decision["logged_at"])
    return (f"  CLOSED {hl} {p['direction']} @ {exit_px:.4g} ({reason}) "
            f"pnl ${pnl:+.2f} entro {exit_ts}")


def pd_ts(s: str):
    import pandas as pd
    return pd.Timestamp(s)


def log_event_with(event: dict, decision_ts: str) -> None:
    """log_event ma con logged_at = decision_ts (cosi' l'evento e' coerente nel
    tempo con la decisione che lo ha generato, non 'ora'). Append-only."""
    event["logged_at"] = decision_ts
    with JOURNAL.open("a") as f:
        f.write(json.dumps(event, default=str) + "\n")


def lost_decisions() -> list[dict]:
    """Decisioni tradeable del desk geopolitico senza una open corrispondente
    ( né reale né gia' backfillata) nelle ultime 48h."""
    decisions = [json.loads(l) for l in JOURNAL.parent.joinpath("decisions.jsonl").read_text().splitlines()
                 if l.strip()]
    journal = [json.loads(l) for l in JOURNAL.read_text().splitlines() if l.strip()]
    cutoff = (datetime.now(timezone.utc).timestamp() - 48 * 3600)
    from pipeline.live import canonical_symbol
    out = []
    for d in decisions:
        if d.get("strategy") != ACCOUNT or d.get("stage") != "final":
            continue
        r = d.get("risk")
        if not isinstance(r, dict) or r.get("verdict") not in ("approve", "reduce"):
            continue
        p = d.get("proposal", {})
        if p.get("action") != "trade":
            continue
        ts = d["logged_at"]
        try:
            if datetime.fromisoformat(ts).timestamp() < cutoff:
                continue
        except ValueError:
            continue
        sym = canonical_symbol(p.get("symbol", ""))
        hl = hl_symbol(sym)
        # ha gia' una open reale o backfill con questo decision_ts?
        has_open = any(e.get("type") == "open" and e.get("strategy") == ACCOUNT
                       and e.get("decision_ts") == ts for e in journal)
        if not has_open:
            out.append(d)
    return out


def main() -> int:
    state = json.loads(STATE_FILE.read_text())
    lost = lost_decisions()
    if not lost:
        print("[backfill] nessuna posizione tradeable persa da recuperare.")
        return 0
    print(f"[backfill] {len(lost)} posizione/i persa/e da ricostruire:")
    for d in lost:
        print(f"  - {d['logged_at'][:16]} {d['proposal']['symbol']} "
              f"{d['proposal']['direction']} (risk={d['risk']['verdict']})")
    print("\nricostruzione (prezzi reali Hyperliquid, logica identica al desk):")
    for d in lost:
        try:
            print(backfill_position(d, state))
        except Exception as e:
            print(f"  ERRORE su {d['proposal']['symbol']}: {e}")
    atomic_write_text(STATE_FILE, json.dumps(state, indent=1, default=str))
    print(f"\n[backfill] state + journal aggiornati.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
