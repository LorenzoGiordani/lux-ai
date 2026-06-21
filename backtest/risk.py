"""Logica di rischio condivisa fra backtest (engine.py) e paper (paper_trade.py).

Un solo posto per: classificazione asset, ATR, stop volatility-adaptive, sizing
vol-target, e gestione uscita con partial TP + trailing. I due engine DEVONO
restare allineati: qui sta la verità, loro la applicano (PnL/funding/liquidazione
restano specifici di ciascun engine).

Fix implementati:
1. Stop ATR-based   — stop = k*ATR%, non % fissa → adatta alla volatilità dell'asset.
2. Vol-target size  — exposure = risk_pct/stop_pct: stop ATR più stretto ⇒ più leva
                      su asset poco volatili, meno su asset volatili. Automatico.
3. RR per classe    — exit.by_class.{crypto,stock} override (stop_atr_mult, target_r,
                      time_stop_h, max_leverage). Crypto: stop largo/RR moderato.
                      Stock/commodity: stop stretto/leva alta.
4. Partial TP+trail — prendi tp1_frac a tp1_r, sposta stop a breakeven, traila il
                      resto a trail_atr_mult*ATR dal massimo favorevole.
"""

from __future__ import annotations

import pandas as pd

# clamp dello stop effettivo: stesso range dei HARD_LIMITS del desk (decide.py)
STOP_PCT_FLOOR = 0.5
STOP_PCT_CAP = 8.0


def asset_class_of(symbol: str | None) -> str:
    """xyz_* / xyz: = stock/commodity HIP-3 (bassa vol). Tutto il resto = crypto."""
    if symbol and symbol.startswith(("xyz_", "xyz:")):
        return "stock"
    return "crypto"


def atr_pct(candles: pd.DataFrame, period: int = 14) -> pd.Series:
    """ATR come frazione del close (rolling mean del true range). Anti-lookahead:
    al bar i usa solo dati ≤ i. Ritorna serie allineata a candles.index."""
    prev_close = candles.close.shift(1)
    tr = pd.concat([
        candles.high - candles.low,
        (candles.high - prev_close).abs(),
        (candles.low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(period, min_periods=max(2, period // 2)).mean()
    return (atr / candles.close).fillna(0.0)


def resolve_exit(spec: dict, symbol: str | None) -> dict:
    """Fonde exit base con l'override exit.by_class[classe] e risolve max_leverage.
    Ritorna un dict piatto: stop_pct, target_r, time_stop_h, stop_atr_mult (opz),
    atr_period, partial (opz), max_leverage."""
    base = {k: v for k, v in spec["exit"].items() if k != "by_class"}
    override = spec["exit"].get("by_class", {}).get(asset_class_of(symbol), {})
    merged = {**base, **override}
    merged.setdefault("atr_period", 14)
    merged.setdefault("time_stop_h", 10**9)
    merged["max_leverage"] = float(override.get("max_leverage", spec["risk"]["max_leverage"]))
    return merged


def effective_stop_pct(merged: dict, atr_pct_val: float | None) -> float:
    """Stop % effettivo. Se stop_atr_mult presente e ATR valido → k*ATR% clampato.
    Altrimenti stop_pct fisso (retro-compatibile)."""
    mult = merged.get("stop_atr_mult")
    if mult and atr_pct_val and atr_pct_val > 0:
        return min(STOP_PCT_CAP, max(STOP_PCT_FLOOR, float(mult) * atr_pct_val * 100.0))
    return float(merged["stop_pct"])


def exposure_for(merged: dict, risk_per_trade_pct: float, stop_pct_eff: float) -> float:
    """Vol-target sizing: frazione di equity = min(leva max, risk%/stop%).
    Stop più stretto (asset poco volatile) ⇒ esposizione maggiore, fino al cap."""
    return min(merged["max_leverage"], float(risk_per_trade_pct) / stop_pct_eff)


def open_levels(merged: dict, entry_px: float, sign: int,
                stop_pct_eff: float, atr_pct_val: float | None) -> dict:
    """Livelli e stato di gestione da salvare nella posizione (dict-based, condiviso).
    sign: +1 long, -1 short."""
    stop_frac = stop_pct_eff / 100.0
    target_r = float(merged.get("target_r", 0)) or None
    pos = {
        "sign": sign,
        "entry_px": entry_px,
        "stop_px": entry_px * (1 - sign * stop_frac),
        "target_px": entry_px * (1 + sign * stop_frac * target_r) if target_r else None,
        "remaining": 1.0,          # frazione della size originale ancora aperta
        "partial_done": False,
        "hi_water": entry_px,      # estremo favorevole, per il trailing
        "tp1_px": None,
        "tp1_frac": 0.0,
        "trail_dist": None,        # distanza assoluta di prezzo del trailing stop
    }
    p = merged.get("partial")
    if p and target_r and atr_pct_val and atr_pct_val > 0:
        pos["tp1_px"] = entry_px * (1 + sign * stop_frac * float(p["tp1_r"]))
        pos["tp1_frac"] = float(p["tp1_frac"])
        pos["trail_dist"] = entry_px * atr_pct_val * float(p["trail_atr_mult"])
    return pos


def step_exit(pos: dict, high: float, low: float, slippage: float) -> list[tuple[float, float, str]]:
    """Valuta una candela contro stop/partial/target e aggiorna il trailing.
    Muta pos (stop_px trailato, remaining, partial_done, hi_water).
    Ritorna lista di fill: (frazione_della_size_originale, prezzo_exit, motivo).
    Conservativo: lo stop vince sul target nella stessa candela."""
    sign = pos["sign"]
    fills: list[tuple[float, float, str]] = []

    # 1. stop (anche trailato) — prima di tutto
    hit_stop = (low <= pos["stop_px"]) if sign > 0 else (high >= pos["stop_px"])
    if hit_stop:
        px = pos["stop_px"] * (1 - sign * slippage)
        fills.append((pos["remaining"], px, "trail_stop" if pos["partial_done"] else "stopped"))
        pos["remaining"] = 0.0
        return fills

    # 2. partial TP1 → realizza tp1_frac, sposta stop a breakeven
    if not pos["partial_done"] and pos["tp1_px"] is not None:
        hit_tp1 = (high >= pos["tp1_px"]) if sign > 0 else (low <= pos["tp1_px"])
        if hit_tp1:
            px = pos["tp1_px"] * (1 - sign * slippage)
            fills.append((pos["tp1_frac"], px, "partial"))
            pos["remaining"] -= pos["tp1_frac"]
            pos["partial_done"] = True
            be = pos["entry_px"]
            if (sign > 0 and be > pos["stop_px"]) or (sign < 0 and be < pos["stop_px"]):
                pos["stop_px"] = be   # breakeven: protegge il resto

    # 3. target finale sul residuo
    if pos["remaining"] > 0 and pos["target_px"] is not None:
        hit_t = (high >= pos["target_px"]) if sign > 0 else (low <= pos["target_px"])
        if hit_t:
            px = pos["target_px"] * (1 - sign * slippage)
            fills.append((pos["remaining"], px, "target"))
            pos["remaining"] = 0.0
            return fills

    # 4. avanza il trailing stop (solo dopo il partial)
    if pos["partial_done"] and pos["trail_dist"]:
        ext = high if sign > 0 else low
        pos["hi_water"] = max(pos["hi_water"], ext) if sign > 0 else min(pos["hi_water"], ext)
        new_stop = pos["hi_water"] - sign * pos["trail_dist"]
        if (sign > 0 and new_stop > pos["stop_px"]) or (sign < 0 and new_stop < pos["stop_px"]):
            pos["stop_px"] = new_stop

    return fills
