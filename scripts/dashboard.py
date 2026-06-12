"""Dashboard VETRO — inietta i dati reali nel template di design.

Il markup vive in dashboard/template.html (handoff da Claude Design, non
toccarlo per cambiare i dati): qui si costruisce SOLO il blocco JSON
(<script id="data">) dallo stato reale e si scrive dashboard/index.html.
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "dashboard/template.html"
OUT = ROOT / "dashboard/index.html"

ACCOUNT_META = {
    "agents-v1": {"label": "Agenti LLM", "tag": "pipeline decide"},
    "tsmom-v1": {"label": "TSMOM challenger", "tag": "sistematico multi-asset"},
    "funding-squeeze-breakout-g2-g1-g2": {"label": "Funding-squeeze", "tag": "segnali crypto"},
}

# Spiegazioni in linguaggio semplice — sezione "Le strategie" + "perché"
# delle aperture sistematiche nel feed decisioni.
STRATEGY_INFO = {
    "tsmom-v1": {
        "nome": "Segui la tendenza (TSMOM)",
        "cosa": "Compra ciò che sta già salendo da settimane e vende allo scoperto ciò che "
                "sta scendendo. L'idea, documentata sui mercati da decenni: un movimento in "
                "corso tende a continuare più spesso di quanto si inverta di colpo.",
        "entra": "la direzione dell'ultima settimana e dell'ultimo mese concordano (entrambe su, o entrambe giù)",
        "esce": "perdita massima predefinita (stop), obiettivo raggiunto (target) o troppo tempo senza risultato",
        "rischio": "massimo 1% del capitale a rischio per operazione, leva non oltre 2x",
    },
    "funding-squeeze-breakout-g2-g1-g2": {
        "nome": "Caccia allo squeeze (crypto)",
        "cosa": "Quando troppi trader scommettono tutti dallo stesso lato — si vede dal "
                "“funding”, il costo di mantenere aperte le posizioni — e il prezzo rompe il "
                "suo intervallo dopo una fase calma, chi è dal lato sbagliato è costretto a "
                "chiudere in fretta. Quelle chiusure forzate spingono il prezzo: la strategia "
                "cavalca proprio quell'onda.",
        "entra": "affollamento estremo da un lato + prezzo che rompe il range con volumi alti, dopo una fase di calma",
        "esce": "stop, target o tempo massimo scaduto",
        "rischio": "massimo 1% del capitale a rischio per operazione, leva non oltre 2x",
    },
    "agents-v1": {
        "nome": "Il desk degli agenti AI",
        "cosa": "Un team di intelligenze artificiali organizzato come un desk di trading: un "
                "analista legge mercati e notizie, due ricercatori dibattono pro e contro, uno "
                "stratega propone l'operazione e un gestore del rischio — indipendente e con "
                "potere di veto — può bloccarla o ridurla. Ogni errore diventa una lezione "
                "scritta che entra nelle decisioni successive.",
        "entra": "solo se la proposta sopravvive al dibattito e al vaglio del gestore del rischio",
        "esce": "stop obbligatorio su ogni posizione, target o tesi smentita dai fatti",
        "rischio": "limiti fissati nel codice, non negoziabili dall'AI: leva max 2x, max 1% a rischio per operazione",
    },
}

# "Perché" leggibile per le aperture sistematiche (dal nome del segnale scattato)
SIGNAL_IT = {
    "tsmom": "tendenza concorde su settimana e mese",
    "funding_percentile": "posizionamento affollato a un estremo",
    "range_breakout": "prezzo fuori dal range con volumi",
    "taker_flow": "pressione netta degli ordini aggressivi",
    "vol_compression": "volatilità compressa (molla carica)",
    "vwap_zscore": "prezzo molto esteso rispetto alla media pesata",
    "volume_surge": "volumi anomali",
    "news_event": "evento di notizie anomalo in corso",
}


def jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def ts_short(s: str) -> str:
    """Qualsiasi timestamp → 'YYYY-MM-DD HH:MM' (il JS del template lo richiede)."""
    s = str(s).replace("T", " ")
    return s[:16]


def clean_symbol(s: str) -> str:
    return str(s).removeprefix("xyz_")


def chart_series(symbol: str, opened_at: str, pre_h: int = 72) -> list | None:
    """Chiusure orarie da poco prima dell'apertura a ora — per il mini-chart.
    Prova il feed live; fallback sul parquet storico. None se entrambi falliscono."""
    candles = None
    try:
        sys.path.insert(0, str(ROOT))
        from pipeline.live import fetch_live
        candles = fetch_live(symbol, lookback_h=500)["candles"]
    except Exception:
        p = ROOT / f"data/candles/{symbol}.parquet"
        if p.exists():
            import pandas as pd
            candles = pd.read_parquet(p).tail(500)
    if candles is None or candles.empty:
        return None
    import pandas as pd
    ts = pd.to_datetime(candles["ts"])
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_localize(None)
    start = pd.Timestamp(ts_short(opened_at)) - pd.Timedelta(hours=pre_h)
    keep = ts >= start
    pts = [[ts_short(t), round(float(c), 6)] for t, c in zip(ts[keep], candles["close"][keep])]
    step = max(1, len(pts) // 300)
    return pts[::step]


def build_data() -> dict:
    state = json.loads((ROOT / "paper/state.json").read_text()) if (ROOT / "paper/state.json").exists() else {}
    journal = jsonl(ROOT / "paper/journal.jsonl")
    decisions = jsonl(ROOT / "paper/decisions.jsonl")
    lessons = jsonl(ROOT / "paper/lessons.jsonl")

    accounts = []
    for sid, st in state.items():
        meta = ACCOUNT_META.get(sid, {"label": sid, "tag": ""})
        closes = [e for e in journal if e.get("type") == "close" and e.get("strategy") == sid]
        curve = [[ts_short(e["logged_at"]), round(e["equity"], 2)] for e in journal
                 if e.get("type") == "heartbeat" and e.get("strategy") == sid]
        accounts.append({
            "id": sid, "label": meta["label"], "tag": meta["tag"],
            "equity": round(st["equity"], 2),
            "pnl_realized": round(sum(e.get("pnl_usd", 0) for e in closes), 2),
            "trades_closed": len(closes),
            "wins": sum(1 for e in closes if e.get("pnl_usd", 0) > 0),
            "equity_curve": curve,
            "positions": [{
                "symbol": clean_symbol(s), "direction": p["direction"],
                "entry_px": round(p["entry_px"], 6), "size_usd": round(p["size_usd"], 2),
                "stop_px": round(p["stop_px"], 6), "target_px": round(p["target_px"], 6),
                "opened_at": ts_short(p["opened_at"]),
                "chart": chart_series(s, p["opened_at"]),
            } for s, p in st.get("positions", {}).items()],
        })

    dec_out = []
    for d in decisions:
        if d.get("stage") != "final":
            continue
        p = d.get("proposal", {})
        if p.get("action") != "trade":
            continue
        risk = d.get("risk", {})
        sym = clean_symbol(p.get("symbol", ""))
        # esito: primo close di agents-v1 sullo stesso simbolo dopo la decisione
        outcome = {"closed": False}
        for e in journal:
            if (e.get("type") == "close" and e.get("strategy") == "agents-v1"
                    and clean_symbol(e.get("symbol", "")) == sym
                    and e.get("logged_at", "") > d.get("logged_at", "")):
                outcome = {"closed": True, "reason": e.get("reason"),
                           "pnl_usd": round(e.get("pnl_usd", 0), 2)}
                break
        rec = {
            "ts": ts_short(d.get("logged_at", "")), "symbol": sym,
            "direction": p.get("direction"), "account": "agents-v1",
            "risk_verdict": risk.get("verdict", "approve"),
            "thesis": p.get("thesis", ""), "invalidation": p.get("invalidation", ""),
            "outcome": outcome,
        }
        if risk.get("size_multiplier") not in (None, 1, 1.0):
            rec["size_multiplier"] = risk["size_multiplier"]
        dec_out.append(rec)

    # aperture sistematiche (challenger) nel feed, col perché in parole semplici
    # (agents-v1 escluso: le sue decisioni sono già sopra, con tesi completa)
    for e in journal:
        if e.get("type") != "open" or e.get("strategy") == "agents-v1":
            continue
        sid = e.get("strategy", "")
        info = STRATEGY_INFO.get(sid, {})
        fired = [SIGNAL_IT.get(k, k) for k, v in e.get("signals_last", {}).items() if v]
        why = (f"Il sistema «{info.get('nome', sid)}» ha aperto {e['direction']} su "
               f"{clean_symbol(e['symbol'])}: {', '.join(fired) or 'condizioni della strategia soddisfatte'}.")
        outcome = {"closed": False}
        for c in journal:
            if (c.get("type") == "close" and c.get("strategy") == sid
                    and c.get("symbol") == e.get("symbol")
                    and c.get("logged_at", "") > e.get("logged_at", "")):
                outcome = {"closed": True, "reason": c.get("reason"),
                           "pnl_usd": round(c.get("pnl_usd", 0), 2)}
                break
        stop_d = abs(e["stop_px"] / e["entry_px"] - 1) * 100
        dec_out.append({
            "ts": ts_short(e.get("opened_at", e.get("logged_at", ""))),
            "symbol": clean_symbol(e["symbol"]), "direction": e["direction"],
            "account": sid, "account_label": ACCOUNT_META.get(sid, {}).get("label", sid),
            "risk_verdict": "sistema", "thesis": why,
            "invalidation": (f"esce da sola se il prezzo va contro del {stop_d:.1f}% (stop), "
                             f"se raggiunge l'obiettivo (target) o se passa troppo tempo"),
            "outcome": outcome,
        })

    dec_out.sort(key=lambda d: d["ts"], reverse=True)  # cronologico inverso

    les_out = [{
        "ts": ts_short(l.get("logged_at", "")), "scope": clean_symbol(l.get("symbol", "")),
        "verdict": l.get("verdict", ""), "lesson": l.get("lesson", ""), "tags": l.get("tags", []),
    } for l in lessons][::-1]

    lineage = []
    files = sorted(ROOT.glob("strategies/*.yaml")) + sorted(ROOT.glob("strategies/generated/*.yaml"))
    for f in files:
        if "candidates" in f.name:
            continue
        s = yaml.safe_load(f.read_text())
        bt = next(iter(s.get("backtest", {}).values()), {})
        agg = bt.get("aggregate") or bt.get("metrics") or {}
        sharpe = agg.get("mean_sharpe", agg.get("sharpe", 0)) or 0
        lineage.append({"id": s["id"], "parent": s.get("parent"),
                        "status": s.get("status", "candidate"), "sharpe": round(float(sharpe), 2),
                        "note": s.get("evolution", {}).get("notes", "")[:160]})

    events = []
    ev_path = ROOT / "data/news/gdelt_events.parquet"
    if ev_path.exists():
        import pandas as pd
        ev = pd.read_parquet(ev_path).sort_values("ts").tail(15)
        events = [{"ts": ts_short(r.ts), "topic": r.topic, "z": round(float(r.z), 2),
                   "tone": None if pd.isna(r.tone) else round(float(r.tone), 2)}
                  for r in ev.itertuples()][::-1]

    strategies = [{"id": sid, **info} for sid, info in STRATEGY_INFO.items()
                  if sid in state]

    return {
        "updated_utc": f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M}",
        "accounts": accounts, "decisions": dec_out, "lessons": les_out, "lineage": lineage,
        "news_events": events, "strategies": strategies,
    }


def main() -> None:
    data = build_data()
    html = TEMPLATE.read_text()
    block = f'<script id="data" type="application/json">\n{json.dumps(data, ensure_ascii=False, indent=1)}\n</script>'
    out, n = re.subn(r'<script id="data" type="application/json">.*?</script>', block, html, flags=re.DOTALL)
    if n != 1:
        sys.exit("ERRORE: blocco #data non trovato nel template")
    OUT.write_text(out)
    print(f"dashboard LUX AI → {OUT}")


if __name__ == "__main__":
    main()
