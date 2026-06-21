"""Paper trading su dati live — forward test (M2). Zero fondi, zero ordini reali.

Uso: uv run scripts/paper_trade.py <strategia.yaml> BTC,ETH,SOL
Pensato per girare ogni decision_every_h via cron. Ogni run:
1. scarica candele/funding/flow recenti (Binance, stessa fonte del backtest)
2. aggiorna le posizioni aperte (stop/target/time-stop sulle candele trascorse)
3. apre nuove posizioni se il segnale è attivo all'ultima barra chiusa
4. stato in paper/state.json, ogni evento in paper/journal.jsonl

Stesse assunzioni dell'engine: fee taker 4.5bps, slippage 2bps.
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from backtest.engine import DEFAULT_SLIPPAGE, HL_TAKER_FEE
from backtest.risk import (atr_pct, effective_stop_pct, exposure_for, open_levels,
                           resolve_exit, step_exit)
from backtest.signals import SIGNALS
from backtest.strategy import _direction, _eval_rule, load
from pipeline.live import fetch_live_cached

ROOT = Path(__file__).resolve().parent.parent  # indipendente dal cwd (cron)
STATE_FILE = ROOT / "paper/state.json"
JOURNAL = ROOT / "paper/journal.jsonl"
LOOKBACK_H = 1000  # copre il lookback massimo dei segnali (336+48)
MAX_PARTICIPATION = 0.005  # size max apribile = 0.5% del volume 24h (gate liquidita per-trade)


def log_event(event: dict) -> None:
    event["logged_at"] = datetime.now(timezone.utc).isoformat()
    with JOURNAL.open("a") as f:
        f.write(json.dumps(event, default=str) + "\n")


def _book_fill(pos: dict, frac: float, px: float, reason: str, equity: float) -> float:
    """Registra un fill (parziale o totale) su pos: PnL, log, riduce remaining."""
    sign = pos["sign"]
    pnl = pos["size_usd"] * frac * (px / pos["entry_px"] - 1) * sign - pos["size_usd"] * frac * HL_TAKER_FEE
    equity += pnl
    pos["remaining"] -= frac
    log_event({"type": "close", "strategy": pos["strategy"], "symbol": pos["symbol"],
               "reason": reason, "exit_px": px, "frac": round(frac, 4),
               "remaining": round(pos["remaining"], 4), "pnl_usd": round(pnl, 2),
               "equity": round(equity, 2), "ts": pos.get("_last_ts")})
    tag = "PARTIAL" if pos["remaining"] > 1e-9 and reason == "partial" else "CLOSE"
    print(f"  {tag} {pos['symbol']} {pos['direction']} → {reason}, frac {frac:.2f}, pnl {pnl:+.2f}$")
    return equity


def update_position(pos: dict, candles: pd.DataFrame, time_stop_h: int, equity: float,
                    forming=None) -> tuple[dict | None, float]:
    """Gestisce stop/partial-TP/target/trailing (via risk.step_exit) + time-stop sulle
    candele chiuse dall'ultimo check. `forming` (barra in corso) attiva solo le uscite
    PROTETTIVE sul residuo (stop/target pieno), come un ordine exchange intrabar: niente
    partial/trailing persistiti finché la barra non chiude (no doppio conteggio)."""
    if "sign" not in pos:  # posizione aperta col vecchio schema (pre ATR/partial)
        pos["sign"] = 1 if pos["direction"] == "long" else -1
        pos.setdefault("remaining", 1.0)
        pos.setdefault("partial_done", False)
        pos.setdefault("hi_water", pos["entry_px"])
        pos.setdefault("tp1_px", None)
        pos.setdefault("tp1_frac", 0.0)
        pos.setdefault("trail_dist", None)
    new = candles[candles.ts > pd.Timestamp(pos["checked_until"])]
    sign = pos["sign"]
    for _, row in new.iterrows():
        pos["_last_ts"] = row.ts
        for frac, px, reason in step_exit(pos, row.high, row.low, DEFAULT_SLIPPAGE):
            equity = _book_fill(pos, frac, px, reason, equity)
        if pos["remaining"] <= 1e-9:
            return None, equity
        if (row.ts - pd.Timestamp(pos["opened_at"])) >= timedelta(hours=time_stop_h):
            equity = _book_fill(pos, pos["remaining"], row.close * (1 - sign * DEFAULT_SLIPPAGE),
                                "time_stop", equity)
            return None, equity
    pos["checked_until"] = str(candles.ts.iloc[-1])

    if forming is not None:  # protezione intrabar sul residuo, senza mutare lo stato
        f = forming
        hit_stop = (f.low <= pos["stop_px"]) if sign > 0 else (f.high >= pos["stop_px"])
        hit_t = pos["target_px"] is not None and (
            (f.high >= pos["target_px"]) if sign > 0 else (f.low <= pos["target_px"]))
        if hit_stop:
            pos["_last_ts"] = f.ts
            equity = _book_fill(pos, pos["remaining"], pos["stop_px"] * (1 - sign * DEFAULT_SLIPPAGE),
                                "trail_stop" if pos["partial_done"] else "stopped", equity)
            return None, equity
        if hit_t:
            pos["_last_ts"] = f.ts
            equity = _book_fill(pos, pos["remaining"], pos["target_px"] * (1 - sign * DEFAULT_SLIPPAGE),
                                "target", equity)
            return None, equity
    return pos, equity


def maybe_open(spec: dict, symbol: str, data: dict, equity: float, strategy_id: str) -> dict | None:
    sigs = pd.DataFrame({s["name"]: SIGNALS[s["name"]](data, **s.get("params", {}))
                         for s in spec["signals"]})
    active = _eval_rule(spec["entry"]["rule"], sigs).iloc[-1]
    direction = float(_direction(spec["entry"]["direction"], sigs).iloc[-1])
    if not active or direction == 0:
        return None
    last = data["candles"].iloc[-1]
    sign = 1 if direction > 0 else -1
    # rischio per asset-class + stop ATR-adattivo + sizing vol-target (risk.py)
    merged = resolve_exit(spec, symbol)
    atrp = float(atr_pct(data["candles"], int(merged["atr_period"])).iloc[-1])
    stop_pct_eff = effective_stop_pct(merged, atrp)
    exposure = exposure_for(merged, spec["risk"]["risk_per_trade_pct"], stop_pct_eff)
    size_usd = round(exposure * equity, 2)
    # gate liquidita caso-per-caso: la size deve restare sotto una frazione del
    # volume 24h reale dell'asset, altrimenti il fill non e realistico → skip.
    vol24h = float((data["candles"].close * data["candles"].volume).tail(24).sum())
    if vol24h <= 0 or size_usd > MAX_PARTICIPATION * vol24h:
        return None
    px = last.close * (1 + sign * DEFAULT_SLIPPAGE)
    pos = {**open_levels(merged, px, sign, stop_pct_eff, atrp),
           "strategy": strategy_id, "symbol": symbol,
           "direction": "long" if sign > 0 else "short", "size_usd": size_usd,
           "opened_at": str(last.ts), "checked_until": str(last.ts)}
    log_event({"type": "open", **pos, "stop_pct_eff": round(stop_pct_eff, 3), "atr_pct": round(atrp, 4),
               "thesis": f"{spec['entry']['rule']} → {spec['entry']['direction']}",
               "signals_last": {c: int(sigs[c].iloc[-1]) for c in sigs.columns}})
    print(f"  OPEN {symbol} {pos['direction']} @ {px:.4g}, size {size_usd}$ (lev {exposure:.2f}, "
          f"stop {stop_pct_eff:.2f}% ATR), target {pos['target_px']:.4g}")
    return pos


def main() -> None:
    spec_path, symbols = sys.argv[1], sys.argv[2].split(",")
    if not Path(spec_path).is_absolute():
        spec_path = ROOT / spec_path
    spec = load(spec_path)
    sid = spec["id"]
    STATE_FILE.parent.mkdir(exist_ok=True)
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    st = state.setdefault(sid, {"equity": 10_000.0, "positions": {}})

    print(f"paper run {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC — {sid}, equity {st['equity']:.2f}$")
    max_conc = int(spec["risk"]["max_concurrent_positions"])

    news_events = None
    if any(s["name"] == "news_event" for s in spec.get("signals", [])):
        try:
            from pipeline.gdelt import news_events_cached
            news_events = news_events_cached()   # memoizzato: 1 fetch/run condiviso, no 429 storm
            print(f"  news events (cache): {0 if news_events is None else len(news_events)}")
        except Exception as e:
            print(f"  news events fetch fallito ({e})", file=sys.stderr)

    # universe corrente + eventuali posizioni aperte fuori universe (es. dopo un
    # cambio di selection): vanno comunque gestite a exit, mai lasciate orfane
    held_outside = [s for s in st["positions"] if s not in symbols]
    for symbol in symbols + held_outside:
        try:
            data = fetch_live_cached(symbol)
            data["symbol"] = symbol  # serve ai segnali cache-reader (liq/kronos/hmm/smart-money)
            data["news_events"] = news_events
            cot = ROOT / f"data/cot/{symbol}.parquet"
            data["cot"] = pd.read_parquet(cot) if cot.exists() else None
        except Exception as e:
            print(f"  {symbol}: fetch fallito ({e})", file=sys.stderr)
            continue
        pos = st["positions"].get(symbol)
        closed_this_run = False
        if pos:
            time_stop_h = int(resolve_exit(spec, symbol)["time_stop_h"])
            pos, st["equity"] = update_position(pos, data["candles"], time_stop_h,
                                                st["equity"], data.get("forming"))
            if pos:
                st["positions"][symbol] = pos
            else:
                del st["positions"][symbol]
                closed_this_run = True  # come il backtest: re-entry al più presto sulla barra dopo, mai stessa barra
        if not closed_this_run and symbol not in st["positions"] and len(st["positions"]) < max_conc:
            new_pos = maybe_open(spec, symbol, data, st["equity"], sid)
            if new_pos:
                st["equity"] -= new_pos["size_usd"] * HL_TAKER_FEE
                st["positions"][symbol] = new_pos

    open_syms = list(st["positions"]) or "nessuna"
    print(f"fine run: equity {st['equity']:.2f}$, posizioni aperte: {open_syms}")
    STATE_FILE.write_text(json.dumps(state, indent=1, default=str))
    log_event({"type": "heartbeat", "strategy": sid, "equity": round(st["equity"], 2),
               "open_positions": len(st["positions"])})


if __name__ == "__main__":
    main()
