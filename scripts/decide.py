"""Pipeline agenti v1 — una decisione di trading end-to-end (Step 3).

Ruoli: Research+Analyst (brief) → Bull vs Bear (debate) → Strategist (proposta
JSON) → hard limit nel codice (veto deterministico, insindacabile) → Risk
Manager LLM (veto qualitativo). Output: decisione nel journal.

Modi:
  uv run scripts/decide.py BTC,ETH,SOL              # full auto via GLM-5.2 (Z.ai Coding Plan)
  uv run scripts/decide.py BTC,ETH,SOL --pack       # stampa contesto+prompt (per ispezione, LLM esterno)
  uv run scripts/decide.py BTC,ETH,SOL --check p.json  # valida proposta Strategist e logga

Hard limits (non negoziabili dall'LLM): leva ≤2, rischio ≤1% equity/trade,
stop obbligatorio 0.5-8%, max 3 posizioni, solo simboli del contesto.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backtest.risk import atr_pct
from backtest.signals import SIGNALS
from backtest.walkforward import regimes
from pipeline.live import fetch_live, news_headlines, open_interest_24h

DECISIONS = ROOT / "paper/decisions.jsonl"

HARD_LIMITS = {
    "max_leverage": 2.0,
    "max_risk_per_trade_pct": 1.0,
    "stop_pct_range": (0.5, 8.0),
    "min_stop_atr_mult": 1.0,   # lo stop deve stare FUORI dal rumore: >= 1*ATR% dell'asset
    "max_concurrent_positions": 3,
}

from scripts.prompts import get_role, SCHEMA as _SCHEMAS, role_names

# Prompt centralizzati in prompts/roles.yaml (versionati, A/B-testabili). ROLES
# espone il solo system-string per retro-compat (geopolitics_paper, render_pack);
# il flusso nuovo usa _ask_role() che applica anche effort + structured output.
ROLES = {n: get_role(n).system for n in role_names()}


def _ask_role(role_name: str, prompt: str, cache: bool = False):
    """Chiamata LLM role-aware: legge system/effort/schema dal yaml centralizzato.
    GLM-5.2 via Z.ai Coding Plan. Se il ruolo ha `schema_name` → structured output
    nativo (tool use forzato, ritorna dict già validato)."""
    r = get_role(role_name)
    schema = _SCHEMAS().get(r.schema_name) if r.schema_name else None
    from scripts.llm import ask
    return ask(prompt, system=r.system, effort=r.effort, schema=schema,
               schema_name=r.schema_name or "answer", role=role_name,
               cache=cache, as_json=r.json)


def aggregate_proposals(votes: list[dict]) -> dict:
    """Self-consistency: majority vote fra N proposte dello Strategist.

    - maggioranza (>=) di no_trade → no_trade (la prudenza domina)
    - altrimenti plurality su (symbol, direction); i campi numerici sono la media
      delle proposte allineate (riduce la varianza di un singolo sample LLM)
    Ritorna la proposta + metadati sc_votes/sc_consensus per il tracing."""
    from collections import Counter
    valid = [v for v in votes if isinstance(v, dict)]
    if not valid:
        raise RuntimeError("self-consistency: nessuna proposta valida")
    n_no = sum(1 for v in valid if v.get("action") == "no_trade")
    if n_no * 2 >= len(valid):          # maggioranza (>=) di no_trade
        return {"action": "no_trade", "sc_votes": len(votes), "sc_consensus": n_no}
    trades = [v for v in valid if v.get("action") == "trade"]
    if not trades:
        return {"action": "no_trade", "sc_votes": len(votes), "sc_consensus": 0}
    key = Counter((v.get("symbol"), v.get("direction")) for v in trades).most_common(1)[0][0]
    aligned = [v for v in trades if (v.get("symbol"), v.get("direction")) == key]
    rep = dict(aligned[0])
    for f in ("leverage", "risk_pct", "stop_pct", "target_r", "time_stop_h"):
        nums = [v[f] for v in aligned if isinstance(v.get(f), (int, float))]
        if nums:
            rep[f] = round(sum(nums) / len(nums), 3)
    rep["sc_votes"] = len(votes)
    rep["sc_consensus"] = len(aligned)
    return rep


def _ask_strategist(prompt: str, n: int | None = None) -> dict:
    """Decisione finale dello Strategist con self-consistency (default N=3).
    GLM-5.2 a temp di default (≈1) = campioni indipendenti → la votazione riduce
    la varianza del flip-di-moneta di una singola chiamata LLM. N via env GLM_SC_N."""
    import os
    n = n if n is not None else max(1, int(os.environ.get("GLM_SC_N", "3")))
    if n <= 1:
        return _ask_role("strategist", prompt)
    votes = [_ask_role("strategist", prompt) for _ in range(n)]
    return aggregate_proposals(votes)


def _ask(prompt: str, as_json: bool = False, effort: str = "max", role: str | None = None):
    """Generic LLM call (GLM-5.2, layer scripts/llm.py). Mantenuto per i chiamanti
    legacy (le strategie importano _ask). Il flusso agenti preferisce _ask_role()."""
    from scripts.llm import ask
    return ask(prompt, as_json=as_json, effort=effort, role=role)


def signal_states(data: dict) -> dict:
    return {name: int(fn(data).iloc[-1]) for name, fn in SIGNALS.items()}


# Confluenza LUX 1.0: l'edge sistematico più robusto del desk, distillato per l'LLM.
LUX_CORE = ["tsmom", "liq_imbalance", "kronos_forecast"]   # devono concordare (top-conviction)
LUX_VOTE = LUX_CORE + ["smart_money_ratio", "oi_trend"]     # voto direzionale a 5


def lux_confluence(sig: dict) -> dict:
    """Stato confluenza LUX dai segnali correnti. aligned=True quando i 3 core
    (trend+liquidazioni+Kronos) sono tutti attivi E concordi → setup top-conviction."""
    core = [sig.get(n, 0) for n in LUX_CORE]
    aligned = all(v != 0 for v in core) and len({v > 0 for v in core}) == 1
    score = sum(sig.get(n, 0) for n in LUX_VOTE)
    return {"aligned": aligned,
            "direction": ("long" if core[0] > 0 else "short") if aligned else "—",
            "vote_score": score, "vote_n": len(LUX_VOTE),
            "components": {n: sig.get(n, 0) for n in LUX_VOTE}}


def build_context(symbols: list[str]) -> dict:
    assets = {}
    for s in symbols:
        d = fetch_live(s)
        c = d["candles"]
        oi = open_interest_24h(s) or {}
        fr = d["funding"].rate.iloc[-1] if d["funding"] is not None and len(d["funding"]) else 0.0
        ratio = ((d["flow"].taker_buy / d["flow"].volume.replace(0, np.nan)).tail(24).mean()
                 if d["flow"] is not None else 0.5)  # fallback HL: niente flow → neutro
        assets[s] = {
            "price": float(c.close.iloc[-1]),
            "atr_pct": round(float(atr_pct(c).iloc[-1]) * 100, 2),   # rumore tipico → stop floor
            "chg_24h": float(c.close.iloc[-1] / c.close.iloc[-25] - 1),
            "chg_7d": float(c.close.iloc[-1] / c.close.iloc[-169] - 1),
            "funding_8h": float(fr),
            "funding_apr": float(fr * 3 * 365),
            "taker_buy_ratio_24h": round(float(ratio), 4),
            "regime_7d": str(regimes(c).iloc[-1]),
            "signals": (_sig := signal_states(d)),
            "lux_confluence": lux_confluence(_sig),
            **{k: round(v, 4) if isinstance(v, float) else v for k, v in oi.items()},
        }
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "assets": assets,
        "news": news_headlines()[:25],
        "lessons": recall_lessons(symbols),
    }


def recall_lessons(symbols: list[str], k: int = 10) -> list[dict]:
    """Lezioni dal journal: prima quelle sugli stessi simboli, poi le più recenti."""
    path = ROOT / "paper/lessons.jsonl"
    if not path.exists():
        return []
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    rows.sort(key=lambda r: (r.get("symbol") in symbols, r.get("logged_at", "")), reverse=True)
    return [{"symbol": r.get("symbol"), "verdict": r.get("verdict"),
             "lesson": r.get("lesson"), "tags": r.get("tags", [])} for r in rows[:k]]


def hard_check(p: dict, open_positions: int = 0, atr_by_symbol: dict | None = None) -> list[str]:
    """Strato 1: limiti deterministici. Una violazione = veto, l'LLM non può discutere."""
    errs = []
    if p.get("action") == "no_trade":
        return errs
    if float(p.get("leverage", 99)) > HARD_LIMITS["max_leverage"]:
        errs.append(f"leva {p.get('leverage')} > max {HARD_LIMITS['max_leverage']}")
    if float(p.get("risk_pct", 99)) > HARD_LIMITS["max_risk_per_trade_pct"]:
        errs.append(f"risk_pct {p.get('risk_pct')} > max {HARD_LIMITS['max_risk_per_trade_pct']}")
    lo, hi = HARD_LIMITS["stop_pct_range"]
    stop = float(p.get("stop_pct", 0))
    if not (lo <= stop <= hi):
        errs.append(f"stop_pct {p.get('stop_pct')} fuori range [{lo},{hi}] (stop obbligatorio)")
    # stop dentro il rumore (< 1 ATR) = noise-stop: causa #1 degli execution_issue
    atrp = (atr_by_symbol or {}).get(p.get("symbol"))
    if atrp and atrp > 0:
        floor = HARD_LIMITS["min_stop_atr_mult"] * atrp
        if stop < floor:
            errs.append(f"stop_pct {stop} < {HARD_LIMITS['min_stop_atr_mult']}*ATR ({floor:.2f}%): "
                        f"dentro il rumore, noise-stop")
    if open_positions >= HARD_LIMITS["max_concurrent_positions"]:
        errs.append("max posizioni concorrenti raggiunto")
    if p.get("direction") not in ("long", "short"):
        errs.append("direction mancante")
    if not p.get("thesis") or not p.get("invalidation"):
        errs.append("tesi o invalidazione mancante (obbligatorie)")
    return errs


def log_decision(record: dict) -> None:
    record["logged_at"] = datetime.now(timezone.utc).isoformat()
    DECISIONS.parent.mkdir(exist_ok=True)
    with DECISIONS.open("a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def render_pack(ctx: dict) -> str:
    parts = [f"# Contesto mercato {ctx['ts']}\n## Asset\n{json.dumps(ctx['assets'], indent=1)}",
             "## News (timestampate)\n" + "\n".join(f"- [{n['ts'][:16]}] {n['title']}" for n in ctx["news"]),
             "## Lezioni dal journal\n" + ("\n".join(
                 f"- [{l['verdict']}] {l['symbol']}: {l['lesson']}" for l in ctx["lessons"]) or "(nessuna ancora)")]
    for role, prompt in ROLES.items():
        parts.append(f"\n=== RUOLO: {role.upper()} ===\n{prompt}")
    return "\n".join(parts)


def main() -> None:
    symbols = sys.argv[1].split(",")
    mode = sys.argv[2] if len(sys.argv) > 2 else "auto"

    if mode == "--check":
        proposal = json.loads(Path(sys.argv[3]).read_text())
        errs = hard_check(proposal)
        verdict = "hard_veto" if errs else "passed_hard_limits"
        print(f"{verdict}" + (f": {errs}" if errs else ""))
        log_decision({"stage": "hard_check", "proposal": proposal,
                      "verdict": verdict, "violations": errs})
        return

    ctx = build_context(symbols)
    if mode == "--pack":
        print(render_pack(ctx))
        return

    # full auto via GLM-5.2 (Z.ai Coding Plan): ruoli dal yaml, effort differenziato,
    # self-consistency (N vote) sulla decisione finale dello Strategist.
    brief = _ask_role("analyst", f"CONTESTO:\n{json.dumps(ctx, default=str)}")
    bull = _ask_role("bull", f"BRIEF:\n{brief}")
    bear = _ask_role("bear", f"BRIEF:\n{brief}")
    proposal = _ask_strategist(f"BRIEF:\n{brief}\n\nBULL:\n{bull}\n\nBEAR:\n{bear}")
    atr_by_symbol = {s: a["atr_pct"] for s, a in ctx["assets"].items()}
    errs = hard_check(proposal, atr_by_symbol=atr_by_symbol)
    if errs:
        log_decision({"stage": "final", "proposal": proposal, "verdict": "hard_veto", "violations": errs})
        print(f"HARD VETO: {errs}")
        return
    risk = _ask_role("risk", f"PROPOSTA:\n{json.dumps(proposal)}\n\nBRIEF:\n{brief}")
    log_decision({"stage": "final", "brief": brief, "bull": bull, "bear": bear,
                  "proposal": proposal, "risk": risk})
    print(json.dumps({"proposal": proposal, "risk": risk}, indent=1, default=str))


if __name__ == "__main__":
    main()
