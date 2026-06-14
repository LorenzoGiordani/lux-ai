"""Robustezza del segnale liquidazioni: lo Sharpe più alto di tsmom-liq è un edge reale
o overfit sui 7 mesi crypto? Due test, niente tuning:
1. Griglia parametri (lookback_d × extreme_pct): un edge reale è STABILE su tutta la
   griglia; un overfit funziona solo in 1-2 celle fortunate.
2. Per-simbolo: un edge reale è DIFFUSO su molti coin; un overfit è guidato da 1-2.

Uso:  .venv/bin/python scripts/robustness_liq.py
"""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.evolve import load_data, eval_basket  # noqa: E402
from scripts.research_seeds import CRYPTO, make_spec  # noqa: E402

MONTHS = 7


def spec_for(lb: int, ext: float) -> dict:
    return make_spec({
        "id": f"liq-{lb}-{ext}", "family": "liq", "symbols": CRYPTO, "thesis": "robustezza",
        "signals": [{"name": "tsmom", "params": {"short_h": 168, "long_h": 720}},
                    {"name": "liq_imbalance", "params": {"lookback_d": lb, "extreme_pct": ext}}],
        "entry": {"rule": "tsmom AND liq_imbalance", "direction": "signal_vote"},
        "exit": {"stop_pct": 2.5, "target_r": 3.0, "time_stop_h": 240},
        "risk": {"max_leverage": 1, "risk_per_trade_pct": 0.6, "max_concurrent_positions": 2},
    })


def base_spec() -> dict:
    return make_spec({
        "id": "base", "family": "base", "symbols": CRYPTO, "thesis": "baseline",
        "signals": [{"name": "tsmom", "params": {"short_h": 168, "long_h": 720}}],
        "entry": {"rule": "tsmom", "direction": "follow:tsmom"},
        "exit": {"stop_pct": 2.5, "target_r": 3.0, "time_stop_h": 240},
        "risk": {"max_leverage": 1, "risk_per_trade_pct": 0.6, "max_concurrent_positions": 3},
    })


def main() -> None:
    datasets = {s: load_data(s, MONTHS) for s in CRYPTO.split(",")}
    base = eval_basket(base_spec(), datasets)["aggregate"]["mean_sharpe"]
    print(f"baseline tsmom (crypto): Sharpe {base:.2f}\n")

    print("=== Griglia parametri — Sharpe di tsmom-liq (baseline {:.2f}) ===".format(base))
    print(f"{'lookback_d':>10} | " + " ".join(f"ext{e:>4}" for e in (70, 75, 80, 85)))
    sharpes = []
    for lb in (10, 14, 21, 30, 45):
        row = []
        for ext in (70, 75, 80, 85):
            sh = eval_basket(spec_for(lb, ext), datasets)["aggregate"]["mean_sharpe"]
            row.append(sh); sharpes.append(sh)
        print(f"{lb:>10} | " + " ".join(f"{v:>7.2f}" for v in row))
    arr = np.array(sharpes)
    beats = (arr > base).mean() * 100
    print(f"\ncelle che battono il baseline: {beats:.0f}%  | "
          f"Sharpe griglia: media {arr.mean():.2f}, min {arr.min():.2f}, max {arr.max():.2f}")
    print("→ edge reale se la maggioranza batte il baseline e la dispersione è bassa.\n")

    print("=== Per-simbolo — Sharpe di tsmom-liq (lookback_d=21, ext=75) ===")
    spec = spec_for(21, 75)
    res = eval_basket(spec, datasets)
    per = res.get("per_symbol", {})
    for sym, r in sorted(per.items(), key=lambda kv: kv[1]["metrics"]["sharpe"], reverse=True):
        m = r["metrics"]
        print(f"  {sym:<6} Sharpe {m['sharpe']:>6.2f}  ret {m['total_return']:>+7.1%}  "
              f"trades {m['n_trades']:>4}")
    pos = sum(1 for r in per.values() if r["metrics"]["sharpe"] > 0)
    print(f"\nsimboli con Sharpe positivo: {pos}/{len(per)} "
          f"→ edge diffuso se la maggioranza è positiva, non guidato da 1-2.")


if __name__ == "__main__":
    main()
