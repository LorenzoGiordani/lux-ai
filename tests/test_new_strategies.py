"""Test del nuovo segnale volume_profile e delle strategie di ricerca 2026-06-22."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backtest.signals import SIGNALS, volume_profile
from backtest.strategy import compile_strategy, load

NEW_STRATS = [
    "volprofile-reversion-v1", "liq-cascade-reversal-v1",
    "vol-expansion-breakout-v1", "lux-confluence-rr2-v1",
]


def _candles(n: int = 400, base: float = 100.0) -> pd.DataFrame:
    ts = pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC")
    close = np.full(n, base)
    close[-6:] = base * 1.3                       # spike sopra la value area
    high, low = close * 1.002, close * 0.998
    vol = np.full(n, 1000.0)
    return pd.DataFrame({"ts": ts, "open": close, "high": high, "low": low,
                         "close": close, "volume": vol})


def test_volume_profile_in_registry():
    assert "volume_profile" in SIGNALS


def test_volume_profile_values_and_extension():
    c = _candles()
    out = volume_profile({"candles": c}, lookback_h=168, recompute_h=6)
    assert len(out) == len(c)
    assert set(np.unique(out.to_numpy())).issubset({-1, 0, 1})
    assert out.iloc[-1] == 1                       # prezzo spinto sopra la VAH → +1


def test_volume_profile_short_series_neutral():
    c = _candles(n=50)
    out = volume_profile({"candles": c}, lookback_h=168)
    assert (out == 0).all()                        # finestra insufficiente → neutro, niente crash


def test_new_strategies_load_and_compile():
    c = _candles()
    data = {"candles": c, "symbol": "BTC", "funding": None, "flow": None,
            "news_events": None, "cot": None}
    for sid in NEW_STRATS:
        spec = load(ROOT / "strategies" / "generated" / f"{sid}.yaml")
        strat, sigs = compile_strategy(spec, data)
        out = strat(c)                             # una chiamata non deve esplodere
        assert "exposure" in out and "target_r" in out
