"""Claude Strategy — strategia ibrida, progettata da zero.

Filosofia (le mie regole, non un clone):
  1. Il SISTEMATICO trova i setup ad alta convinzione — dove le regole battono
     l'intuito. Gate = confluenza di FLUSSO FORZATO: trend (tsmom) e sbilancio
     liquidazioni reali (liq_imbalance) concordi sulla stessa direzione. È l'unico
     edge ortogonale sopravvissuto a tutte le falsificazioni del progetto.
  2. CLAUDE GIUDICA — dove l'LLM aggiunge valore davvero: sintetizzare il contesto
     (regime, funding contro, news, RISCHIO DI CORRELAZIONE col book aperto) e
     decidere qualità/timing/size. MAI come predittore di prezzo (lezione dura del
     progetto: forecast LLM = niente alpha). È un GIUDICE avverso, non un oracolo.
  3. LLM ECONOMICO — una sola chiamata per run, e solo se il gate ha candidati.
     Niente gate → niente costo. Selettività: 0 o 1 trade, 'no_trade' è normale.

Esecuzione riusata: scrive la decisione (taggata claude-strategy-v1) in
decisions.jsonl; la apre scripts/agents_paper.py --account claude-strategy-v1.

Uso (in cron, richiede claude CLI):
  uv run scripts/claude_strategy.py BTC,ETH,SOL,XRP,SUI,NEAR,WLD,ZEC,CRV
  uv run scripts/agents_paper.py --account claude-strategy-v1
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.decide import _ask, build_context, hard_check, log_decision

ACCOUNT = "claude-strategy-v1"

PM_ROLE = (
    "Sei il Portfolio Manager della 'Claude Strategy'. Un filtro sistematico ti passa SOLO "
    "setup ad alta convinzione (trend e liquidazioni reali concordi = flusso forzato nella "
    "stessa direzione). Il tuo compito NON è prevedere il prezzo — l'LLM fallisce lì e il "
    "progetto l'ha dimostrato — ma GIUDICARE da PM avverso: regime di mercato, funding "
    "contrario, qualità/freschezza delle news, e soprattutto il RISCHIO DI CORRELAZIONE con "
    "le posizioni già aperte (non accumulare la stessa scommessa). Sei selettivo: scegli AL "
    "PIÙ un trade fra i candidati, e 'no_trade' è una risposta rispettabile e frequente. "
    "Se entri: direzione allineata alla confluenza (motiva se vai contro); STOP fuori dal "
    "rumore (stop_pct >= atr_pct dell'asset nel contesto, mai più stretto dell'invalidazione); "
    "RR realistico per la classe (crypto ~2, non 3); size_mult 0.5-1.0 secondo la convinzione. "
    "Rispondi SOLO con JSON: {\"action\":\"trade\"|\"no_trade\",\"symbol\":str,"
    "\"direction\":\"long\"|\"short\",\"leverage\":float,\"risk_pct\":float,\"stop_pct\":float,"
    "\"target_r\":float,\"time_stop_h\":int,\"size_mult\":float,\"thesis\":str (falsificabile),"
    "\"invalidation\":str}"
)


def gate_candidates(ctx: dict) -> list[dict]:
    """Setup ad alta convinzione: tsmom e liq_imbalance attivi e CONCORDI."""
    out = []
    for sym, a in ctx["assets"].items():
        sig = a.get("signals", {})
        t, l = sig.get("tsmom", 0), sig.get("liq_imbalance", 0)
        if t != 0 and l != 0 and (t > 0) == (l > 0):
            out.append({"symbol": sym, "direction": "long" if t > 0 else "short",
                        "atr_pct": a.get("atr_pct"), "funding_apr": a.get("funding_apr"),
                        "chg_7d": a.get("chg_7d")})
    return out


def main() -> None:
    symbols = sys.argv[1].split(",")
    ctx = build_context(symbols)
    cands = gate_candidates(ctx)
    if not cands:
        print("Claude Strategy: nessun setup (gate confluenza chiuso) → nessuna chiamata LLM")
        log_decision({"stage": "gate", "strategy": ACCOUNT, "verdict": "no_setup", "candidates": []})
        return
    print(f"Claude Strategy: {len(cands)} candidati dal gate: {[c['symbol'] for c in cands]}")

    open_now = ctx.get("open_positions") or _open_symbols()
    payload = {"candidati": cands, "posizioni_aperte_claude": open_now,
               "contesto": ctx["assets"], "news": ctx.get("news", [])[:15]}
    proposal = _ask(f"{PM_ROLE}\n\nDATI:\n{json.dumps(payload, default=str)}", as_json=True)

    if proposal.get("action") != "trade":
        log_decision({"stage": "final", "strategy": ACCOUNT, "proposal": proposal,
                      "risk": {"verdict": "veto", "size_multiplier": 0.0, "notes": "PM: no_trade"}})
        print("Claude Strategy: no_trade (PM selettivo)")
        return

    atr_by = {s: a["atr_pct"] for s, a in ctx["assets"].items()}
    errs = hard_check(proposal, atr_by_symbol=atr_by)
    if errs:
        log_decision({"stage": "final", "strategy": ACCOUNT, "proposal": proposal,
                      "verdict": "hard_veto", "violations": errs})
        print(f"Claude Strategy HARD VETO: {errs}")
        return

    mult = max(0.0, min(1.0, float(proposal.get("size_mult", 1.0))))
    log_decision({"stage": "final", "strategy": ACCOUNT, "proposal": proposal,
                  "risk": {"verdict": "approve" if mult >= 0.99 else "reduce",
                           "size_multiplier": mult, "notes": "Claude PM layer"}})
    print(f"Claude Strategy → {proposal['direction']} {proposal['symbol']} "
          f"(stop {proposal.get('stop_pct')}%, RR {proposal.get('target_r')}, size×{mult})")


def _open_symbols() -> list[str]:
    from scripts.paper_trade import STATE_FILE
    if not STATE_FILE.exists():
        return []
    st = json.loads(STATE_FILE.read_text()).get(ACCOUNT, {})
    return list(st.get("positions", {}))


if __name__ == "__main__":
    main()
