"""Exit-check real-time (TP/SL). Gira spesso, lanciato dal Worker CF SOLO quando un
livello è sfiorato → minuti Actions quasi nulli. Per ogni posizione aperta valuta
stop/target sulla candela in formazione (come un vero ordine exchange) e chiude subito.

SOLO uscite: niente segnali, niente ingressi, niente LLM. Il time-stop (basato sul
tempo, non sul prezzo) resta all'hourly run — qui non urge.

Strategie ritirate (status YAML = retired): chiude tutte le posizioni al prezzo
attuale con reason="retired". Il loop evolutivo ritira la spec ma state.json
conserva il conto + posizioni aperte → senza questo, restano posizioni zombie
che incidono sull'equity display ma la strategia non è più attiva.

Uso: uv run scripts/paper_exits.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest.lifecycle import all_specs
from pipeline.live import atomic_write_text, fetch_live
from scripts.paper_trade import STATE_FILE, _book_fill, update_position

NO_TIME_STOP = 10_000_000  # ore: le uscite a tempo le gestisce l'hourly run, non questo check


def main() -> None:
    if not STATE_FILE.exists():
        print("nessuno stato")
        return
    state = json.loads(STATE_FILE.read_text())
    retired_ids = {s["id"] for _, s in all_specs() if s.get("status") == "retired"}
    closed = 0
    for sid, st in state.items():
        is_retired = sid in retired_ids
        for sym in list(st.get("positions", {})):
            pos = st["positions"][sym]
            if "notional" in pos or "stop_px" not in pos:
                continue   # gamba book a portafoglio (engine:portfolio): la gestisce il rebalance, non lo stop/target
            try:
                data = fetch_live(sym)
            except Exception as e:
                print(f"  {sid}/{sym}: fetch fallito ({e})", file=sys.stderr)
                continue
            if is_retired:
                # strategia ritirata: chiudi al mercato, niente più gestione
                if "sign" not in pos:
                    pos["sign"] = 1 if pos.get("direction") == "long" else -1
                    pos.setdefault("remaining", 1.0)
                px = float(data["candles"]["close"].iloc[-1]) if len(data["candles"]) else pos["entry_px"]
                pos["_last_ts"] = str(data["candles"]["ts"].iloc[-1]) if len(data["candles"]) else None
                st["equity"] = _book_fill(pos, pos.get("remaining", 1.0), px, "retired", st["equity"])
                del st["positions"][sym]
                closed += 1
                continue
            newpos, st["equity"] = update_position(pos, data["candles"], NO_TIME_STOP,
                                                   st["equity"], data.get("forming"))
            if newpos is None:
                del st["positions"][sym]
                closed += 1
            else:
                st["positions"][sym] = newpos  # checked_until in-memory, persistito solo se c'è una chiusura

    if closed:
        atomic_write_text(STATE_FILE, json.dumps(state, indent=1, default=str))
        print(f"exit-check: {closed} posizioni chiuse")
    else:
        print("exit-check: nessuna uscita")


if __name__ == "__main__":
    main()
