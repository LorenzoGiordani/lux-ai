"""Paper trading di TUTTE le strategie attive (champion + challenger).

Sostituisce le chiamate hard-coded: la lista esce dal registry (status nello
YAML), così il loop evolutivo può aggiungere/promuovere strategie senza toccare
lo scheduler. Ogni strategia trada il proprio universo (paper_symbols / kinds).

Uso: .venv/bin/python scripts/paper_all.py
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest.lifecycle import active_specs, paper_symbols

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    active = active_specs()
    if not active:
        print("nessuna strategia attiva (champion/challenger)")
        return
    print(f"strategie attive: {len(active)}")
    for path, spec in active:
        syms = paper_symbols(spec)
        print(f"\n→ {spec['id']} [{spec['status']}] su {syms}")
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "paper_trade.py"),
                            str(path), syms])
        if r.returncode != 0:
            print(f"  ⚠ {spec['id']} uscito con codice {r.returncode}", file=sys.stderr)


if __name__ == "__main__":
    main()
