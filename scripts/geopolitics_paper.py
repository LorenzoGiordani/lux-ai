"""Desk geopolitico (account 'geopolitics-v1') — layer LLM cross-asset GATED.

Gira a ogni cron, ma è economico: prima controlla se c'è un BURST geopolitico
attivo (GDELT topic=geopolitics, news_events_live). Senza burst → aggiorna le
posizioni aperte e logga heartbeat, ZERO chiamate LLM. Con burst → il desk
(Analyst geo → Bull/Bear → Strategist → Risk, riuso di decide.py) ragiona sul
canale di trasmissione cross-asset (oil, gold, natgas, crypto) e propone UN
trade. La DIREZIONE esce dal nesso causale, mai dal tono (falsificato, event
study 2026-06-13).

Le decisioni vanno in paper/decisions.jsonl taggate strategy=geopolitics-v1 →
isolate dal desk agents-v1. Uso:
  uv run scripts/geopolitics_paper.py            # full auto (richiede CLI claude)
  uv run scripts/geopolitics_paper.py --pack     # stampa contesto+prompt (LLM in sessione)
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backtest.engine import DEFAULT_SLIPPAGE, HL_TAKER_FEE
from backtest.lifecycle import all_specs
from pipeline.live import fetch_live
from scripts.decide import ROLES, _ask_role, build_context, hard_check, log_decision
from scripts.paper_trade import STATE_FILE, log_event, update_position

ACCOUNT = "geopolitics-v1"
DECISIONS = ROOT / "paper/decisions.jsonl"
EVENTS_PARQUET = ROOT / "data/news/gdelt_events.parquet"

# Analyst specializzato: sostituisce quello crypto di decide.py. Resto dei ruoli riusato.
ANALYST_GEO = (
    "Sei lo stratega geopolitico di un desk macro cross-asset. È ATTIVO un burst "
    "geopolitico (GDELT): {bursts}. Dal contesto (oil, gold, natgas, crypto: prezzi, "
    "regime, segnali) e dai titoli, produci un brief: 1) qual è il catalizzatore e il "
    "suo CANALE DI TRASMISSIONE più diretto (guerra/sanzioni → energia; risk-off → "
    "safe-haven/deleveraging crypto); 2) per ogni asset, impatto atteso e perché; "
    "3) l'asset dove l'edge geopolitico è più pulito e direzionale. "
    "VINCOLO: NON usare il tono/sentiment delle news come predittore di direzione "
    "(falsificato, event study: tone_hit 0.38<0.50). La direzione esce SOLO dal "
    "ragionamento causale sul canale di trasmissione. Max 350 parole."
)


def load_spec() -> dict:
    for _, s in all_specs():
        if s.get("id") == ACCOUNT:
            return s
    raise RuntimeError(f"spec {ACCOUNT} non trovata")


def active_bursts(params: dict) -> list[dict]:
    """Burst geopolitici attivi nelle ultime max_age_h.

    Fonte PRIMARIA = gdelt_events.parquet (offline, rinfrescato da
    gdelt-precompute.yml ogni ora): niente 429, niente gate chiuso per rate-limit.
    Fonte secondaria = live GDELT via news_events_cached (come complemento fresco
    se il precompute è indietro). Lista vuota = gate chiuso (zero costo LLM)."""
    topic = params.get("topics", "geopolitics")
    min_z = float(params.get("min_z", 2.0))
    max_age_h = int(params.get("max_age_h", 96))
    now = datetime.now(timezone.utc)

    ev = None
    if EVENTS_PARQUET.exists():
        ev = pd.read_parquet(EVENTS_PARQUET)
        if not ev.empty:
            ev["ts"] = pd.to_datetime(ev["ts"], utc=True)
    # integrazione con la cache live (se esiste e non vuota), per catturare burst
    # troppo recenti per il precompute orario
    try:
        from pipeline.gdelt import news_events_cached
        live = news_events_cached(days=max(14, max_age_h // 24 + 2))
        if live is not None and not live.empty:
            live["ts"] = pd.to_datetime(live["ts"], utc=True)
            ev = pd.concat([ev, live]).drop_duplicates(subset=["ts", "topic"]) if ev is not None else live
    except Exception as e:
        print(f"  gdelt live fallita ({e}), uso solo parquet precompute", file=sys.stderr)
    if ev is None or ev.empty:
        return []
    ev = ev[(ev["topic"] == topic) & (ev["z"] >= min_z)].copy()
    if ev.empty:
        return []
    ev = ev[(now - ev["ts"]) <= pd.Timedelta(hours=max_age_h)]
    return [{"ts": str(r.ts)[:16], "z": round(float(r.z), 2), "tone": round(float(r.tone), 2)}
            for r in ev.itertuples()]


def run_desk(symbols: list[str], bursts: list[dict], pack: bool) -> dict | None:
    ctx = build_context(symbols)
    ctx["geopolitical_bursts"] = bursts
    analyst = ANALYST_GEO.format(bursts=json.dumps(bursts, ensure_ascii=False))
    if pack:
        print(f"# BURST GEOPOLITICI ATTIVI\n{json.dumps(bursts, indent=1)}\n")
        print(f"# CONTESTO\n{json.dumps(ctx['assets'], indent=1, default=str)}\n")
        print("## News\n" + "\n".join(f"- [{n['ts'][:16]}] {n['title']}" for n in ctx["news"]))
        for role, prompt in {"analyst": analyst, **{k: v for k, v in ROLES.items() if k != "analyst"}}.items():
            print(f"\n=== RUOLO: {role.upper()} ===\n{prompt}")
        return None
    brief = _ask_role("geo_analyst",
                      f"BURST GEOPOLITICI ATTIVI:\n{json.dumps(bursts, ensure_ascii=False)}\n\n"
                      f"CONTESTO:\n{json.dumps(ctx, default=str)}")
    bull = _ask_role("bull", f"BRIEF:\n{brief}")
    bear = _ask_role("bear", f"BRIEF:\n{brief}")
    proposal = _ask_role("strategist", f"BRIEF:\n{brief}\n\nBULL:\n{bull}\n\nBEAR:\n{bear}")
    errs = hard_check(proposal)
    if errs:
        log_decision({"strategy": ACCOUNT, "stage": "final", "bursts": bursts,
                      "proposal": proposal, "verdict": "hard_veto", "violations": errs})
        print(f"HARD VETO: {errs}")
        return None
    risk = _ask_role("risk", f"PROPOSTA:\n{json.dumps(proposal)}\n\nBRIEF:\n{brief}")
    log_decision({"strategy": ACCOUNT, "stage": "final", "bursts": bursts,
                  "brief": brief, "bull": bull, "bear": bear, "proposal": proposal, "risk": risk})
    print(json.dumps({"proposal": proposal, "risk": risk}, indent=1, default=str))
    return {"proposal": proposal, "risk": risk}


def pending_decisions(after_ts: str) -> list[dict]:
    """Solo le decisioni final di QUESTO account, approvate dal Risk."""
    if not DECISIONS.exists():
        return []
    out = []
    for line in DECISIONS.read_text().splitlines():
        d = json.loads(line)
        if d.get("strategy") != ACCOUNT or d.get("stage") != "final":
            continue
        if d.get("logged_at", "") <= after_ts:
            continue
        p, risk = d.get("proposal", {}), d.get("risk", {})
        if p.get("action") == "trade" and risk.get("verdict") in ("approve", "reduce"):
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
    pos = {
        "strategy": ACCOUNT, "symbol": symbol, "direction": p["direction"],
        "entry_px": px, "size_usd": round(exposure * equity, 2),
        "stop_px": px * (1 - sign * stop_pct),
        "target_px": px * (1 + sign * stop_pct * float(p["target_r"])),
        "opened_at": str(last.ts), "checked_until": str(last.ts),
        # fallback 96h se l'LLM omette/emette 0 → posizione eterna senza time-stop (bug latente)
        "time_stop_h": int(p.get("time_stop_h") or 96),
        "thesis": p["thesis"], "invalidation": p["invalidation"], "decision_ts": d["logged_at"],
    }
    log_event({"type": "open", **pos})
    print(f"  OPEN {symbol} {p['direction']} @ {px:.4g}, size {pos['size_usd']}$ "
          f"(risk {d['risk']['verdict']} ×{mult})")
    return pos


def main() -> None:
    pack = "--pack" in sys.argv
    spec = load_spec()
    symbols = spec["paper_symbols"].split(",")
    gate = next((s["params"] for s in spec.get("signals", []) if s["name"] == "news_event"), {})
    max_conc = int(spec["risk"]["max_concurrent_positions"])

    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    st = state.setdefault(ACCOUNT, {"equity": 10_000.0, "positions": {}, "last_decision_ts": ""})
    print(f"geo desk {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC — equity {st['equity']:.2f}$")

    # 1. aggiorna posizioni aperte (sempre, anche senza burst)
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

    # 2. GATE: decidi solo se c'è un burst geopolitico attivo
    bursts = active_bursts(gate)
    if not bursts:
        print("  gate chiuso: nessun burst geopolitico attivo → nessuna decisione")
    elif pack:
        run_desk(symbols, bursts, pack=True)
        return
    else:
        print(f"  GATE APERTO: {len(bursts)} burst → desk LLM")
        run_desk(symbols, bursts, pack=False)

    # 3. esegui le decisioni nuove di questo account
    for d in pending_decisions(st["last_decision_ts"]):
        st["last_decision_ts"] = max(st["last_decision_ts"], d["logged_at"])
        symbol = d["proposal"]["symbol"]
        if symbol in st["positions"] or len(st["positions"]) >= max_conc:
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
