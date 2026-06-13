"""Promozione/retrocessione automatica delle strategie sulla performance PAPER.

Per ogni famiglia (ceppo evolutivo):
  - challenger che batte il champion con campione sufficiente → champion
  - vecchio champion battuto → retired (resta visibile: è la storia)
  - challenger in perdita con campione sufficiente → retired

Gate conservativi (anti-rumore): servono MIN_CLOSED trade chiusi prima di
qualsiasi mossa. Con pochi dati NON promuove nulla — comportamento corretto.
Il paper trading è il gate finale (cfr. FORMAT.md): mai promuovere su backtest.

Uso: .venv/bin/python scripts/promote.py [--min-trades 20] [--dry-run]
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest.lifecycle import (ROOT, all_specs, backtest_dsr, family,
                                paper_stats, set_status)

LIFECYCLE_LOG = ROOT / "paper" / "lifecycle.jsonl"
LESSONS = ROOT / "paper" / "lessons.jsonl"

MIN_SHARPE = 0.3   # sharpe_r minimo per essere "champion material"
MARGIN = 0.2       # il challenger deve battere il champion di questo margine (sharpe_r)


def log_event(rec: dict) -> None:
    rec["logged_at"] = datetime.now(timezone.utc).isoformat()
    LIFECYCLE_LOG.parent.mkdir(exist_ok=True)
    with LIFECYCLE_LOG.open("a") as f:
        f.write(json.dumps(rec) + "\n")


def add_lesson(strategy: str, verdict: str, lesson: str, tags: list[str]) -> None:
    rec = {"trade_key": f"lifecycle|{strategy}|{datetime.now(timezone.utc):%Y-%m-%d}",
           "symbol": "basket", "strategy": strategy, "verdict": verdict,
           "lesson": lesson, "tags": tags,
           "logged_at": datetime.now(timezone.utc).isoformat()}
    with LESSONS.open("a") as f:
        f.write(json.dumps(rec) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-trades", type=int, default=20)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    specs = {s["id"]: (f, s) for f, s in all_specs()
             if s.get("status") in ("champion", "challenger")}
    fams: dict[str, list] = {}
    for sid, (f, s) in specs.items():
        fams.setdefault(family(sid), []).append((f, s, paper_stats(sid)))

    changes = 0
    for fam, members in sorted(fams.items()):
        champ = next((m for m in members if m[1]["status"] == "champion"), None)
        challengers = [m for m in members if m[1]["status"] == "challenger"]
        champ_sharpe = champ[2]["sharpe_r"] if champ else None
        print(f"\n[{fam}] champion={champ[1]['id'] if champ else '—'} "
              f"(sharpe_r {champ_sharpe if champ else 'n/a'}), challenger={len(challengers)}")

        # 1. ritira i challenger chiaramente perdenti (campione sufficiente)
        for f, s, st in challengers:
            print(f"  challenger {s['id']}: {st['n_closed']} chiusi, "
                  f"sharpe_r {st['sharpe_r']}, meanR {st['mean_r']}, PnL {st['total_pnl']}$")
            if st["n_closed"] >= args.min_trades and st["mean_r"] < 0:
                print(f"    → RETIRE (perdente con {st['n_closed']} trade)")
                if not args.dry_run:
                    set_status(f, "retired")
                    log_event({"event": "retire", "strategy": s["id"], "family": fam, "stats": st})
                    add_lesson(s["id"], "thesis_wrong",
                               f"Ritirata da challenger: {st['n_closed']} trade paper, "
                               f"meanR {st['mean_r']} (perdente). Il paper trading ha falsificato l'edge.",
                               ["lifecycle", "retire", "paper"])
                changes += 1

        # 2. miglior challenger qualificato
        qual = [(f, s, st) for f, s, st in challengers
                if st["n_closed"] >= args.min_trades and st["mean_r"] > 0
                and st["sharpe_r"] >= MIN_SHARPE]
        if not qual:
            continue
        best = max(qual, key=lambda m: m[2]["sharpe_r"])
        bf, bs, bst = best

        beats = champ_sharpe is None or bst["sharpe_r"] >= champ_sharpe + MARGIN
        if not beats:
            print(f"  {bs['id']} (sharpe_r {bst['sharpe_r']}) non batte il champion di {MARGIN}")
            continue

        print(f"  → PROMOTE {bs['id']} a champion (sharpe_r {bst['sharpe_r']}, "
              f"DSR backtest {backtest_dsr(bs)})")
        if not args.dry_run:
            if champ:
                set_status(champ[0], "retired")
                log_event({"event": "dethrone", "strategy": champ[1]["id"], "family": fam,
                           "by": bs["id"], "stats": champ[2]})
            set_status(bf, "champion")
            log_event({"event": "promote", "strategy": bs["id"], "family": fam, "stats": bst})
            add_lesson(bs["id"], "thesis_right",
                       f"Promossa a CHAMPION: {bst['n_closed']} trade paper, sharpe_r "
                       f"{bst['sharpe_r']}, win {bst['win_rate']}, PnL {bst['total_pnl']}$. "
                       + (f"Spodesta {champ[1]['id']}." if champ else "Primo champion della famiglia."),
                       ["lifecycle", "promote", "paper", "champion"])
        changes += 1

    print(f"\n{changes} cambi di stato" + (" (dry-run, nessuna modifica)" if args.dry_run else ""))


if __name__ == "__main__":
    main()
