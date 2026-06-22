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
    "vol-expansion-breakout-v1", "lux-confluence-rr2-v1", "xsmom-v1",
]


def _candles(n: int = 400, base: float = 100.0) -> pd.DataFrame:
    ts = pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC")
    close = np.full(n, base)
    close[-6:] = base * 1.3                       # spike sopra la value area
    high, low = close * 1.002, close * 0.998
    vol = np.full(n, 1000.0)
    return pd.DataFrame({"ts": ts, "open": close, "high": high, "low": low,
                         "close": close, "volume": vol})


def test_new_signals_in_registry():
    assert "volume_profile" in SIGNALS
    assert "xsection_momentum" in SIGNALS


def test_claude_strategy_gate():
    from scripts.claude_strategy import gate_candidates
    ctx = {"assets": {
        "BTC": {"signals": {"tsmom": 1, "liq_imbalance": 1}, "atr_pct": 3.0},    # concordi long
        "ETH": {"signals": {"tsmom": 1, "liq_imbalance": -1}, "atr_pct": 2.0},   # discordi → escluso
        "SOL": {"signals": {"tsmom": 0, "liq_imbalance": 1}, "atr_pct": 2.0},    # uno spento → escluso
        "ZEC": {"signals": {"tsmom": -1, "liq_imbalance": -1}, "atr_pct": 5.0},  # concordi short
    }}
    got = {x["symbol"]: x["direction"] for x in gate_candidates(ctx)}
    assert got == {"BTC": "long", "ZEC": "short"}


def test_claude_strategy_spec_excluded():
    from backtest.lifecycle import active_specs
    spec = load(ROOT / "strategies/generated/claude-strategy-v1.yaml")
    assert spec["engine"] == "desk"
    assert "claude-strategy-v1" not in [s["id"] for _, s in active_specs()]


def test_dedup_by_underlying():
    from pipeline.live import _dedup_by_underlying
    rows = [("HYPE", 100.0), ("hyna:HYPE", 50.0), ("xyz:CL", 30.0), ("hyna:CL", 20.0), ("BTC", 200.0)]
    names = [n for n, _ in _dedup_by_underlying(rows)]
    assert names == ["HYPE", "xyz:CL", "BTC"]    # una variante per underlying, la piu liquida


def test_exclude_classes_filters_indices():
    from backtest.lifecycle import paper_symbols
    spec = {"universe": {"exclude_classes": ["index"]},
            "paper_symbols": "BTC,xyz:SP500,ETH,xyz_GOLD"}
    out = paper_symbols(spec).split(",")
    assert "xyz:SP500" not in out            # indice escluso per classe
    assert "BTC" in out and "ETH" in out and "xyz_GOLD" in out   # crypto + commodity restano


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
