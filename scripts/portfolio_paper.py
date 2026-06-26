"""Executor paper per strategie a PORTAFOGLIO (engine: portfolio).

Tiene un book cross-asset con pesi continui (es. cross-sectional momentum
dollar-neutral) e ribilancia ogni `rebalance_h`. Diverso dal loop per-simbolo
(paper_trade.py): niente stop intrabar per posizione — il rischio è gross
leverage + dollar-neutrality + ribilanciamento. Mark-to-market a ogni run.

Stato in paper/state.json sotto l'id della strategia; eventi in journal.
Stesse fee/slippage dell'engine. Account fittizio 10k$, prezzi reali HL.

Uso: uv run scripts/portfolio_paper.py strategies/generated/xsmom-port-v1.yaml
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backtest.engine import DEFAULT_SLIPPAGE, HL_TAKER_FEE
from backtest.portfolio import xs_momentum_weights
from backtest.strategy import load
from pipeline.live import fetch_live
from scripts.paper_trade import STATE_FILE, log_event

COST = HL_TAKER_FEE + DEFAULT_SLIPPAGE


def trailing_returns(symbols: list[str], lookback_h: int,
                    multi_horizon: list[int] | None = None) -> tuple[pd.Series, dict]:
    """Ritorno trailing per simbolo + ultimo prezzo. Salta i simboli senza dati.
    multi_horizon: se passato ([96,168,336]), ritorna la MEDIA normalizzata dei rank
    su piu' orizzonti (xsmom-multihorizon)."""
    if multi_horizon:
        # media dei rank cross-section normalizzati su ogni orizzonte
        rank_acc, px = {}, {}
        for s in symbols:
            try:
                c = fetch_live(s, lookback_h=max(multi_horizon) + 5)["candles"]
            except Exception as e:
                print(f"  {s}: fetch fallito ({e})", file=sys.stderr)
                continue
            px[s] = float(c.close.iloc[-1])
            rank_acc[s] = []
            for lb in multi_horizon:
                if len(c) > lb:
                    rank_acc[s].append(float(c.close.iloc[-1] / c.close.iloc[-1 - lb] - 1.0))
        if len(rank_acc) < 3:
            return pd.Series(dtype=float), px
        # media dei ritorni trailing normalizzati per asset (proxy multi-orizzonte onesto)
        rets = {s: float(np.mean(rs)) for s, rs in rank_acc.items() if rs}
        return pd.Series(rets), px
    rets, px = {}, {}
    for s in symbols:
        try:
            c = fetch_live(s, lookback_h=lookback_h + 5)["candles"]
        except Exception as e:
            print(f"  {s}: fetch fallito ({e})", file=sys.stderr)
            continue
        if len(c) <= lookback_h:
            continue
        last, base = float(c.close.iloc[-1]), float(c.close.iloc[-1 - lookback_h])
        if base > 0:
            rets[s] = last / base - 1.0
            px[s] = last
    return pd.Series(rets), px


def main() -> None:
    spec = load(sys.argv[1]) if len(sys.argv) > 1 else None
    if not spec or spec.get("engine") != "portfolio":
        print("uso: portfolio_paper.py <spec engine:portfolio>", file=sys.stderr)
        return
    acct = spec["id"]
    pf = spec["portfolio"]
    symbols = [s.strip() for s in spec["paper_symbols"].split(",")] if isinstance(spec["paper_symbols"], str) \
        else list(spec["paper_symbols"])
    lookback_h = int(pf["lookback_h"]) if "lookback_h" in pf else int(pf.get("lookbacks_h", [168])[0])
    rebalance_h = int(pf["rebalance_h"])
    gross = float(pf.get("gross", 1.0))
    multi_horizon = pf.get("lookbacks_h")        # [96,168,336] → media dei rank

    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    st = state.setdefault(acct, {"equity": 10_000.0, "positions": {}, "last_rebalance_ts": ""})
    now = datetime.now(timezone.utc)
    print(f"portfolio paper {acct} {now:%Y-%m-%d %H:%M} UTC — equity {st['equity']:.2f}$")

    # prezzi correnti per i simboli in book + universo
    rets, px = trailing_returns(symbols, lookback_h, multi_horizon)
    if not px:
        print("  nessun prezzo: skip"); return

    # 1. mark-to-market del book esistente
    for s, pos in list(st["positions"].items()):
        if s not in px:
            continue
        new_px = px[s]
        pnl = pos["notional"] * (new_px / pos["px"] - 1.0)
        st["equity"] += pnl
        pos["notional"] *= new_px / pos["px"]   # il notional deriva col prezzo
        pos["px"] = new_px

    # 2. ribilanciamento se è ora (o book vuoto)
    due = (not st["last_rebalance_ts"] or
           now - datetime.fromisoformat(st["last_rebalance_ts"]) >= pd.Timedelta(hours=rebalance_h).to_pytimedelta())
    if due and len(rets) >= 3:
        w = xs_momentum_weights(rets, long_q=float(pf.get("long_q", 0.66)),
                                short_q=float(pf.get("short_q", 0.33)), gross=gross,
                                dollar_neutral=bool(pf.get("dollar_neutral", True)))
        target = {s: float(w[s]) * st["equity"] for s in w.index if abs(w[s]) > 1e-9}
        current = {s: st["positions"].get(s, {}).get("notional", 0.0) for s in set(target) | set(st["positions"])}
        turnover = sum(abs(target.get(s, 0.0) - current.get(s, 0.0)) for s in current)
        st["equity"] -= turnover * COST
        st["positions"] = {s: {"notional": n, "px": px[s]} for s, n in target.items() if s in px}
        st["last_rebalance_ts"] = now.isoformat()
        print(f"  REBALANCE: {len(target)} gambe, turnover {turnover:.0f}$, fee {turnover*COST:.2f}$")
        log_event({"type": "rebalance", "strategy": acct, "equity": round(st["equity"], 2),
                   "weights": {s: round(v, 4) for s, v in
                               sorted(target.items(), key=lambda kv: -abs(kv[1]))}})
    else:
        print(f"  no rebalance (prossimo tra <= {rebalance_h}h)")

    net = sum(p["notional"] for p in st["positions"].values())
    gross_now = sum(abs(p["notional"]) for p in st["positions"].values())
    print(f"fine: equity {st['equity']:.2f}$, gambe {len(st['positions'])}, "
          f"gross {gross_now:.0f}$, net {net:+.0f}$")
    STATE_FILE.write_text(json.dumps(state, indent=1, default=str))
    log_event({"type": "heartbeat", "strategy": acct, "equity": round(st["equity"], 2),
               "open_positions": len(st["positions"])})


if __name__ == "__main__":
    main()
