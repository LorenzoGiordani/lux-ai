"""Paper trading di TUTTE le strategie portfolio attive (engine:portfolio).

Runner dedicato per i book cross-asset dollar-neutral: ogni strategia viene
ribilanciata da scripts/portfolio_paper.py. Sostituisce i glob pattern
hard-coded nel cron/workflow — ogni futura portfolio (champion/challenger) viene
inclusa automaticamente via portfolio_active_specs(), niente più zombie per nome
file che non matcha un pattern (com'era xsmom-multihorizon-v1).

Uso: .venv/bin/python scripts/portfolio_all.py
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest.lifecycle import portfolio_active_specs

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    active = portfolio_active_specs()
    if not active:
        print("nessuna strategia portfolio attiva (champion/challenger)")
        return
    print(f"strategie portfolio attive: {len(active)}")
    for path, spec in active:
        sid = spec["id"]
        print(f"\n→ {sid} [{spec['status']}]")
        # una strategia che fallisce non ferma le altre (come backtest_report):
        # niente sys.exit — il deploy della dashboard non deve dipendere da un'unica
        # spec rotta.
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "portfolio_paper.py"), str(path)])
        if r.returncode != 0:
            print(f"  ⚠ {sid} uscito con codice {r.returncode}", file=sys.stderr)


if __name__ == "__main__":
    main()
