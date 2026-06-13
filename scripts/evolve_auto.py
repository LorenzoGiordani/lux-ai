"""Loop evolutivo AUTOMATICO: per ogni famiglia, evolve il miglior esemplare.

Per ogni ceppo attivo (champion, o miglior challenger se non c'è champion):
  1. LLM genera N mutazioni (registry chiuso di segnali)
  2. ognuna valutata sul basket → gate DSR (deflated Sharpe ≥ soglia)
  3. chi passa il gate E batte il parent → salvata come `challenger`
     (il paper trading la prende in carico al prossimo run)
  4. le altre → `candidate` (archiviate, visibili nell'albero)

Pensato per il cron settimanale. Richiede `claude` CLI (piano Pro).
Uso: .venv/bin/python scripts/evolve_auto.py [--n 4] [--months 6] [--dsr 0.90]
"""

import argparse
import sys
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest.lifecycle import active_specs, family, paper_stats, paper_symbols
from backtest.stats import deflated_sharpe, sharpe_moments
from scripts.evolve import (OUT_DIR, REGISTRY_DOC, ask_claude, eval_basket,
                            load_data, validate)


def pick_parents() -> dict:
    """Un parent per famiglia: il champion, o il miglior challenger per sharpe_r."""
    by_fam: dict[str, list] = {}
    for f, s in active_specs():
        by_fam.setdefault(family(s["id"]), []).append((f, s))
    parents = {}
    for fam, members in by_fam.items():
        champ = next((m for m in members if m[1]["status"] == "champion"), None)
        if champ:
            parents[fam] = champ
        else:
            parents[fam] = max(members, key=lambda m: paper_stats(m[1]["id"])["sharpe_r"])
    return parents


def evolve_family(parent_path: Path, parent: dict, n: int, months: int, dsr_gate: float) -> int:
    symbols = paper_symbols(parent).split(",")
    datasets = {s: load_data(s, months) for s in symbols}
    pe = eval_basket(parent, datasets)
    pa = pe["aggregate"]
    print(f"\n[{family(parent['id'])}] parent {parent['id']}: "
          f"mean_sharpe {pa['mean_sharpe']:.2f}, mean_ret {pa['mean_return']:+.2%}")

    prompt = f"""{REGISTRY_DOC}

PARENT (YAML):
{parent_path.read_text()}

RISULTATI PARENT su basket {','.join(symbols)}, {months} mesi (fee/slippage/funding inclusi):
aggregato: {pa}

Proponi {n} mutazioni in YAML (schema identico al parent). Obiettivo: robustezza
sul basket, non picchi su singolo asset. Puoi usare `entry.veto` (segnali-gate
che sospendono entrate, es. news_event come filtro di volatilità)."""
    try:
        specs = [yaml.safe_load(c["yaml"]) for c in ask_claude(prompt)["candidates"]]
    except Exception as e:
        print(f"  generazione LLM fallita: {e}", file=sys.stderr)
        return 0

    rows = []
    for i, cand in enumerate(specs, 1):
        try:
            spec = validate(cand, parent, i)
            res = eval_basket(spec, datasets)
            rets = res.pop("basket_rets")
            spec["backtest"] = {f"basket_{months}m": res}
            rows.append((spec, res["aggregate"], rets))
        except Exception as e:
            print(f"  candidato {i} scartato: {e}", file=sys.stderr)

    if not rows:
        return 0
    n_prior = len([f for f in OUT_DIR.glob("*.yaml") if "candidates" not in f.name])
    trial_srs = [sharpe_moments(r)["sr"] for _, _, r in rows]
    k = n_prior + len(rows) + 1

    promoted = 0
    for spec, agg, rets in rows:
        d = deflated_sharpe(rets, k, trial_srs)
        agg["dsr"] = round(d["dsr"], 3)
        agg["dsr_sr0_ann"] = d["sr0_ann"]
        passes = d["dsr"] >= dsr_gate and agg["mean_sharpe"] > pa["mean_sharpe"]
        spec["status"] = "challenger" if passes else "candidate"
        if passes:
            spec.setdefault("paper_symbols", ",".join(symbols))
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / f"{spec['id']}.yaml").write_text(
            yaml.safe_dump(spec, sort_keys=False, allow_unicode=True))
        flag = "✓ CHALLENGER" if passes else "· candidate"
        print(f"  {spec['id']:<40} DSR {agg['dsr']:.2f} | sharpe {agg['mean_sharpe']:+.2f} | {flag}")
        promoted += int(passes)
    return promoted


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=4)
    ap.add_argument("--months", type=int, default=6)
    ap.add_argument("--dsr", type=float, default=0.90)
    args = ap.parse_args()

    parents = pick_parents()
    if not parents:
        print("nessun ceppo attivo da evolvere")
        return
    total = 0
    for fam, (pf, ps) in parents.items():
        total += evolve_family(pf, ps, args.n, args.months, args.dsr)
    print(f"\n{total} nuovi challenger generati (gate DSR ≥ {args.dsr})")


if __name__ == "__main__":
    main()
