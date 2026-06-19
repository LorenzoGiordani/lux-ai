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


def active_specs() -> list[tuple[Path, dict]]:
    """champion + challenger = ciò che gira nel loop paper MECCANICO.
    Esclude engine:desk (strategie LLM-desk, eseguite da runner dedicati,
    es. scripts/geopolitics_paper.py — il runner a segnali le romperebbe)."""
    return [(f, s) for f, s in all_specs()
            if s.get("status") in ("champion", "challenger") and s.get("engine") != "desk"]


def paper_symbols(spec: dict) -> str:
    if spec.get("paper_symbols"):
        ps = spec["paper_symbols"]
        return ",".join(ps) if isinstance(ps, list) else ps
    kinds = spec.get("universe", {}).get("kinds", ["perp"])
    return DEFAULT_SYMBOLS["mixed" if "mixed" in kinds else "perp"]


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
    R-multiple = pnl / capitale a rischio all'apertura — robusto con pochi trade."""
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
                           "r": e.get("pnl_usd", 0.0) / risk if risk > 0 else 0.0})
    n = len(closed)
    if n == 0:
        return {"n_closed": 0, "total_pnl": 0.0, "win_rate": 0.0,
                "mean_r": 0.0, "sharpe_r": 0.0, "open_now": len(opens)}
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
    }


def backtest_dsr(spec: dict) -> float | None:
    """DSR dal backtest salvato nello YAML (gate anti-overfitting), se presente."""
    bt = next(iter(spec.get("backtest", {}).values()), {})
    agg = bt.get("aggregate", {})
    return agg.get("dsr")
