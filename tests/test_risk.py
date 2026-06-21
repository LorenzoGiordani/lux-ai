"""Test della logica di rischio condivisa (backtest/risk.py)."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest.risk import (asset_class_of, atr_pct, effective_stop_pct,
                           exposure_for, open_levels, resolve_exit, step_exit)


def _spec():
    return {
        "exit": {
            "stop_pct": 4.0, "stop_atr_mult": 2.5, "target_r": 2.0, "atr_period": 14,
            "time_stop_h": 240,
            "partial": {"tp1_r": 1.0, "tp1_frac": 0.5, "trail_atr_mult": 3.0},
            "by_class": {
                "crypto": {"stop_atr_mult": 2.5, "target_r": 2.0},
                "stock": {"stop_atr_mult": 1.5, "target_r": 1.8, "max_leverage": 4},
            },
        },
        "risk": {"max_leverage": 2, "risk_per_trade_pct": 1.0},
    }


def test_asset_class():
    assert asset_class_of("xyz_GOLD") == "stock"
    assert asset_class_of("xyz:SP500") == "stock"
    assert asset_class_of("BTC") == "crypto"
    assert asset_class_of(None) == "crypto"


def test_atr_pct_positive():
    c = pd.DataFrame({"high": [11, 12, 13, 12, 14], "low": [9, 10, 11, 10, 12],
                      "close": [10, 11, 12, 11, 13]})
    a = atr_pct(c, period=3)
    assert len(a) == len(c)
    assert (a >= 0).all() and a.iloc[-1] > 0


def test_resolve_exit_by_class():
    s = _spec()
    crypto = resolve_exit(s, "BTC")
    stock = resolve_exit(s, "xyz_GOLD")
    assert crypto["stop_atr_mult"] == 2.5 and crypto["max_leverage"] == 2.0
    assert stock["stop_atr_mult"] == 1.5 and stock["target_r"] == 1.8
    assert stock["max_leverage"] == 4.0   # override per classe


def test_effective_stop_pct():
    m = resolve_exit(_spec(), "BTC")
    # ATR 2% * mult 2.5 = 5% stop
    assert abs(effective_stop_pct(m, 0.02) - 5.0) < 1e-9
    # ATR assente → fallback fisso stop_pct
    assert effective_stop_pct(m, None) == 4.0
    # clamp: ATR enorme → cap 8%
    assert effective_stop_pct(m, 0.10) == 8.0


def test_vol_target_sizing():
    m = resolve_exit(_spec(), "BTC")  # max_leverage 2, risk 1%
    # stop stretto (0.5%) → 1/0.5 = 2x ma cappato a max_leverage 2
    assert exposure_for(m, 1.0, 0.5) == 2.0
    # stop largo (5%) → 1/5 = 0.2x, sotto il cap
    assert abs(exposure_for(m, 1.0, 5.0) - 0.2) < 1e-9


def test_step_exit_full_stop_long():
    pos = open_levels(resolve_exit(_spec(), "BTC"), entry_px=100.0, sign=1,
                      stop_pct_eff=5.0, atr_pct_val=0.02)
    # stop a 95; candela che lo buca
    fills = step_exit(pos, high=101, low=94, slippage=0.0)
    assert fills == [(1.0, 95.0, "stopped")]
    assert pos["remaining"] == 0.0


def test_step_exit_partial_then_target_long():
    pos = open_levels(resolve_exit(_spec(), "BTC"), entry_px=100.0, sign=1,
                      stop_pct_eff=5.0, atr_pct_val=0.02)
    # tp1 a 1R = 105, target a 2R = 110
    f1 = step_exit(pos, high=106, low=100, slippage=0.0)   # tocca tp1, non target
    assert len(f1) == 1 and f1[0][0] == 0.5 and abs(f1[0][1] - 105.0) < 1e-6 and f1[0][2] == "partial"
    assert pos["partial_done"] and pos["stop_px"] == 100.0  # stop a breakeven
    f2 = step_exit(pos, high=111, low=106, slippage=0.0)    # tocca target sul residuo
    assert len(f2) == 1 and f2[0][0] == 0.5 and abs(f2[0][1] - 110.0) < 1e-6 and f2[0][2] == "target"
    assert pos["remaining"] == 0.0


def test_step_exit_trailing_protects_after_partial():
    pos = open_levels(resolve_exit(_spec(), "BTC"), entry_px=100.0, sign=1,
                      stop_pct_eff=5.0, atr_pct_val=0.02)
    # restiamo sotto il target 2R (110) per testare il trailing, non il target
    step_exit(pos, high=106, low=100, slippage=0.0)         # partial → BE stop 100, trail_dist=100*0.02*3=6
    step_exit(pos, high=109, low=106, slippage=0.0)         # hi_water 109 → trail stop 103
    assert abs(pos["stop_px"] - 103.0) < 1e-9
    f = step_exit(pos, high=108, low=102, slippage=0.0)     # ritraccia sotto 103 → trail_stop
    assert f and f[0][2] == "trail_stop" and pos["remaining"] == 0.0


def test_step_exit_short_stop():
    pos = open_levels(resolve_exit(_spec(), "BTC"), entry_px=100.0, sign=-1,
                      stop_pct_eff=5.0, atr_pct_val=0.02)
    assert pos["stop_px"] == 105.0 and pos["target_px"] == 90.0
    fills = step_exit(pos, high=106, low=99, slippage=0.0)
    assert fills == [(1.0, 105.0, "stopped")]


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fails = 0
    for fn in fns:
        try:
            fn(); print(f"PASS {fn.__name__}")
        except Exception:
            fails += 1; print(f"FAIL {fn.__name__}"); traceback.print_exc()
    print(f"\n{len(fns)-fails}/{len(fns)} passed")
    sys.exit(1 if fails else 0)
