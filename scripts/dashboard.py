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
    "tsmom-conservative-v1": {"label": "TSMOM conservativo", "tag": "difensivo multi-asset"},
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
    "tsmom-conservative-v1": {
        "nome": "Segui la tendenza — versione prudente",
        "cosa": "Lo stesso motore del «segui la tendenza», ma con il piede leggero sull'acceleratore: "
                "nessuna leva, stop più stretto e meno posizioni aperte insieme. L'idea è rinunciare a "
                "un po' di guadagno potenziale per subire cali molto più contenuti — e ottenere così un "
                "rendimento più stabile nel tempo.",
        "entra": "la direzione dell'ultima settimana e dell'ultimo mese concordano (entrambe su, o entrambe giù)",
        "esce": "stop ravvicinato, obiettivo raggiunto o troppo tempo senza risultato",
        "rischio": "nessuna leva (1x), massimo 0,6% del capitale a rischio per operazione, al più 2 posizioni insieme",
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
    "cot_percentile": "posizionamento estremo dei fondi (report COT)",
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


def asset_class(symbols: str) -> str:
    syms = [s.strip() for s in symbols.split(",") if s.strip()]
    if not syms:
        return "multi-asset"
    xyz = sum(1 for s in syms if s.startswith("xyz_"))
    if xyz == 0:
        return "crypto"
    if xyz == len(syms):
        return "commodities/indici"
    return "multi-asset"


def risk_profile(risk: dict) -> str:
    lev = risk.get("max_leverage", 1)
    rpt = risk.get("risk_per_trade_pct", 1.0)
    if lev <= 1 and rpt <= 0.8:
        return "conservativo"
    if lev >= 2 and rpt >= 1.4:
        return "aggressivo"
    return "bilanciato"


def build_strategies(state: dict) -> list[dict]:
    """Sezione 'Le strategie': tutte le attive (champion+challenger), spiegazione
    curata se disponibile (STRATEGY_INFO) altrimenti derivata dalla tesi nello YAML.
    Auto-include i nuovi ceppi e quelli che il loop evolutivo promuoverà."""
    sys.path.insert(0, str(ROOT))
    from backtest.lifecycle import active_specs, paper_stats, paper_symbols
    out = []
    seen = set()
    for path, spec in active_specs():
        sid = spec["id"]
        seen.add(sid)
        syms = paper_symbols(spec)
        info = STRATEGY_INFO.get(sid)
        if info:
            entry = {"id": sid, **info}
        else:  # derivata: tesi accorciata + entra/esce/rischio dallo YAML
            thesis = " ".join((spec.get("thesis") or "").split())
            entry = {
                "id": sid,
                "nome": ACCOUNT_META.get(sid, {}).get("label", sid),
                "cosa": thesis[:280] + ("…" if len(thesis) > 280 else ""),
                "entra": "segnali: " + ", ".join(s["name"] for s in spec.get("signals", [])),
                "esce": f"stop {spec['exit'].get('stop_pct')}%, target {spec['exit'].get('target_r')}R, "
                        f"tempo max {spec['exit'].get('time_stop_h')}h",
                "rischio": f"leva max {spec['risk'].get('max_leverage')}x, "
                           f"{spec['risk'].get('risk_per_trade_pct')}% a rischio per operazione",
            }
        entry["status"] = spec.get("status", "challenger")
        entry["asset_class"] = asset_class(syms)
        entry["risk_profile"] = risk_profile(spec.get("risk", {}))
        try:
            ps = paper_stats(sid)
            entry["stats"] = {k: ps.get(k) for k in
                              ("n_closed", "sharpe_r", "mean_r", "win_rate", "total_pnl")}
        except Exception:
            entry["stats"] = {}
        out.append(entry)
    # agents-v1 non è un file YAML: aggiungilo se attivo in paper
    if "agents-v1" in state and "agents-v1" not in seen:
        out.append({"id": "agents-v1", **STRATEGY_INFO["agents-v1"],
                    "status": "live", "asset_class": "crypto", "risk_profile": "bilanciato"})
    return out


LUX_MATRIX_SIGNALS = ["tsmom", "liq_imbalance", "kronos_forecast", "smart_money_ratio", "oi_trend"]
LUX_MATRIX_CORE = ["tsmom", "liq_imbalance", "kronos_forecast"]


def signals_matrix(symbols: list[str]) -> list[dict]:
    """Stato live dei segnali LUX per asset + confluenza (aligned). Trasparenza dell'edge."""
    from backtest.signals import SIGNALS
    from pipeline.live import fetch_live
    rows = []
    for s in symbols:
        if s.startswith("xyz_"):
            continue
        try:
            d = fetch_live(s)
            d["symbol"] = s
            vals = {n: int(SIGNALS[n](d).iloc[-1]) for n in LUX_MATRIX_SIGNALS}
        except Exception:
            continue
        core = [vals[n] for n in LUX_MATRIX_CORE]
        aligned = all(v != 0 for v in core) and len({v > 0 for v in core}) == 1
        rows.append({"symbol": s, "signals": vals, "aligned": aligned,
                     "direction": ("long" if core[0] > 0 else "short") if aligned else "—"})
    return rows


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
            "entry_px": round(e["entry_px"], 6), "size_usd": round(e["size_usd"], 2),
            "invalidation": (f"esce da sola se il prezzo va contro del {stop_d:.1f}% (stop), "
                             f"se raggiunge l'obiettivo (target) o se passa troppo tempo"),
            "outcome": outcome,
        })

    dec_out.sort(key=lambda d: d["ts"], reverse=True)  # cronologico inverso

    les_out = [{
        "ts": ts_short(l.get("logged_at", "")), "scope": clean_symbol(l.get("symbol", "")),
        "verdict": l.get("verdict", ""), "lesson": l.get("lesson", ""), "tags": l.get("tags", []),
    } for l in lessons][::-1]

    from backtest.lifecycle import paper_stats
    lineage = []
    files = sorted(ROOT.glob("strategies/*.yaml")) + sorted(ROOT.glob("strategies/generated/*.yaml"))
    for f in files:
        if "candidates" in f.name:
            continue
        s = yaml.safe_load(f.read_text())
        bt = next(iter(s.get("backtest", {}).values()), {})
        agg = bt.get("aggregate") or bt.get("metrics") or {}
        sharpe = agg.get("mean_sharpe", agg.get("sharpe", 0)) or 0
        try:
            ps = paper_stats(s["id"])
        except Exception:
            ps = {}
        lineage.append({"id": s["id"], "parent": s.get("parent"),
                        "status": s.get("status", "candidate"), "sharpe": round(float(sharpe), 2),
                        "sharpe_r": ps.get("sharpe_r"), "n_closed": ps.get("n_closed"),
                        "mean_r": ps.get("mean_r"), "pnl_paper": ps.get("total_pnl"),
                        "note": s.get("evolution", {}).get("notes", "")[:160]})

    # eventi del ciclo di vita (promote/retire/dethrone) — l'evoluzione "sul campo"
    lifecycle = []
    lc_path = ROOT / "paper" / "lifecycle.jsonl"
    if lc_path.exists():
        for l in lc_path.read_text().splitlines()[-50:]:
            if not l.strip():
                continue
            e = json.loads(l)
            st = e.get("stats", {}) or {}
            lifecycle.append({"event": e.get("event"), "strategy": e.get("strategy"),
                              "family": e.get("family"), "by": e.get("by"),
                              "sharpe_r": st.get("sharpe_r"), "n_closed": st.get("n_closed"),
                              "ts": ts_short(e.get("logged_at", ""))})
        lifecycle = lifecycle[::-1]

    events = []
    ev_path = ROOT / "data/news/gdelt_events.parquet"
    if ev_path.exists():
        import pandas as pd
        ev = pd.read_parquet(ev_path).sort_values("ts").tail(15)
        events = [{"ts": ts_short(r.ts), "topic": r.topic, "z": round(float(r.z), 2),
                   "tone": None if pd.isna(r.tone) else round(float(r.tone), 2)}
                  for r in ev.itertuples()][::-1]

    # trading book: open↔close accoppiati dal journal, in ordine cronologico
    def risk_usd(o):  # capitale a rischio all'apertura: distanza stop × size
        return abs(o["stop_px"] / o["entry_px"] - 1) * o["size_usd"]

    def hours_between(a, b):
        import pandas as pd
        try:
            return round(float((pd.Timestamp(ts_short(b)) - pd.Timestamp(ts_short(a)))
                               .total_seconds() / 3600), 1)
        except Exception:
            return None

    book, pending = [], {}
    for e in journal:
        if e.get("type") == "open":
            pending[(e["strategy"], e["symbol"])] = e
        elif e.get("type") == "close":
            o = pending.pop((e["strategy"], e["symbol"]), None)
            if o is None:
                continue
            sign = 1 if o["direction"] == "long" else -1
            closed_at = e.get("ts", e["logged_at"])
            risk = risk_usd(o)
            book.append({
                "strategy": e["strategy"],
                "account_label": ACCOUNT_META.get(e["strategy"], {}).get("label", e["strategy"]),
                "symbol": clean_symbol(e["symbol"]), "direction": o["direction"],
                "entry_px": round(o["entry_px"], 6), "exit_px": round(e["exit_px"], 6),
                "size_usd": round(o["size_usd"], 2), "pnl_usd": round(e.get("pnl_usd", 0), 2),
                "pnl_pct": round(sign * (e["exit_px"] / o["entry_px"] - 1) * 100, 2),
                "risk_usd": round(risk, 2),
                "r_mult": round(e.get("pnl_usd", 0) / risk, 2) if risk > 0 else None,
                "opened_at": ts_short(o["opened_at"]), "closed_at": ts_short(closed_at),
                "duration_h": hours_between(o["opened_at"], closed_at),
                "reason": e.get("reason", ""), "status": "closed",
            })
    for (sid, sym), o in pending.items():  # ancora aperte
        book.append({
            "strategy": sid, "account_label": ACCOUNT_META.get(sid, {}).get("label", sid),
            "symbol": clean_symbol(sym), "direction": o["direction"],
            "entry_px": round(o["entry_px"], 6), "exit_px": None,
            "size_usd": round(o["size_usd"], 2), "pnl_usd": None, "pnl_pct": None,
            "risk_usd": round(risk_usd(o), 2), "r_mult": None,
            "opened_at": ts_short(o["opened_at"]), "closed_at": None, "duration_h": None,
            "reason": "", "status": "open",
        })
    book.sort(key=lambda t: t["opened_at"], reverse=True)

    strategies = build_strategies(state)

    return {
        "updated_utc": f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M}",
        "accounts": accounts, "decisions": dec_out, "lessons": les_out, "lineage": lineage,
        "lifecycle": lifecycle,
        "signals_matrix": signals_matrix("BTC,ETH,SOL,XRP,SUI,NEAR,WLD,ZEC,CRV".split(",")),
        "news_events": events, "strategies": strategies, "tradebook": book,
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
