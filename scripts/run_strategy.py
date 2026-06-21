"""Esegue un artefatto strategia su un asset: metriche overall, per fold, per regime.

Uso: uv run scripts/run_strategy.py strategies/<file>.yaml BTC [mesi]
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from backtest.engine import Backtest
from backtest.metrics import buy_and_hold, compute, report
from backtest.strategy import compile_strategy, load
from backtest.walkforward import evaluate


def read(path: str) -> pd.DataFrame | None:
    return pd.read_parquet(path) if Path(path).exists() else None


def main() -> None:
    spec_path, symbol = sys.argv[1], sys.argv[2]
    months = int(sys.argv[3]) if len(sys.argv) > 3 else 6

    candles = pd.read_parquet(f"data/candles/{symbol}.parquet").tail(months * 30 * 24).reset_index(drop=True)
    data = {"candles": candles, "symbol": symbol,
            "funding": read(f"data/funding/{symbol}.parquet"),
            "flow": read(f"data/flow/{symbol}.parquet"),
            "news_events": read("data/news/gdelt_events.parquet"),
            "cot": read(f"data/cot/{symbol}.parquet")}

    spec = load(spec_path)
    strat, sigs = compile_strategy(spec, data)
    print(f"{spec['id']} su {symbol}, {len(candles)} candele "
          f"({candles.ts.min():%Y-%m-%d} → {candles.ts.max():%Y-%m-%d})")
    print(f"barre con entry attivo: {int(((sigs != 0).all(axis=1)).sum())}\n")

    bt = Backtest(candles, max_leverage=spec["risk"]["max_leverage"])
    equity = bt.run(strat)

    print(report("strategia", compute(equity, bt.trades)))
    print(report("buy & hold 1x", buy_and_hold(candles)))

    ev = evaluate(equity, candles)
    print(f"\nconsistenza: {ev['consistency']}")
    for name, m in ev["regimes"].items():
        print(f"  {name:<5} ret {m['ret']:+7.2%} | sharpe {m['sharpe']:6.2f} | {m['hours']}h")
    reasons = pd.Series([t["reason"] for t in bt.trades]).value_counts().to_dict() if bt.trades else {}
    print(f"uscite: {reasons}")


if __name__ == "__main__":
    main()
