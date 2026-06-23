"""Ciclo di vita delle strategie: registry, famiglie, performance paper.

Status: candidate → challenger (paper trading) → champion (il migliore della
famiglia) → retired. Una "famiglia" raggruppa le mutazioni di uno stesso ceppo
(prefisso dell'id prima di -gN/-vN). promote.py e evolve_auto.py si appoggiano qui.
"""

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
STRAT_DIRS = [ROOT / "strategies", ROOT / "strategies" / "generated"]
JOURNAL = ROOT / "paper" / "journal.jsonl"

# universo paper di default per "kind" (HL liquidi); override con paper_symbols nello YAML
DEFAULT_SYMBOLS = {
    "perp": "BTC,ETH,SOL,XRP,SUI,NEAR,WLD,ZEC,CRV",
    "mixed": "BTC,ETH,xyz_GOLD,xyz_CL,xyz_BRENTOIL,xyz_SILVER,xyz_SP500,xyz_MU",
}


def family(strategy_id: str) -> str:
    """Ceppo evolutivo: id senza i suffissi di generazione/versione."""
    return re.split(r"-(?:g\d+|v\d+)", strategy_id)[0]


def all_specs() -> list[tuple[Path, dict]]:
    out = []
    for d in STRAT_DIRS:
        for f in sorted(d.glob("*.yaml")):
            if "candidates" in f.name:
                continue
            try:
                out.append((f, yaml.safe_load(f.read_text())))
            except Exception:
                continue
    return out


NON_MECHANICAL_ENGINES = ("desk", "portfolio")   # girano via runner dedicati, non il loop a segnali


def active_specs() -> list[tuple[Path, dict]]:
    """champion + challenger = ciò che gira nel loop paper MECCANICO.
    Esclude engine:desk (LLM-desk, es. scripts/geopolitics_paper.py) e
    engine:portfolio (book cross-asset, scripts/portfolio_paper.py): il runner a
    segnali per-simbolo le romperebbe."""
    return [(f, s) for f, s in all_specs()
            if s.get("status") in ("champion", "challenger")
            and s.get("engine") not in NON_MECHANICAL_ENGINES]


def paper_symbols(spec: dict) -> str:
    uni = spec.get("universe", {})
    # nomi da escludere a prescindere (curati a mano: asset dove i segnali non hanno
    # edge, post-mortem ripetuti — es. governance/microcap alta-beta). Lista o CSV.
    excl = uni.get("exclude", [])
    excl = set(x.strip() for x in (excl.split(",") if isinstance(excl, str) else excl))
    # esclusione per CLASSE (crypto|index|commodity|stock): robusta ai nomi duplicati
    # (xyz_CL vs xyz:CL). Es. le strategie trend escludono `index` (il trend perde
    # sugli indici: backtest tsmom su SP500 Sharpe -5.5).
    excl_classes = set(uni.get("exclude_classes", []))
    from backtest.risk import asset_class_of

    def _filter(csv: str) -> str:
        return ",".join(s for s in csv.split(",")
                        if s and s not in excl and asset_class_of(s) not in excl_classes)

    # selezione dinamica: tutti i perp core liquidi, risolti live da HL ad ogni run
    # (la lista si auto-aggiorna; ha priorita sull'eventuale paper_symbols esplicito)
    if uni.get("selection") in ("top_liquidity", "all_perps"):
        from pipeline.live import all_perp_symbols
        syms = all_perp_symbols(uni.get("min_day_volume_usd", 1_000_000))
        if syms:
            return _filter(syms)
        # API HL muta: fallback su esplicito/default sotto, mai trade-su-niente
    if spec.get("paper_symbols"):
        ps = spec["paper_symbols"]
        return _filter(",".join(ps) if isinstance(ps, list) else ps)
    kinds = uni.get("kinds", ["perp"])
    return _filter(DEFAULT_SYMBOLS["mixed" if "mixed" in kinds else "perp"])


def set_status(path: Path, status: str) -> None:
    spec = yaml.safe_load(path.read_text())
    spec["status"] = status
    path.write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True))


def _journal() -> list[dict]:
    if not JOURNAL.exists():
        return []
    return [json.loads(l) for l in JOURNAL.read_text().splitlines() if l.strip()]


def paper_stats(strategy_id: str) -> dict:
    """Performance paper realizzata di una strategia, da open↔close del journal.
    R-multiple = pnl / capitale a rischio all'apertura — robusto con pochi trade.
    equity_dd_pct = drawdown corrente vs baseline $10k (da state.json): gate
    precoce per ritirare strategie in perdita grave anche con pochi trade chiusi.
    basket_sharpe_r / basket_mean_r = mean Sharpe/mean R **per-symbol** poi
    mediato sul basket (regola 5): una strategia che vince su 1 asset e perde
    sugli altri non passa — il pooled stat maschererebbe la concentrazione."""
    j = _journal()
    opens, closed = {}, []
    for e in j:
        if e.get("strategy") != strategy_id:
            continue
        if e.get("type") == "open":
            opens[e["symbol"]] = e
        elif e.get("type") == "close":
            o = opens.pop(e["symbol"], None)
            if not o:
                continue
            risk = abs(o["stop_px"] / o["entry_px"] - 1) * o["size_usd"]
            closed.append({"pnl": e.get("pnl_usd", 0.0),
                           "r": e.get("pnl_usd", 0.0) / risk if risk > 0 else 0.0,
                           "symbol": e.get("symbol", "")})
    n = len(closed)
    # drawdown corrente da state.json (equity unrealized incluse posizioni aperte)
    state_path = ROOT / "paper" / "state.json"
    equity_dd_pct = 0.0
    if state_path.exists():
        try:
            st = json.loads(state_path.read_text())
            eq = st.get(strategy_id, {}).get("equity")
            if eq is not None:
                equity_dd_pct = round((eq - 10000.0) / 10000.0 * 100, 2)
        except Exception:
            pass
    # per-symbol R-multiples → basket Sharpe/mean R (regola 5: mean per-asset, non pooled)
    by_symbol: dict[str, list[float]] = {}
    for c in closed:
        by_symbol.setdefault(c["symbol"], []).append(c["r"])
    per_symbol_mean = {s: sum(rs) / len(rs) for s, rs in by_symbol.items() if rs}
    basket_mean_r = round(sum(per_symbol_mean.values()) / len(per_symbol_mean), 3) if per_symbol_mean else 0.0
    per_symbol_sharpe = []
    for s, rs in by_symbol.items():
        if len(rs) < 2:
            continue   # Sharpe richiede ≥2 trade per stimare la deviazione
        m = sum(rs) / len(rs)
        sd = (sum((r - m) ** 2 for r in rs) / (len(rs) - 1)) ** 0.5
        per_symbol_sharpe.append(m / sd * (len(rs) ** 0.5) if sd > 0 else 0.0)
    basket_sharpe_r = round(sum(per_symbol_sharpe) / len(per_symbol_sharpe), 3) if per_symbol_sharpe else 0.0
    if n == 0:
        return {"n_closed": 0, "total_pnl": 0.0, "win_rate": 0.0,
                "mean_r": 0.0, "sharpe_r": 0.0, "open_now": len(opens),
                "equity_dd_pct": equity_dd_pct,
                "basket_mean_r": basket_mean_r, "basket_sharpe_r": basket_sharpe_r,
                "symbols_traded": len(by_symbol)}
    rs = [c["r"] for c in closed]
    mean_r = sum(rs) / n
    sd = (sum((r - mean_r) ** 2 for r in rs) / (n - 1)) ** 0.5 if n > 1 else 0.0
    return {
        "n_closed": n,
        "total_pnl": round(sum(c["pnl"] for c in closed), 2),
        "win_rate": round(sum(1 for c in closed if c["pnl"] > 0) / n, 3),
        "mean_r": round(mean_r, 3),
        "sharpe_r": round(mean_r / sd * (n ** 0.5), 3) if sd > 0 else 0.0,
        "open_now": len(opens),
        "equity_dd_pct": equity_dd_pct,
        "basket_mean_r": basket_mean_r,
        "basket_sharpe_r": basket_sharpe_r,
        "symbols_traded": len(by_symbol),
    }


def backtest_dsr(spec: dict) -> float | None:
    """DSR dal backtest salvato nello YAML (gate anti-overfitting), se presente."""
    bt = next(iter(spec.get("backtest", {}).values()), {})
    agg = bt.get("aggregate", {})
    return agg.get("dsr")


# Global caps per strategie meccaniche (regola 3). I desk LLM hanno HARD_LIMITS
# più stretti in decide.py. Le meccaniche diversificano su basket → caps più
# larghi ma bounded. Override per-asset-class consentito con commento nello YAML.
GLOBAL_RISK_CAPS = {
    "max_leverage": 4,            # >4 = rischio eccessivo anche su low-vol
    "max_concurrent_positions": 12,  # >12 = over-diversification, niente edge
    "max_risk_per_trade_pct": 2.0,   # >2% = risk-of-ruin non trascurabile
}


def validate_spec_risk(spec: dict) -> list[str]:
    """Valida il blocco risk di una strategia meccanica contro i global caps.
    Ritorna lista di warning (vuota = OK). Non blocca il runner (così il loop
    evolutivo può esplorare), ma paper_all.py warna e l'audit le surfaces."""
    warnings = []
    risk = spec.get("risk", {})
    if not risk:
        return ["blocco risk mancante"]
    sid = spec.get("id", "?")
    lev = float(risk.get("max_leverage", 2))
    if lev > GLOBAL_RISK_CAPS["max_leverage"]:
        warnings.append(f"max_leverage {lev} > cap {GLOBAL_RISK_CAPS['max_leverage']}")
    conc = int(risk.get("max_concurrent_positions", 1))
    if conc > GLOBAL_RISK_CAPS["max_concurrent_positions"]:
        warnings.append(f"max_concurrent_positions {conc} > cap {GLOBAL_RISK_CAPS['max_concurrent_positions']}")
    rpt = float(risk.get("risk_per_trade_pct", 1.0))
    if rpt > GLOBAL_RISK_CAPS["max_risk_per_trade_pct"]:
        warnings.append(f"risk_per_trade_pct {rpt} > cap {GLOBAL_RISK_CAPS['max_risk_per_trade_pct']}")
    # override per-asset-class nel blocco exit.by_class (es. stock low-vol leva 4)
    by_class = spec.get("exit", {}).get("by_class", {})
    for cls, cfg in by_class.items():
        if isinstance(cfg, dict) and "max_leverage" in cfg:
            cl = float(cfg["max_leverage"])
            if cl > GLOBAL_RISK_CAPS["max_leverage"]:
                warnings.append(f"by_class.{cls}.max_leverage {cl} > cap {GLOBAL_RISK_CAPS['max_leverage']} "
                                f"(consentito con commento justification nello YAML)")
    return warnings
