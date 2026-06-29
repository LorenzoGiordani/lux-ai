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
    "tsmom-liq-v1": {"label": "TSMOM + liquidazioni", "tag": "trend filtrato da liq"},
    "lux-0.1-beta": {"label": "LUX 0.1 beta", "tag": "tripla confluenza"},
    "geopolitics-v1": {"label": "Desk geopolitico", "tag": "news globali cross-asset"},
    "tsmom-atr-v1": {"label": "TSMOM ATR", "tag": "trend + vol-target"},
    "lux-confluence-rr2-v1": {"label": "LUX confluence RR2", "tag": "confluenza 3 core · RR2"},
    "agents-rr2-v1": {"label": "Agenti RR2", "tag": "A/B agenti · RR2"},
    "claude-strategy-v1": {"label": "Claude strategy", "tag": "trend + flow"},
    "xsmom-port-v1": {"label": "Cross-section momentum", "tag": "book market-neutral"},
    "glm-regime-confluence-v1": {"label": "GLM regime confluence", "tag": "2 momentum ortogonali"},
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
    "geopolitics-v1": {
        "nome": "Il desk geopolitico",
        "cosa": "Un desk AI cross-asset che si attiva SOLO quando esplode una notizia "
                "geopolitica rilevante (guerra, sanzioni, conflitti). Allora ragiona sul "
                "canale di trasmissione — una crisi muove prima petrolio e oro, poi il "
                "risk-off colpisce le crypto — e sceglie asset e direzione dal nesso causale, "
                "non dal sentiment delle notizie (che si è dimostrato non predittivo).",
        "entra": "solo durante un evento geopolitico anomalo in corso, se il desk individua un canale chiaro",
        "esce": "stop obbligatorio, target o tesi smentita dall'evoluzione dell'evento",
        "rischio": "limiti nel codice: leva max 2x, max 1% a rischio per operazione, al più 2 posizioni",
    },
    "glm-regime-confluence-v1": {
        "nome": "GLM regime confluence",
        "cosa": "Due lenti momentum ortogonali devono concordare: tsmom (trend assoluto, "
                "Moskowitz-Ooi-Pedersen) e xsection_momentum (forza relativa nel basket, "
                "market-neutral). L'accordo assoluto+relativo segnala alpha confermato, non "
                "drift di mercato. Veto hard su eventi news, volatilità alta e funding estremo "
                "contro direzione. L'LLM (glm-5.2) fa solo da auditor di correlazione col book "
                "aperto, non da oracolo direzionale.",
        "entra": "tsmom + xsection_momentum allineati, veto superato, conviction vote 0-4 sufficiente",
        "esce": "stop 2×ATR, target 2R, time-stop 96h",
        "rischio": "leva max 2x, max 1% a rischio per operazione",
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
    "liq_imbalance": "liquidazioni sbilanciate (cascata possibile)",
    "kronos_forecast": "previsione del modello Kronos concorde",
    "smart_money_ratio": "posizionamento del denaro 'informato'",
    "oi_trend": "open interest conferma la direzione del prezzo",
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
    # riduce al BASE coin canonico per display e matching nel feed: l'LLM emette
    # "SOL/USDT", "SOLUSDT", "SOL-PERP"... e le venue HIP-3 usano "xyz:CL" mentre
    # la decisione corrispondente dice "CL". Senza ridurre entrambi a "CL" il feed
    # non riconcilia la decisione con la posizione reale in state (che memorizza
    # il nome HL completo xyz:CL, necessario a fetch_live).
    # canonical_symbol preserva xyz: (serve a fetch); qui lo strippiamo via.
    from pipeline.live import canonical_symbol
    c = canonical_symbol(s)
    if ":" in c:                     # venue HIP-3: "xyz:CL" -> "CL"
        c = c.split(":", 1)[1]
    c = c.removeprefix("xyz_")       # legacy: "xyz_NATGAS" -> "NATGAS"
    return c


# descrizione sintetica e onesta di un burst news: la pipeline GDELT salva solo
# (ts, topic, z, tone) — niente headline. Costruiamo un contesto leggibile dal
# tema + direzione del tono + intensita', coerente con la filosofia della sezione
# (il tono non predice la direzione; conta la volatilita').
_TOPIC_LABEL = {
    "crypto": "copertura su asset crypto",
    "fed_macro": "focus su decisioni Fed / macro",
    "commodities": "copertura su materie prime",
    "equities": "attenzione sui mercati azionari",
    "geopolitics": "tensione geopolitica",
}


def event_desc(topic: str, z: float, tone) -> str:
    base = _TOPIC_LABEL.get(topic, f"burst sul tema {topic}")
    mag = "forte" if z >= 3 else "marcato" if z >= 2.2 else "lieve"
    if tone is None:
        tone_txt = "tono non disponibile"
    elif tone <= -1.0:
        tone_txt = "tono fortemente negativo (ribassista)"
    elif tone < 0:
        tone_txt = "tono negativo (ribassista)"
    elif tone >= 1.0:
        tone_txt = "tono fortemente positivo (rialzista)"
    else:
        tone_txt = "tono positivo (rialzista)"
    return f"Burst {mag} di {base} ({z:.1f}\u03c3). {tone_txt} \u2014 filtro di rischio attivo, nuove entrate sospese."


def asset_class(symbols: str) -> str:
    syms = [s.strip() for s in symbols.split(",") if s.strip()]
    if not syms:
        return "multi-asset"
    # xyz = stock/commodity HIP-3 (vecchio "xyz_" o dex-qualificato "xyz:")
    xyz = sum(1 for s in syms if s.startswith(("xyz_", "xyz:")))
    n = len(syms)
    if n > 20:  # universe wide (selection top_liquidity): conta, non elencare i symbol
        return f"tutti i perp ({n})" + ("" if xyz == 0 else ", crypto+stock/commodity")
    if xyz == 0:
        return "crypto"
    if xyz == n:
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
    from backtest.lifecycle import all_specs, paper_stats, paper_symbols
    out = []
    seen = set()
    _NON_MECH = ("desk", "portfolio")
    # tutte le spec con YAML: champion/challenger (attive, anche desk/portfolio) o in state
    yaml_specs = list(all_specs())
    in_state_ids = {sid for sid in state}  # qualsiasi conto in state, anche flat
    # una strategia e' "attiva" se ha un conto paper (ha girato almeno una volta) o
    # e' il campione. I challenger promossi nello YAML ma mai attivati nel cron
    # (nessuno state) sono candidati parcheggiate: non conteggiati come attive —
    # restano visibili nell'albero di evoluzione (lineage), non tra i conti vivi.
    specs = [(p, s) for p, s in yaml_specs
             if s["id"] in in_state_ids or s.get("status") == "champion"]
    for path, spec in specs:
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
    # agents-v1 e glm-regime-confluence-v1 non hanno YAML: aggiungili se attivi in state
    for sid in ("agents-v1", "glm-regime-confluence-v1"):
        if sid in state and sid not in seen:
            out.append({"id": sid, **STRATEGY_INFO[sid],
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


def llm_stats() -> dict:
    """Aggrega il tracing del layer LLM (paper/llm_calls.jsonl): chiamate per ruolo,
    latenza media, token, ripartizione per effort, hit di cache. Osservabilità del
    costo/latenza di ogni ruolo — base per ottimizzare effort e prompt."""
    from collections import defaultdict
    p = ROOT / "paper/llm_calls.jsonl"
    if not p.exists():
        return {}
    rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    by_role = defaultdict(lambda: {"n": 0, "lat": 0.0, "tok_in": 0, "tok_out": 0})
    by_effort = defaultdict(int)
    for r in rows:
        u = r.get("usage", {}) or {}
        d = by_role[r.get("role") or "?"]
        d["n"] += 1
        d["lat"] += float(r.get("latency_s", 0) or 0)
        d["tok_in"] += int(u.get("in") or 0)
        d["tok_out"] += int(u.get("out") or 0)
        by_effort[r.get("effort") or "?"] += 1
    roles = [{"role": role, "n": d["n"],
              "avg_lat": round(d["lat"] / d["n"], 1) if d["n"] else 0,
              "tok_in": d["tok_in"], "tok_out": d["tok_out"]}
             for role, d in sorted(by_role.items(), key=lambda kv: -kv[1]["n"])]
    return {"total": len(rows), "roles": roles, "by_effort": dict(by_effort),
            "cached": sum(1 for r in rows if r.get("cached")),
            "tot_tok": sum(d["tok_in"] + d["tok_out"] for d in by_role.values())}


def portfolio_live_view(state: dict) -> list[dict]:
    """Vista live delle strategie engine:portfolio: cosa tengono ora (gambe con
    P&L non realizzato) e cosa guardano (ranking corrente per asset — il segnale
    che decidera' le gambe al prossimo ribilanciamento). Riusa la STESSA logica
    di portfolio_paper.py (xs_momentum_weights + stessi fattori) per coerenza.
    Fetch cached: 9 asset × 1 fetch, poi i segnali si combinano per config."""
    import yaml as _yaml
    import pandas as _pd
    pd = _pd
    from backtest.portfolio import xs_momentum_weights
    from pipeline.live import fetch_live_cached

    pf_specs = []
    for d in (ROOT / "strategies", ROOT / "strategies" / "generated"):
        for f in sorted(d.glob("*.yaml")):
            if "candidates" in f.name:
                continue
            try:
                s = _yaml.safe_load(f.read_text())
            except Exception:
                continue
            if s.get("engine") == "portfolio" and s.get("status") in ("champion", "challenger"):
                pf_specs.append(s)
    if not pf_specs:
        return []

    # basket comune (tutte le portfolio usano gli stessi 9 crypto qui): cache unica
    symbols = sorted({s.strip() for spec in pf_specs
                      for s in str(spec.get("paper_symbols", "")).split(",") if s.strip()})
    # dati per asset: candele cached (lookback ampio per il segnale piu' lungo, 336h)
    px_now, ret_168, vol_72, mh = {}, {}, {}, {}
    for sym in symbols:
        try:
            c = fetch_live_cached(sym, lookback_h=400)["candles"]
        except Exception:
            continue
        if len(c) < 340:
            continue
        px_now[sym] = float(c.close.iloc[-1])
        if float(c.close.iloc[-1 - 168]) > 0:
            ret_168[sym] = float(c.close.iloc[-1] / c.close.iloc[-1 - 168] - 1.0)
        vol_72[sym] = float(c.close.pct_change().iloc[-72:].std())
        # multihorizon: media normalizzata dei rank su 3 orizzonti
        rs = []
        for lb in (96, 168, 336):
            if len(c) > lb:
                rs.append(float(c.close.iloc[-1] / c.close.iloc[-1 - lb] - 1.0))
        mh[sym] = float(sum(rs) / len(rs)) if rs else 0.0

    out = []
    for spec in pf_specs:
        sid = spec["id"]
        st = state.get(sid) or {}
        pf = spec.get("portfolio", {}) or {}
        factors = pf.get("factors")
        # vettore segnale secondo la config della strategia (come portfolio_paper)
        if factors:  # combo: z-score pesato xsmom+highvol
            w = pf.get("weights", [0.5, 0.5])
            sig = {s: ret_168.get(s, 0.0) * w[0] + vol_72.get(s, 0.0) * w[1] for s in symbols}
            s_ser = pd.Series(sig)
            if len(s_ser) >= 3 and s_ser.std() > 0:
                s_ser = (s_ser - s_ser.mean()) / s_ser.std()
            sig_series = s_ser
            factor_label = " + ".join(factors) + f" ({'/'.join(str(x) for x in w)})"
        elif pf.get("factor") == "highvol":
            sig_series = pd.Series({s: vol_72.get(s, 0.0) for s in symbols})
            factor_label = "high-vol (72h)"
        elif pf.get("lookbacks_h"):  # multihorizon
            sig_series = pd.Series({s: mh.get(s, 0.0) for s in symbols})
            factor_label = "momentum multi-H " + str(pf.get("lookbacks_h"))
        else:  # xsmom puro
            sig_series = pd.Series({s: ret_168.get(s, 0.0) for s in symbols})
            factor_label = f"momentum ({pf.get('lookback_h', 168)}h)"
        # pesi target = cosa farebbe al prossimo rebalance (coerente col live)
        w_target = xs_momentum_weights(
            sig_series, long_q=float(pf.get("long_q", 0.66)),
            short_q=float(pf.get("short_q", 0.33)), gross=float(pf.get("gross", 1.0)),
            dollar_neutral=bool(pf.get("dollar_neutral", True)))
        # ranking per asset: side + peso target + valore segnale (forza)
        rank = []
        for s in symbols:
            wt = float(w_target.get(s, 0.0))
            rank.append({"symbol": s, "side": "long" if wt > 1e-9 else ("short" if wt < -1e-9 else "flat"),
                        "weight": round(wt, 4), "signal": round(float(sig_series.get(s, 0.0)), 4)})
        rank.sort(key=lambda r: -abs(r["signal"]))

        # gambe attuali arricchite con prezzo live + P&L non realizzato per gamba
        legs = []
        for s, p in (st.get("positions") or {}).items():
            if "notional" not in p:
                continue
            cs = clean_symbol(s)
            entry = float(p.get("px", 0.0))
            now = px_now.get(cs)
            notional = float(p.get("notional", 0.0))
            # P&L: notional deriva col prezzo; pnl = notional * (now/entry - 1)
            pnl_usd = round(notional * (now / entry - 1.0), 2) if (entry > 0 and now) else None
            pnl_pct = round((now / entry - 1.0) * 100, 2) if (entry > 0 and now) else None
            legs.append({"symbol": cs, "side": "long" if notional >= 0 else "short",
                         "notional_usd": round(notional, 2), "entry_px": round(entry, 6),
                         "px_now": round(now, 6) if now else None,
                         "pnl_usd": pnl_usd, "pnl_pct": pnl_pct})
        legs.sort(key=lambda l: -abs(l["notional_usd"]))

        # prossimo ribilanciamento (countdown)
        last_reb = st.get("last_rebalance_ts", "")
        reb_h = int(pf.get("rebalance_h", 168))
        import pandas as _pd
        try:
            nxt = (_pd.Timestamp(last_reb) + _pd.Timedelta(hours=reb_h)).isoformat() if last_reb else ""
        except Exception:
            nxt = ""
        gross_now = sum(abs(l["notional_usd"]) for l in legs)
        net_now = round(sum(l["notional_usd"] for l in legs), 0)
        out.append({
            "id": sid, "label": ACCOUNT_META.get(sid, {}).get("label", sid),
            "factor": factor_label, "equity": round(st.get("equity", 10000.0), 2),
            "last_rebalance": ts_short(last_reb), "next_rebalance": ts_short(nxt),
            "rebalance_h": reb_h, "gross_usd": round(gross_now, 0), "net_usd": net_now,
            "legs": legs, "signal": rank,
            "equity_curve": [[ts_short(h["ts"]), round(h["eq"], 2)]
                             for h in (st.get("equity_history") or [])],
        })
    out.sort(key=lambda p: p["id"])
    return out


def build_data() -> dict:
    state = json.loads((ROOT / "paper/state.json").read_text()) if (ROOT / "paper/state.json").exists() else {}
    journal = jsonl(ROOT / "paper/journal.jsonl")
    decisions = jsonl(ROOT / "paper/decisions.jsonl")
    lessons = jsonl(ROOT / "paper/lessons.jsonl")

    sys.path.insert(0, str(ROOT))
    from backtest.lifecycle import all_specs
    retired_ids = {s["id"] for _, s in all_specs() if s.get("status") == "retired"}

    accounts = []
    for sid, st in state.items():
        # strategie ritirate senza posizioni aperte: non sono conti vivi, non gonfiano i KPI
        if sid in retired_ids and not st.get("positions"):
            continue
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
                "symbol": clean_symbol(s), "direction": p.get("direction", "long"),
                "entry_px": round(p.get("entry_px", 0), 6), "size_usd": round(p.get("size_usd", 0), 2),
                "stop_px": round(p.get("stop_px", 0), 6), "target_px": round(p.get("target_px", 0), 6),
                "opened_at": ts_short(p.get("opened_at", "")),
                "chart": chart_series(s, p.get("opened_at", "")),
            } for s, p in st.get("positions", {}).items() if "notional" not in p],
            # gambe del book a portafoglio (dollar-neutral): niente stop/target per posizione
            # → fuori dalle card (entry/stop/target=0 davano NaN nel risk/reward JS). Si
            # leggono dalla equity curve; esposte a parte per direzione e notional reali.
            # entry_px = px al ribilanciamento (per P&L non realizzato nel layer live).
            "book": [{"symbol": clean_symbol(s), "side": "long" if p.get("notional", 0) >= 0 else "short",
                      "notional_usd": round(p.get("notional", 0), 2),
                      "entry_px": round(p.get("px", 0), 6)}
                     for s, p in st.get("positions", {}).items() if "notional" in p],
        })

    dec_out = []
    # posizioni REALMENTE aperte in state (sia desk con entry_px SIA gambe del
    # book a portafoglio con notional). Verita' usata per marcare "aperta" nel
    # feed: una decisione/apertura e' aperta solo se la posizione corrispondente
    # e' viva in state, non se "non esiste un close" (altrimenti proposte
    # veto/superate, o gambe di portfolio gia' ribilanciate via, risulterebbero
    # posizioni aperte, slegandosi da Posizioni). Includere anche i book e'
    # indispensabile: le aperture sistematiche dei portfolio (xsmom/highvol)
    # vivono proprio come gambe notional — senza diche non verrebbero mai
    # marcate "aperta" nel feed, staccandosi dalle posizioni reali.
    open_keys = {
        (sid, clean_symbol(sym))
        for sid, st in state.items()
        for sym, p in st.get("positions", {}).items()
        if "notional" in p or p.get("entry_px", 0) > 0
    }
    TRADEABLE = {"approve", "reduce"}
    for d in decisions:
        if d.get("stage") != "final":
            continue
        p = d.get("proposal", {})
        if p.get("action") != "trade":
            continue
        sym = clean_symbol(p.get("symbol", ""))
        acct = d.get("strategy", "agents-v1")   # desk reale: agents-v1 (untagged) o geopolitics-v1 ecc.
        # verdict + note: le decisioni hard_veto non hanno blocco risk, ma un verdict
        # top-level + violations. Normalizziamo *veto → "veto" (filtro/stile esistenti).
        if "risk" in d and isinstance(d["risk"], dict):
            risk = d["risk"]
            risk_verdict = risk.get("verdict", "approve")
            risk_notes = (risk.get("notes", "") or "")[:400]
            size_mult = risk.get("size_multiplier")
        else:
            top = d.get("verdict", "")
            risk_verdict = "veto" if "veto" in str(top) else (top or "approve")
            viol = d.get("violations") or []
            risk_notes = (("Bloccato dal risk gate: " + "; ".join(map(str, viol)))[:400]
                          if viol else "")
            size_mult = None
        # esito: primo close dello STESSO desk sullo stesso simbolo dopo la decisione;
        # altrimenti "aperta" SOLO se la posizione è davvero viva in state e la decisione
        # è tradeable. Le proposte veto/superate/non eseguite non prendono banner.
        closed_match = None
        for e in journal:
            if (e.get("type") == "close" and e.get("strategy") == acct
                    and clean_symbol(e.get("symbol", "")) == sym
                    and e.get("logged_at", "") > d.get("logged_at", "")):
                closed_match = e
                break
        if closed_match:
            outcome = {"closed": True, "reason": closed_match.get("reason"),
                       "pnl_usd": round(closed_match.get("pnl_usd", 0), 2)}
        elif risk_verdict in TRADEABLE and (acct, sym) in open_keys:
            outcome = {"closed": False}
        else:
            outcome = None
        rec = {
            "ts": ts_short(d.get("logged_at", "")), "symbol": sym,
            "direction": p.get("direction"), "account": acct,
            "account_label": ACCOUNT_META.get(acct, {}).get("label", acct),
            "risk_verdict": risk_verdict,
            "risk_notes": risk_notes,
            "thesis": p.get("thesis", ""), "invalidation": p.get("invalidation", ""),
        }
        if outcome is not None:
            rec["outcome"] = outcome
        if size_mult not in (None, 1, 1.0):
            rec["size_multiplier"] = size_mult
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
        # stesso criterio del feed desk: "aperta" solo se la posizione è viva in state
        closed_match = None
        for c in journal:
            if (c.get("type") == "close" and c.get("strategy") == sid
                    and clean_symbol(c.get("symbol", "")) == clean_symbol(e.get("symbol", ""))
                    and c.get("logged_at", "") > e.get("logged_at", "")):
                closed_match = c
                break
        if closed_match:
            outcome = {"closed": True, "reason": closed_match.get("reason"),
                       "pnl_usd": round(closed_match.get("pnl_usd", 0), 2)}
        elif (sid, clean_symbol(e.get("symbol", ""))) in open_keys:
            outcome = {"closed": False}
        else:
            outcome = None
        stop_d = abs(e["stop_px"] / e["entry_px"] - 1) * 100
        rec = {
            "ts": ts_short(e.get("opened_at", e.get("logged_at", ""))),
            "symbol": clean_symbol(e["symbol"]), "direction": e["direction"],
            "account": sid, "account_label": ACCOUNT_META.get(sid, {}).get("label", sid),
            "risk_verdict": "sistema", "thesis": why,
            "entry_px": round(e["entry_px"], 6), "size_usd": round(e["size_usd"], 2),
            "invalidation": (f"esce da sola se il prezzo va contro del {stop_d:.1f}% (stop), "
                             f"se raggiunge l'obiettivo (target) o se passa troppo tempo"),
        }
        if outcome is not None:
            rec["outcome"] = outcome
        dec_out.append(rec)

    dec_out.sort(key=lambda d: d["ts"], reverse=True)  # cronologico inverso

    # dedup banner "aperta": per ogni (account, symbol) con posizione viva, solo la
    # decisione PIÙ RECENTE resta "aperta". Le proposte precedenti sullo stesso
    # simbolo (es. diverse reduce successive su ZEC) diventano "superata" da quella
    # più recente — coerente con una sola card visibile in Posizioni per simbolo.
    seen_open = set()
    for d in dec_out:
        o = d.get("outcome")
        if not o or o.get("closed"):
            continue
        key = (d.get("account"), d.get("symbol"))
        if key in seen_open:
            o["superseded"] = True
        else:
            seen_open.add(key)

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
                   "tone": None if pd.isna(r.tone) else round(float(r.tone), 2),
                   "desc": event_desc(r.topic, float(r.z),
                                       None if pd.isna(r.tone) else float(r.tone))}
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

    backtests = {}
    bt_path = ROOT / "paper" / "backtests.json"
    if bt_path.exists():
        try:
            backtests = json.loads(bt_path.read_text())
        except (json.JSONDecodeError, ValueError) as e:
            # non degenera silenziosamente a {}: logga, cosi' una scrittura
            # troncata (race col backtest report, ormai mitigata dalla scrittura
            # atomica) non fa sparire i backtest senza traccia.
            print(f"[dashboard] backtests.json illeggibile: {e}", file=sys.stderr)
            backtests = {}

    return {
        "updated_utc": f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M}",
        "accounts": accounts, "decisions": dec_out, "lessons": les_out, "lineage": lineage,
        "lifecycle": lifecycle,
        "signals_matrix": signals_matrix("BTC,ETH,SOL,XRP,SUI,NEAR,WLD,ZEC,CRV".split(",")),
        "news_events": events, "strategies": strategies, "tradebook": book,
        "backtests": backtests,
        "llm_stats": llm_stats(),
        "portfolio_live": portfolio_live_view(state),
    }


# Sito multipagina: una pagina per voce di nav. (file, etichetta, [section id]).
# I dati (build_data) sono identici su tutte le pagine → scritti UNA volta in
# data.js (window.__DATA__), che ogni pagina carica via <script src>. Il template
# resta single-file: lo splittiamo in head (shell+nav) / sezioni / tail (footer+JS),
# e ogni pagina = head + le sue sezioni + tail. La sezione #strategia (dettaglio,
# toggle via JS) viaggia con #strategie.
PAGES = [
    ("index.html",        "Stato",        ["stato"]),
    ("strategie.html",    "Strategie",    ["strategie", "strategia"]),
    ("portafogli.html",   "Portafogli",   ["portafogli"]),
    ("backtest.html",     "Backtest",     ["backtest"]),
    ("posizioni.html",    "Posizioni",    ["posizioni"]),
    ("rischio.html",      "Rischio",      ["rischio"]),
    ("decisioni.html",    "Decisioni",    ["decisioni"]),
    ("trading-book.html", "Trading book", ["book"]),
    ("lezioni.html",      "Lezioni",      ["lezioni"]),
    ("evoluzione.html",   "Evoluzione",   ["evoluzione"]),
    ("eventi.html",       "Eventi",       ["eventi"]),
    ("llm.html",          "LLM",          ["llm"]),
]


def _nav_inner(active_file: str) -> str:
    links = "".join(
        f'<a href="{fn}"{" class=\"active\"" if fn == active_file else ""}>{label}</a>'
        for fn, label, _ in PAGES)
    return f'<div class="wrap secnav-inner">\n    {links}\n  </div>'


def main() -> None:
    data = build_data()
    out_dir = ROOT / "dashboard"
    from pipeline.live import atomic_write_text

    # dati condivisi: una volta sola, non 12× embedded
    atomic_write_text(out_dir / "data.js",
                      "window.__DATA__ = "
                      + json.dumps(data, ensure_ascii=False, separators=(",", ":"))
                      + ";\n")

    html = TEMPLATE.read_text()
    # il blob #data del template (placeholder) → riferimento esterno a data.js
    html, n = re.subn(r'<script id="data" type="application/json">.*?</script>',
                      '<script src="data.js"></script>', html, flags=re.DOTALL)
    if n != 1:
        sys.exit("ERRORE: blocco #data non trovato nel template")

    # split head / sezioni / tail attorno a <main>…</main>
    pre, _, post = html.partition("</main>")
    if not post:
        sys.exit("ERRORE: </main> non trovato nel template")
    head, tail = pre[:pre.index("<section id=")], "</main>" + post
    parts = re.split(r"(?=<section id=)", pre[pre.index("<section id="):])
    sections = {m.group(1): p for p in parts
                if (m := re.match(r'<section id="([^"]+)"', p))}

    for fn, _label, ids in PAGES:
        missing = [i for i in ids if i not in sections]
        if missing:
            sys.exit(f"ERRORE: sezioni {missing} non trovate nel template")
        page_head = re.sub(r'<div class="wrap secnav-inner">.*?</div>',
                           lambda _: _nav_inner(fn), head, count=1, flags=re.DOTALL)
        page = page_head + "".join(sections[i] for i in ids) + tail
        atomic_write_text(out_dir / fn, page)

    print(f"dashboard LUX AI → {len(PAGES)} pagine + data.js in {out_dir}")


if __name__ == "__main__":
    main()
