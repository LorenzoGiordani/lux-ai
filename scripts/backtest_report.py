"""Backtest onesto (basket multi-asset) delle strategie attive → paper/backtests.json.

Regola #5: MAI backtest su singolo asset. Ogni strategia è valutata sul suo basket
dichiarato (paper_symbols), metrica aggregata = media per-symbol (mean Sharpe, non
pooled: una strategia che vince su BTC e perde su 8 alt non passa).

Realismo engine (tutto opt-in, onesto in entrambe le direzioni):
  - funding STORICO reale per-symbol (la costante legacy sovrastimava e nascondeva
    i flip di segno nei mesi bear) — abilitato dove ci sono i dati;
  - slippage size-aware square-root (k=0.5): rivela i Profit Mirage sugli asset
    illiquidi, certifica la robustezza sui liquidi.

Output: paper/backtests.json con, per strategia: aggregate + per-symbol + finestra.
Letto da dashboard.py → sezione "Backtest" della dashboard pubblica.

Uso:
  uv run scripts/backtest_report.py                # 6 mesi trailing, strategie attive + riferimento
  uv run scripts/backtest_report.py --months 12    # finestra più lunga
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest.engine import Backtest
from backtest.metrics import compute
from backtest.strategy import compile_strategy, load
from backtest.walkforward import evaluate

DATA = ROOT / "data"
OUT = ROOT / "paper" / "backtests.json"
MONTHS_DEFAULT = 6
IMPACT_K = 0.5   # square-root market impact (Almgren 2005) — rivela mirage su illiquidi

# Strategie da mostrare: tutte le challenger attive + il benchmark documentato (tsmom).
# Aggiornato leggendo lo status dagli artefatti.
BENCHMARK = "tsmom-v1"


def _read(path: Path) -> pd.DataFrame | None:
    return pd.read_parquet(path) if path.exists() else None


def _dataset(symbol: str, months: int) -> dict | None:
    """Candles + dati ausiliari per un simbolo, finestra trailing coerente."""
    cp = DATA / "candles" / f"{symbol}.parquet"
    if not cp.exists():
        return None
    candles = pd.read_parquet(cp).tail(months * 30 * 24).reset_index(drop=True)
    if len(candles) < 30 * 24:   # troppi pochi dati
        return None
    return {
        "candles": candles, "symbol": symbol,
        "funding": _read(DATA / "funding" / f"{symbol}.parquet"),
        "flow": _read(DATA / "flow" / f"{symbol}.parquet"),
        "cot": _read(DATA / "cot" / f"{symbol}.parquet"),
        "news_events": _read(DATA / "news" / "gdelt_events.parquet"),
    }


def _eval_symbol(spec: dict, data: dict) -> dict | None:
    """Una strategia su un simbolo: metriche + consistenza, con engine realistico."""
    try:
        strat, _ = compile_strategy(spec, data)
    except Exception:
        return None
    bt = Backtest(data["candles"], max_leverage=spec["risk"]["max_leverage"],
                  funding_hist=data.get("funding"), impact_k=IMPACT_K)
    equity = bt.run(strat)
    if equity.empty:
        return None
    m = compute(equity, bt.trades)
    ev = evaluate(equity, data["candles"])
    exits = pd.Series([t["reason"] for t in bt.trades]).value_counts().to_dict() if bt.trades else {}
    return {
        "symbol": data["symbol"],
        "ret": round(m["total_return"], 4),
        "sharpe": round(m["sharpe"], 2),
        "max_dd": round(m["max_drawdown"], 4),
        "trades": m["n_trades"],
        "win_rate": round(m["win_rate"], 3),
        "pf": round(m["profit_factor"], 2) if m["profit_factor"] != float("inf") else None,
        "consistency": ev["consistency"],
        "exits": exits,
    }


def _aggregate(per_symbol: list[dict]) -> dict:
    """Media per-symbol (mai pooled). Robusta a concentrazioni su un asset."""
    n = len(per_symbol)
    if not n:
        return {}
    sharpe = sum(p["sharpe"] for p in per_symbol) / n
    ret = sum(p["ret"] for p in per_symbol) / n
    worst_dd = min(p["max_dd"] for p in per_symbol)
    pos = sum(1 for p in per_symbol if p["ret"] > 0)
    folds_pos = sum(int(p["consistency"].split("/")[0]) for p in per_symbol)
    folds_tot = sum(int(p["consistency"].split("/")[1].split()[0]) for p in per_symbol)
    return {
        "mean_sharpe": round(sharpe, 2),
        "mean_return": round(ret, 4),
        "worst_drawdown": round(worst_dd, 4),
        "positive_symbols": f"{pos}/{n}",
        "consistency": f"{folds_pos}/{folds_tot}",
    }


def backtest_strategy(spec_path: Path, months: int) -> dict | None:
    spec = load(spec_path)
    symbols = [s.strip() for s in str(spec.get("paper_symbols", "")).split(",") if s.strip()]
    if not symbols:
        return None
    per_symbol = []
    for sym in symbols:
        data = _dataset(sym, months)
        if not data:
            continue
        res = _eval_symbol(spec, data)
        if res:
            per_symbol.append(res)
    if not per_symbol:
        return None
    c0 = per_symbol[0]
    window = _dataset(symbols[0], months)["candles"]
    return {
        "id": spec["id"],
        "status": spec.get("status", "?"),
        "thesis": spec.get("thesis", "")[:280],
        "is_benchmark": spec["id"] == BENCHMARK,
        "window": f"{window.ts.min():%Y-%m-%d} → {window.ts.max():%Y-%m-%d}",
        "basket_size": len(per_symbol),
        "aggregate": _aggregate(per_symbol),
        "per_symbol": per_symbol,
    }


def _active_specs() -> list[Path]:
    """Tutte le challenger/attive + il benchmark, ordinate (benchmark per primo)."""
    paths = sorted((ROOT / "strategies").glob("*.yaml")) + sorted((ROOT / "strategies" / "generated").glob("*.yaml"))
    out = []
    for p in paths:
        try:
            s = load(p)
        except Exception:
            continue
        if s.get("id") == BENCHMARK:
            out.append(p)
        elif s.get("status") in ("challenger", "champion", "active", "paper"):
            out.append(p)
    # benchmark davanti, poi le altre per id
    out.sort(key=lambda p: (load(p).get("id") != BENCHMARK, str(p)))
    return out


def main() -> int:
    months = MONTHS_DEFAULT
    if "--months" in sys.argv:
        months = int(sys.argv[sys.argv.index("--months") + 1])

    results = []
    for spec_path in _active_specs():
        r = backtest_strategy(spec_path, months)
        if r:
            print(f"  {r['id']:<32} mean Sharpe {r['aggregate']['mean_sharpe']:5.2f} | "
                  f"ret {r['aggregate']['mean_return']:+6.2%} | "
                  f"{r['aggregate']['positive_symbols']} positivi")
            results.append(r)

    payload = {
        "months": months,
        "impact_k": IMPACT_K,
        "funding_mode": "storico (dove disponibile)",
        "generated_at": pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M UTC"),
        "strategies": results,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    print(f"\nbacktest report ({len(results)} strategie) → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
