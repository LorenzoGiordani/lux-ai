"""Pipeline agenti v1 — una decisione di trading end-to-end (Step 3).

Ruoli: Research+Analyst (brief) → Bull vs Bear (debate) → Strategist (proposta
JSON) → hard limit nel codice (veto deterministico, insindacabile) → Risk
Manager LLM (veto qualitativo). Output: decisione nel journal.

Modi:
  uv run scripts/decide.py BTC,ETH,SOL              # full auto via `claude -p`
  uv run scripts/decide.py BTC,ETH,SOL --pack       # stampa contesto+prompt (LLM = sessione Claude Code)
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
from backtest.signals import SIGNALS
from backtest.walkforward import regimes
from pipeline.live import fetch_live, news_headlines, open_interest_24h

DECISIONS = ROOT / "paper/decisions.jsonl"

HARD_LIMITS = {
    "max_leverage": 2.0,
    "max_risk_per_trade_pct": 1.0,
    "stop_pct_range": (0.5, 8.0),
    "max_concurrent_positions": 3,
}

ROLES = {
    "analyst": (
        "Sei il Market Analyst di un desk crypto. Dal contesto (prezzi, funding, OI, "
        "taker flow, segnali, news) produci un brief: 1) regime di mercato complessivo, "
        "2) per ogni asset: lettura quantitativa in 1-2 righe (posizionamento, flussi, struttura), "
        "3) i 2-3 asset con il setup più interessante e perché. Niente raccomandazioni di trade. Max 350 parole."
    ),
    "bull": (
        "Sei il ricercatore BULL. Dal brief dell'Analyst, argomenta la migliore tesi LONG "
        "possibile (asset specifico, catalizzatori, posizionamento). Sii aggressivo ma onesto sui rischi. Max 150 parole."
    ),
    "bear": (
        "Sei il ricercatore BEAR. Dal brief dell'Analyst, argomenta la migliore tesi SHORT "
        "possibile (asset specifico, catalizzatori, posizionamento). Sii aggressivo ma onesto sui rischi. Max 150 parole."
    ),
    "strategist": (
        "Sei lo Strategist. Hai il brief, il dibattito bull/bear e le LEZIONI dal journal "
        "(post-mortem di trade passati): rispettale o motiva esplicitamente perché non si applicano. "
        "Decidi: UN trade o nessuno (nessun trade è una decisione rispettabile). Rispondi SOLO con JSON: "
        '{"action": "trade"|"no_trade", "symbol": str, "direction": "long"|"short", '
        '"leverage": float, "risk_pct": float, "stop_pct": float, "target_r": float, '
        '"time_stop_h": int, "thesis": str (3-4 frasi, falsificabile), "invalidation": str (cosa la smentisce)}'
    ),
    "risk": (
        "Sei il Risk Manager, adversariale per mandato: sei premiato per trovare difetti, "
        "non per accondiscendere. Valuta la proposta: qualità della tesi, timing, correlazione col "
        "portafoglio, funding contro, liquidità. Rispondi SOLO con JSON: "
        '{"verdict": "approve"|"reduce"|"veto", "size_multiplier": float, "notes": str}'
    ),
}


def _ask(prompt: str, as_json: bool = False):
    """Headless Claude Code — piano Pro. Env ANTHROPIC_* rimosso (proxy DashScope in zshrc)."""
    import os
    import subprocess
    env = {k: v for k, v in os.environ.items() if not k.startswith("ANTHROPIC_")}
    if as_json:
        prompt += "\n\nRispondi SOLO con JSON valido, niente markdown fence."
    r = subprocess.run(["claude", "-p", "--output-format", "json"],
                       input=prompt, capture_output=True, text=True, timeout=600, env=env)
    if r.returncode != 0:
        raise RuntimeError(f"claude -p fallito: {r.stderr[:500]}")
    text = json.loads(r.stdout)["result"].strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(text) if as_json else text


def signal_states(data: dict) -> dict:
    return {name: int(fn(data).iloc[-1]) for name, fn in SIGNALS.items()}


def build_context(symbols: list[str]) -> dict:
    assets = {}
    for s in symbols:
        d = fetch_live(s)
        c = d["candles"]
        oi = open_interest_24h(s) or {}
        fr = d["funding"].rate.iloc[-1] if d["funding"] is not None and len(d["funding"]) else 0.0
        ratio = (d["flow"].taker_buy / d["flow"].volume.replace(0, np.nan)).tail(24).mean()
        assets[s] = {
            "price": float(c.close.iloc[-1]),
            "chg_24h": float(c.close.iloc[-1] / c.close.iloc[-25] - 1),
            "chg_7d": float(c.close.iloc[-1] / c.close.iloc[-169] - 1),
            "funding_8h": float(fr),
            "funding_apr": float(fr * 3 * 365),
            "taker_buy_ratio_24h": round(float(ratio), 4),
            "regime_7d": str(regimes(c).iloc[-1]),
            "signals": signal_states(d),
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


def hard_check(p: dict, open_positions: int = 0) -> list[str]:
    """Strato 1: limiti deterministici. Una violazione = veto, l'LLM non può discutere."""
    errs = []
    if p.get("action") == "no_trade":
        return errs
    if float(p.get("leverage", 99)) > HARD_LIMITS["max_leverage"]:
        errs.append(f"leva {p.get('leverage')} > max {HARD_LIMITS['max_leverage']}")
    if float(p.get("risk_pct", 99)) > HARD_LIMITS["max_risk_per_trade_pct"]:
        errs.append(f"risk_pct {p.get('risk_pct')} > max {HARD_LIMITS['max_risk_per_trade_pct']}")
    lo, hi = HARD_LIMITS["stop_pct_range"]
    if not (lo <= float(p.get("stop_pct", 0)) <= hi):
        errs.append(f"stop_pct {p.get('stop_pct')} fuori range [{lo},{hi}] (stop obbligatorio)")
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

    # full auto via claude -p (richiede CLI nativa installata)
    brief = _ask(f"{ROLES['analyst']}\n\nCONTESTO:\n{json.dumps(ctx, default=str)}")
    bull = _ask(f"{ROLES['bull']}\n\nBRIEF:\n{brief}")
    bear = _ask(f"{ROLES['bear']}\n\nBRIEF:\n{brief}")
    proposal = _ask(f"{ROLES['strategist']}\n\nBRIEF:\n{brief}\n\nBULL:\n{bull}\n\nBEAR:\n{bear}", as_json=True)
    errs = hard_check(proposal)
    if errs:
        log_decision({"stage": "final", "proposal": proposal, "verdict": "hard_veto", "violations": errs})
        print(f"HARD VETO: {errs}")
        return
    risk = _ask(f"{ROLES['risk']}\n\nPROPOSTA:\n{json.dumps(proposal)}\n\nBRIEF:\n{brief}", as_json=True)
    log_decision({"stage": "final", "brief": brief, "bull": bull, "bear": bear,
                  "proposal": proposal, "risk": risk})
    print(json.dumps({"proposal": proposal, "risk": risk}, indent=1, default=str))


if __name__ == "__main__":
    main()
