"""Executor live testnet (M4) — riconcilia le posizioni reali su Hyperliquid testnet
con i target di una strategia validata. DRY-RUN di default (senza chiave API wallet
nessun ordine reale parte: stampa e logga cosa FAREBBE).

Stessa identica logica di segnale del paper trader (paper_trade.py) → il forward test
e l'esecuzione reale non possono divergere. Differenza: qui gli ordini vanno a HL.

Uso:  .venv/bin/python scripts/execute_testnet.py strategies/generated/tsmom-liq-v1.yaml BTC,ETH,SOL
       (dry-run finché HL_ACCOUNT_ADDRESS + HL_API_SECRET non sono nell'env)
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest.signals import SIGNALS
from backtest.strategy import _direction, _eval_rule, load
from pipeline.executor import Executor
from pipeline.live import fetch_live

ROOT = Path(__file__).resolve().parent.parent


def target_for(spec: dict, symbol: str) -> dict | None:
    """Direzione/size/stop target all'ultima barra chiusa, o None se flat."""
    data = fetch_live(symbol)
    data["symbol"] = symbol  # segnali cache-reader (liq_imbalance, ...)
    sigs = pd.DataFrame({s["name"]: SIGNALS[s["name"]](data, **s.get("params", {}))
                         for s in spec["signals"]})
    active = bool(_eval_rule(spec["entry"]["rule"], sigs).iloc[-1])
    direction = float(_direction(spec["entry"]["direction"], sigs).iloc[-1])
    if not active or direction == 0:
        return None
    sign = 1 if direction > 0 else -1
    entry_px = float(data["candles"]["close"].iloc[-1])
    stop_pct = float(spec["exit"]["stop_pct"]) / 100
    return {"symbol": symbol, "is_buy": sign > 0, "sign": sign, "entry_px": entry_px,
            "stop_px": entry_px * (1 - sign * stop_pct)}


def main() -> None:
    spec_path, symbols = sys.argv[1], sys.argv[2].split(",")
    if not Path(spec_path).is_absolute():
        spec_path = ROOT / spec_path
    spec = load(spec_path)
    ex = Executor()

    equity = 10_000.0
    if ex.address and not ex.dry_run:
        try:
            st = ex.info.user_state(ex.address)
            equity = float(st["marginSummary"]["accountValue"])
        except Exception:
            pass
    leverage = int(spec["risk"]["max_leverage"])
    exposure = min(leverage, float(spec["risk"]["risk_per_trade_pct"]) / float(spec["exit"]["stop_pct"]))
    size_usd = exposure * equity
    max_conc = int(spec["risk"]["max_concurrent_positions"])

    mode = "DRY-RUN (nessun ordine reale)" if ex.dry_run else f"LIVE {ex.network}"
    print(f"[{mode}] {spec['id']} — equity {equity:.0f}$, leva≤{leverage}, "
          f"size/trade {size_usd:.0f}$, max {max_conc} posizioni")

    current = ex.positions()  # {coin: signed size}; vuoto in dry-run senza address
    targets = {}
    for s in symbols:
        try:
            t = target_for(spec, s)
            if t:
                targets[s] = t
        except Exception as e:
            print(f"  {s}: target fallito ({e})", file=sys.stderr)

    # 0) pulizia: SL/TP orfani su coin senza posizione aperta (es. SL scattato tra le run)
    for s in symbols:
        if s not in current:
            canc = ex.cancel_open_orders(s)
            if canc:
                print(f"  CLEAN {s}: {len(canc)} ordini trigger orfani cancellati")

    # 1) chiudi posizioni che non corrispondono più al target
    for coin, szi in current.items():
        cur_sign = 1 if szi > 0 else -1
        if coin not in targets or targets[coin]["sign"] != cur_sign:
            print(f"  CLOSE {coin} (szi {szi:+g})")
            ex.close_position(coin)

    # 2) apri nuovi target (rispetta max_concurrent)
    open_count = sum(1 for c, s in current.items()
                     if c in targets and targets[c]["sign"] == (1 if s > 0 else -1))
    for coin, t in targets.items():
        already = coin in current and (1 if current[coin] > 0 else -1) == t["sign"]
        if already:
            continue
        if open_count >= max_conc:
            print(f"  SKIP {coin} (max {max_conc} posizioni raggiunto)")
            continue
        side = "LONG" if t["is_buy"] else "SHORT"
        print(f"  OPEN {coin} {side} @ {t['entry_px']:.5g}, stop {t['stop_px']:.5g}, size {size_usd:.0f}$")
        ex.open_position(coin, t["is_buy"], size_usd, t["entry_px"], t["stop_px"], leverage)
        open_count += 1

    if not targets:
        print("  nessun segnale attivo all'ultima barra — flat")


if __name__ == "__main__":
    main()
