"""Valuta artefatti strategia sul basket con walk-forward + gate DSR.

A differenza di run_strategy.py (un solo asset) qui si valuta sull'intero basket
come fa il loop evolutivo: media metriche cross-asset + deflated Sharpe (López de
Prado) contro lo Sharpe atteso dal solo rumore su n_trials. Il DSR usa la varianza
cross-trial di TUTTI gli spec passati insieme (quindi passali tutti in un colpo).

Uso: uv run scripts/eval_specs.py s1.yaml s2.yaml ... [--months 6] [--symbols CSV] [--trials N]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest.stats import deflated_sharpe, sharpe_moments
from backtest.strategy import load
from scripts.evolve import eval_basket, load_data

DEFAULT_SYMBOLS = "BTC,ETH,SOL,XRP,SUI,NEAR,WLD,ZEC,CRV"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("specs", nargs="+")
    ap.add_argument("--months", type=int, default=6)
    ap.add_argument("--symbols", default=DEFAULT_SYMBOLS)
    ap.add_argument("--trials", type=int, default=None,
                    help="n_trials per il DSR (default = n. spec passati)")
    a = ap.parse_args()

    syms = a.symbols.split(",")
    datasets = {s: load_data(s, a.months) for s in syms}
    results = []
    for sp in a.specs:
        spec = load(sp)
        results.append((spec, eval_basket(spec, datasets)))

    trial_srs = [sharpe_moments(r["basket_rets"])["sr"] for _, r in results]   # SR per-periodo per trial
    n_trials = a.trials or len(results)
    print(f"basket {len(syms)} asset, {a.months}m, n_trials={n_trials}\n")
    print(f"{'strategia':<32} {'meanSharpe':>10} {'DSR':>6} {'gate':>5} "
          f"{'meanRet':>9} {'worstDD':>9} {'+sym':>6} {'fold':>7} {'trades':>7}")
    for spec, r in results:
        agg = r["aggregate"]
        d = deflated_sharpe(r["basket_rets"], n_trials, trial_srs)
        gate = "PASS" if d["dsr"] >= 0.95 else "—"
        print(f"{spec['id']:<32} {agg['mean_sharpe']:>10.2f} {d['dsr']:>6.2f} {gate:>5} "
              f"{agg['mean_return']:>+9.2%} {agg['worst_drawdown']:>+9.2%} "
              f"{agg['positive_symbols']:>6} {agg['folds']:>7} {agg['total_trades']:>7}")


if __name__ == "__main__":
    main()
