"""GLM Regime-Confluence — strategia ibrida progettata da glm-5.2.

Filosofia (le mie scelte, date le lezioni del progetto):
  1. GATE ORTOGONALE — due lenti momentum indipendenti concordano: tsmom
     (trend assoluto, Moskowitz) + xsection_momentum (forza relativa nel basket,
     market-neutral → netta il beta che tsmom si porta dietro). Confluenza
     assoluto+relativo = il move non è solo drift di mercato, è alpha relativo
     confermato. Entrambe validate, ortogonali (IC indipendenti). Diverso da
     lux_confluence (tsmom+liq+kronos) e da claude_strategy (tsmom+liq).
  2. VETO DI REGIME/Evento — news_event attivo (volatilità event-risk, il tono
     è falsificato ma la vol non lo è) O kronos_vol alta (regime imprevedibile)
     O funding_percentile estremo CONTRO direzione (crowding headwind, lezione
     altcoin-exhaustion). Veto hard: niente entry durante burst/crowding.
  3. VOTE DI CONVINZIONE — hmm_regime(trending) + taker_flow + smart_money_ratio
     + oi_trend. Ogni allineamento aggiunge 1 al conviction score (0-4) →
     size_mult 0.5 + 0.125*score. Filtro regime morbido (hmm solo su BTC/ETH:
     score degrada a 0-3 sugli altri, gate resta valido).
  4. LLM AUDITOR DI PORTAFOGLIO — non oracolo, non predittore di prezzo. Il gate
     ha già fissato direzione e conviction. Io giudico SOLO: rischio di
     correlazione col book aperto (non impilare la stessa scommessa su asset
     correlati) e freschezza/cogeneità. Una chiamata, solo se il gate ha
     candidati sopravvissuti al veto. no_trade = risposta normale.
  5. EXIT ROBUSTA — stop ATR-adaptive (2×ATR, floor 1×ATR anti noise-stop,
     lezione altcoin_volatility), target_r 2.0 (crypto, RR2 batte RR3), time_stop
     96h (coerente con tesi momentum 7d, lezione SOL execution_issue).

Esecuzione riusata: scrive decisione (tag glm-regime-confluence-v1) in
decisions.jsonl; la apre agents_paper.py --account glm-regime-confluence-v1.

Uso (cron, fallback LLM integrato in decide._ask):
  uv run scripts/glm_strategy.py BTC,ETH,SOL,XRP,SUI,NEAR,WLD,ZEC,CRV
  uv run scripts/agents_paper.py --account glm-regime-confluence-v1
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.decide import _ask_role, build_context, hard_check, log_decision

ACCOUNT = "glm-regime-confluence-v1"

CORE = ["tsmom", "xsection_momentum"]               # allineati obbligatori (ortogonali)
VETO = ["news_event", "kronos_vol"]                  # attivi → salta entry (event-risk / regime incerto)
# +1 conviction per ogni vote allineato alla direzione del core
VOTES = ["hmm_regime", "taker_flow", "smart_money_ratio", "oi_trend"]

AUDITOR_ROLE = (
    "Sei il Risk Auditor della 'GLM Regime-Confluence'. Un gate sistematico ti passa candidati "
    "con direzione e conviction score già fissati (tsmom + xsection_momentum allineati, veto "
    "event/crowding già applicato). Il tuo compito NON è prevedere il prezzo o dibattere la direzione "
    "(l'edge sistematico lo ha già stabilito) — è GIUDICARE il rischio di CORRELAZIONE con le posizioni "
    "già aperte: non accumulare la stessa scommessa su asset correlati (BTC↔ETH, SOL↔SUI↔NEAR, "
    "settore AI/depin, defi). Sei avverso e selettivo: scegli AL PIÙ un trade, 'no_trade' è "
    "rispettabile e frequente. Rispondi SOLO con JSON: {\"action\":\"trade\"|\"no_trade\","
    "\"symbol\":str,\"direction\":\"long\"|\"short\",\"leverage\":float,\"risk_pct\":float,"
    "\"stop_pct\":float,\"target_r\":float,\"time_stop_h\":int,\"size_mult\":float,"
    "\"thesis\":str (falsificabile),\"invalidation\":str}"
)


def _aligned(a, b):
    return a != 0 and b != 0 and (a > 0) == (b > 0)


# soglia conviction sotto la quale accettiamo tsmom da solo (cache xsection spesso
# assente in cloud se il workflow non rigenera → AND a 2 gambe era sempre chiuso).
# Core allineato (tsmom+xsection) accettato a qualunque conviction; tsmom da solo
# solo se almeno N vote concordano (filtro regime, non collo di bottiglia single-signal).
TSMOM_SOLO_MIN_VOTES = 2


def gate_candidates(ctx: dict) -> list[dict]:
    """Core tsmom+xsection allineati (via preferenziale) OPPURE tsmom + conviction alto
    dai vote (via di fallback quando xsection degrada a neutro). Veto sempre applicato."""
    out = []
    for sym, a in ctx["assets"].items():
        sig = a.get("signals", {})
        t, x = sig.get("tsmom", 0), sig.get("xsection_momentum", 0)
        if t == 0:
            continue
        direction = "long" if t > 0 else "short"
        # veto: event-risk / regime incerto / crowding contro direzione (sempre applicato)
        if any(sig.get(v, 0) != 0 for v in VETO):
            continue
        fp = sig.get("funding_percentile", 0)
        if fp != 0 and ((direction == "long" and fp > 0) or (direction == "short" and fp < 0)):
            continue   # funding estremo CONTRO direzione = crowding headwind
        # conviction vote (prima di filtrare sul core: serve per la via di fallback)
        vote = 0
        for v in VOTES:
            sv = sig.get(v, 0)
            if sv != 0 and (sv > 0) == (t > 0):
                vote += 1
        # via preferenziale: core tsmom+xsection allineati; via fallback: tsmom + conviction
        core_aligned = _aligned(t, x)
        if not core_aligned and vote < TSMOM_SOLO_MIN_VOTES:
            continue
        out.append({"symbol": sym, "direction": direction, "conviction": vote,
                    "core_aligned": core_aligned,
                    "atr_pct": a.get("atr_pct"), "funding_apr": a.get("funding_apr"),
                    "chg_7d": a.get("chg_7d")})
    out.sort(key=lambda c: (c["core_aligned"], c["conviction"]), reverse=True)
    return out


def main() -> None:
    symbols = sys.argv[1].split(",")
    ctx = build_context(symbols)
    cands = gate_candidates(ctx)
    if not cands:
        print("GLM Strategy: nessun candidato (gate core/veto) → no LLM call")
        log_decision({"stage": "gate", "strategy": ACCOUNT, "verdict": "no_setup", "candidates": []})
        return
    print(f"GLM Strategy: {len(cands)} candidati sopravvissuti al gate: "
          f"{[(c['symbol'], c['direction'], c['conviction']) for c in cands]}")

    open_now = _open_symbols()
    payload = {"candidati": cands, "posizioni_aperte_glm": open_now,
               "contesto": ctx["assets"], "news": ctx.get("news", [])[:15]}
    proposal = _ask_role("auditor", f"DATI:\n{json.dumps(payload, default=str)}")

    if proposal.get("action") != "trade":
        log_decision({"stage": "final", "strategy": ACCOUNT, "proposal": proposal,
                      "risk": {"verdict": "veto", "size_multiplier": 0.0, "notes": "auditor: no_trade"}})
        print("GLM Strategy: no_trade (auditor selettivo)")
        return

    atr_by = {s: a["atr_pct"] for s, a in ctx["assets"].items()}
    errs = hard_check(proposal, atr_by_symbol=atr_by)
    if errs:
        log_decision({"stage": "final", "strategy": ACCOUNT, "proposal": proposal,
                      "verdict": "hard_veto", "violations": errs})
        print(f"GLM Strategy HARD VETO: {errs}")
        return

    mult = max(0.0, min(1.0, float(proposal.get("size_mult", 1.0))))
    log_decision({"stage": "final", "strategy": ACCOUNT, "proposal": proposal,
                  "risk": {"verdict": "approve" if mult >= 0.99 else "reduce",
                           "size_multiplier": mult, "notes": "GLM auditor layer"}})
    print(f"GLM Strategy → {proposal['direction']} {proposal['symbol']} "
          f"(stop {proposal.get('stop_pct')}%, RR {proposal.get('target_r')}, size×{mult})")


def _open_symbols() -> list[str]:
    from scripts.paper_trade import STATE_FILE
    if not STATE_FILE.exists():
        return []
    st = json.loads(STATE_FILE.read_text()).get(ACCOUNT, {})
    return list(st.get("positions", {}))


if __name__ == "__main__":
    main()
