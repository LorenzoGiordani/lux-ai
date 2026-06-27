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
from pipeline.live import atomic_write_text, fetch_live
from scripts.paper_trade import STATE_FILE, log_event

COST = HL_TAKER_FEE + DEFAULT_SLIPPAGE

# Vol-target overlay (Moreira-Muir 2017): scala il gross inverso alla vol realizzata
# del book. Cablato qui per i candidati con portfolio.vol_target.enabled=true.
# Cron ogni 4h -> annualizzo per sqrt(PERIODS_PER_YEAR_HEARTBEAT). Warmup m=1.0.
PERIODS_PER_YEAR_HEARTBEAT = 6 * 365   # heartbeat ogni 4h


def _vol_target_multiplier(history: list, vt: dict) -> float:
    """m = clip(target_vol / realized_vol, gross_floor, gross_cap).
    history: lista di dict {"ts", "eq"} passati (anti-lookahead: solo <= now).
    Ritorna 1.0 in warmup (< min_periods punti)."""
    if not vt or not vt.get("enabled"):
        return 1.0
    min_p = int(vt.get("vol_window_h", 720)) // 4          # ~punti heartbeat necessari
    min_p = max(min_p, 30)
    eqs = [float(h["eq"]) for h in history if h.get("eq")]
    if len(eqs) < min_p:
        return 1.0                                       # warmup
    import numpy as _np
    window = eqs[-min_p:]
    rets = _np.diff(window) / _np.array(window[:-1])
    if len(rets) < 5 or _np.std(rets) <= 0:
        return 1.0
    realized_ann = float(_np.std(rets) * _np.sqrt(PERIODS_PER_YEAR_HEARTBEAT))
    target = float(vt.get("target_vol_ann", 0.20))
    m = target / realized_ann
    return float(_np.clip(m, float(vt.get("gross_floor", 0.3)), float(vt.get("gross_cap", 1.5))))


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


def vol_signal(symbols: list[str], lookback_h: int) -> tuple[pd.Series, dict]:
    """HIGH-VOL factor: per ogni asset la dev-standard dei rendimenti orari trailing.
    xs_momentum_weights poi long-top (i piu' volatili) / short-bottom (calmi).
    Risk premium crypto, ortogonale al momentum (ranka vol, non ret)."""
    vols, px = {}, {}
    for s in symbols:
        try:
            c = fetch_live(s, lookback_h=lookback_h + 5)["candles"]
        except Exception as e:
            print(f"  {s}: fetch fallito ({e})", file=sys.stderr)
            continue
        if len(c) <= lookback_h:
            continue
        r = c.close.pct_change().iloc[-lookback_h:]
        vols[s] = float(r.std())
        px[s] = float(c.close.iloc[-1])
    return pd.Series(vols), px


def combo_signal(symbols: list[str], factors: list[str], weights: list[float],
                 lookback_h: int, vol_lookback_h: int) -> tuple[pd.Series, dict]:
    """COMBO multi-fattore: media pesata dei segnali normalizzati (z-score per
    comparabilita'). xsmom = ret trailing (z), highvol = std trailing (z).
    Pesi da `weights` (es. [0.7, 0.3]). Anti-lookahead: ogni segnale usa dati <= t."""
    sigs = {}
    px = {}
    for s in symbols:
        try:
            n = max(lookback_h, vol_lookback_h) + 5
            c = fetch_live(s, lookback_h=n)["candles"]
        except Exception as e:
            print(f"  {s}: fetch fallito ({e})", file=sys.stderr)
            continue
        px[s] = float(c.close.iloc[-1])
        parts = []
        for f, w in zip(factors, weights):
            if f == "xsmom":
                r = c.close.iloc[-1] / c.close.iloc[-1 - lookback_h] - 1.0
                parts.append(float(r) * w)
            elif f == "highvol":
                v = c.close.pct_change().iloc[-vol_lookback_h:].std()
                parts.append(float(v) * w)   # segno +: long i volatili
        sigs[s] = sum(parts)
    # normalizza per cross-section comparabilita' (z-score)
    s = pd.Series(sigs)
    if len(s) >= 3 and s.std() > 0:
        s = (s - s.mean()) / s.std()
    return s, px


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
    factor = pf.get("factor", "xsmom")           # xsmom (rank ret) | highvol (rank std)

    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    st = state.setdefault(acct, {"equity": 10_000.0, "positions": {}, "last_rebalance_ts": "",
                                 "equity_history": []})
    vt = pf.get("vol_target")                            # overlay Moreira-Muir (opt-in)
    now = datetime.now(timezone.utc)
    print(f"portfolio paper {acct} {now:%Y-%m-%d %H:%M} UTC — equity {st['equity']:.2f}$")

    # prezzi correnti per i simboli in book + universo
    factors = pf.get("factors")                # [xsmom, highvol] → combo pesata
    if factors:
        rets, px = combo_signal(symbols, factors, pf.get("weights", [0.5, 0.5]),
                                pf.get("lookback_h", 168), pf.get("vol_lookback_h", 72))
    elif factor == "highvol":
        rets, px = vol_signal(symbols, int(pf.get("vol_lookback_h", 72)))
    else:
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
        m = _vol_target_multiplier(st.get("equity_history", []), vt)   # anti-lookahead: solo passato
        gross_eff = gross * m
        if vt and vt.get("enabled") and abs(m - 1.0) > 1e-6:
            print(f"  vol-target: realized->m={m:.2f} (gross {gross:.2f}->{gross_eff:.2f})")
        w = xs_momentum_weights(rets, long_q=float(pf.get("long_q", 0.66)),
                                short_q=float(pf.get("short_q", 0.33)), gross=gross_eff,
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
    # equity history per vol-target overlay (append + trim a 720 punti ~120g)
    st["equity_history"] = (st.get("equity_history", []) + [{"ts": now.isoformat(), "eq": round(st["equity"], 2)}])[-720:]
    print(f"fine: equity {st['equity']:.2f}$, gambe {len(st['positions'])}, "
          f"gross {gross_now:.0f}$, net {net:+.0f}$")
    atomic_write_text(STATE_FILE, json.dumps(state, indent=1, default=str))
    log_event({"type": "heartbeat", "strategy": acct, "equity": round(st["equity"], 2),
               "open_positions": len(st["positions"])})


if __name__ == "__main__":
    main()
