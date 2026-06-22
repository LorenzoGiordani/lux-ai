"""Chiusura MANUALE di posizioni paper: al prezzo live, con PnL/fee corretti e
log nel journal (reason 'manual_close'). Per togliere subito posizioni che non
hanno senso (indici/commodity col vecchio RR, strategie ritirate) senza aspettare
stop o time-stop.

Selezione (combinabili):
  --non-crypto              chiude tutte le posizioni non-crypto (index/commodity/stock)
  --accounts a,b            svuota interamente questi account
  --symbols X,Y             chiude solo questi simboli
  --dry-run                 mostra cosa farebbe, non tocca nulla

Uso: uv run scripts/close_positions.py --non-crypto --accounts tsmom-liq-v1
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backtest.engine import DEFAULT_SLIPPAGE, HL_TAKER_FEE
from backtest.risk import asset_class_of
from pipeline.live import fetch_live
from scripts.paper_trade import STATE_FILE, log_event


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--non-crypto", action="store_true")
    ap.add_argument("--accounts", default="")
    ap.add_argument("--symbols", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    accts = {x.strip() for x in a.accounts.split(",") if x.strip()}
    syms = {x.strip() for x in a.symbols.split(",") if x.strip()}

    state = json.loads(STATE_FILE.read_text())
    closed = 0
    for acct, adata in state.items():
        for sym in list(adata.get("positions", {})):
            pos = adata["positions"][sym]
            if "notional" in pos:                       # book a portafoglio: non gestito qui
                continue
            hit = (acct in accts) or (sym in syms) or (a.non_crypto and asset_class_of(sym) != "crypto")
            if not hit:
                continue
            try:
                px = float(fetch_live(sym, lookback_h=5)["candles"].close.iloc[-1])
            except Exception as e:
                print(f"  {acct}/{sym}: prezzo non disponibile ({e}) — salto", file=sys.stderr)
                continue
            sign = 1 if pos.get("direction") == "long" else -1
            rem = float(pos.get("remaining", 1.0))
            size = float(pos["size_usd"]) * rem
            exit_px = px * (1 - sign * DEFAULT_SLIPPAGE)
            pnl = size * (exit_px / pos["entry_px"] - 1) * sign - size * HL_TAKER_FEE
            cls = asset_class_of(sym)
            print(f"  {'[dry] ' if a.dry_run else ''}CLOSE {acct}/{sym} ({cls}) {pos.get('direction')} "
                  f"@ {exit_px:.4g} → pnl {pnl:+.2f}$")
            if a.dry_run:
                continue
            adata["equity"] = adata.get("equity", 10_000.0) + pnl
            log_event({"type": "close", "strategy": acct, "symbol": sym, "reason": "manual_close",
                       "exit_px": exit_px, "frac": round(rem, 4), "remaining": 0.0,
                       "pnl_usd": round(pnl, 2), "equity": round(adata["equity"], 2)})
            del adata["positions"][sym]
            closed += 1
    if not a.dry_run:
        STATE_FILE.write_text(json.dumps(state, indent=1, default=str))
    print(f"\n{'(dry-run) ' if a.dry_run else ''}{closed} posizioni chiuse.")


if __name__ == "__main__":
    main()
