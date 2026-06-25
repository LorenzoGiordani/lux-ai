"""Test della liquidazione mark-to-market (maintenance margin).

Verifica che il modello MTM sia piu' realistico dell'approssimazione legacy:
cattura il funding accumulato (l'equity e' il collaterale cross-margin) e lascia
il margine di mantenimento residuo invece di perdere size/lev in modo rigido.
Backward-compat: MMR None == modello legacy, curve identiche.

Nota: l'esposizione target viene clippata a exit_cfg['max_leverage'] (e al
max_leverage del Backtest). Per testare posizione a leva alta usiamo
max_leverage coerente in entrambi i posti.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtest.engine import Backtest


def _candles(prices: list[float]) -> pd.DataFrame:
    ts = pd.date_range("2026-01-01", periods=len(prices), freq="1h", tz="UTC")
    o = np.r_[prices[0], prices[:-1]]
    return pd.DataFrame({"ts": ts, "open": o, "high": prices, "low": prices,
                         "close": prices, "volume": [10_000.0] * len(prices)})


def _strat(expo=5.0, stop=80.0, lev=5.0):
    def f(_):
        return {"exposure": expo, "stop_pct": stop, "exit_cfg": {"max_leverage": lev}}
    return f


# --- backward-compat: MMR None == legacy, curve identiche ---
def test_mmr_none_identical_to_legacy():
    c = _candles([100.0] * 30)
    eq_off = Backtest(c, maintenance_margin_frac=None).run(_strat(1.0, 80, 1.0))
    eq_legacy = Backtest(c).run(_strat(1.0, 80, 1.0))
    pd.testing.assert_series_equal(
        eq_off["equity"].reset_index(drop=True),
        eq_legacy["equity"].reset_index(drop=True), check_names=False)


# --- flush di prezzo: legacy (1/lev) sopravvive, MTM liquida lasciando MMR ---
def test_mtm_liquidates_where_legacy_survives():
    """Leva 5: legacy liquida solo a entry*0.80. Un flush a 85 NON lo triggera
    (legacy sopravvive con forte perdita). Il MTM con MMR 10% liquida perche'
    l'account equity (10000-7500=2500) scende sotto MMR*size (0.10*50000=5000)."""
    px = [100.0] * 5 + [85.0] * 5
    c = _candles(px)
    eq_legacy = Backtest(c, max_leverage=5.0, funding_hourly=0.0,
                         maintenance_margin_frac=None).run(_strat(5.0, 80, 5.0))
    eq_mtm = Backtest(c, max_leverage=5.0, funding_hourly=0.0,
                      maintenance_margin_frac=0.10).run(_strat(5.0, 80, 5.0))
    # legacy: 85 > 80 (soglia 1/lev) -> NON liquida, equity ~2470 (mtm)
    assert abs(eq_legacy["equity"].iloc[-1] - 2470.0) < 20.0
    # MTM: liquida, equity si ferma al MMR residuo (~4980, 5000 meno fee)
    assert abs(eq_mtm["equity"].iloc[-1] - 4980.0) < 30.0
    assert eq_mtm["equity"].iloc[-1] > eq_legacy["equity"].iloc[-1]


# --- equity residua post-liquidazione = MMR (margine di mantenimento) ---
def test_residual_equity_is_mmr():
    # leva 3, size=30000, flush -40%: unreal=-12000, account_eq=-2000 << MMR
    px = [100.0] * 3 + [60.0] * 4
    c = _candles(px)
    eq = Backtest(c, max_leverage=3.0, funding_hourly=0.0,
                  maintenance_margin_frac=0.05).run(_strat(3.0, 80, 3.0))
    # MMR = 0.05*30000 = 1500 -> equity residua ~1500
    assert abs(eq["equity"].iloc[-1] - 1500.0) < 5.0


# --- liquidazione registrata come trade con pnl reale (override) ---
def test_liquidation_logged_with_real_pnl():
    px = [100.0] * 3 + [50.0] * 4   # flush -50%, leva 3
    c = _candles(px)
    bt = Backtest(c, max_leverage=3.0, funding_hourly=0.0,
                  maintenance_margin_frac=0.05)
    bt.run(_strat(3.0, 80, 3.0))
    liq = [t for t in bt.trades if t["reason"] == "liquidated"]
    assert len(liq) == 1
    # size=30000, MMR=1500: pnl reale = 1500 - ~10000 = ~-8500
    assert liq[0]["pnl_usd"] < -8000.0


# --- funding accumulato erode il collaterale: MTM liquida, legacy no (a bassa leva) ---
def test_funding_erosion_triggers_mtm_liquidation():
    """A leva moderata (2x) con funding forte e prezzo costante: il legacy non
    liquida mai (soglia 1/lev=50% dall'entry, prezzo fermo). Il MTM invece vede
    l'equity erodersi barra dopo barra sotto MMR*size e liquida. Isola l'effetto
    funding (nessun movimento di prezzo)."""
    px = [100.0] * 50
    c = _candles(px)
    # leva 2: legacy liquida solo a 50; prezzo fermo 100 -> mai. Sopravvive.
    eq_legacy = Backtest(c, max_leverage=2.0, funding_hourly=0.05,
                         maintenance_margin_frac=None).run(_strat(2.0, 80, 2.0))
    # MTM MMR 30%: size=20000, MMR=6000. funding 0.05/h*20000=1000/h pagato.
    # equity scende di ~1000/h; dopo ~5 barre account_eq < 6000 -> liquida.
    bt_mtm = Backtest(c, max_leverage=2.0, funding_hourly=0.05,
                      maintenance_margin_frac=0.30)
    eq_mtm = bt_mtm.run(_strat(2.0, 80, 2.0))
    # proprieta' chiave: il MTM registra liquidazioni (funding eroso il collaterale),
    # il legacy (soglia 1/lev fissa, prezzo costante) NON registra liquidazioni.
    assert any(t["reason"] == "liquidated" for t in bt_mtm.trades)
    bt_legacy = Backtest(c, max_leverage=2.0, funding_hourly=0.05)
    bt_legacy.run(_strat(2.0, 80, 2.0))
    assert not any(t["reason"] == "liquidated" for t in bt_legacy.trades)


# --- MMR piu' alto = liquida prima -> lascia piu' equity residua ---
def test_higher_mmr_leaves_more_residual():
    px = [100.0] * 3 + [50.0] * 4   # flush -50%, leva 3
    c = _candles(px)
    eq_loose = Backtest(c, max_leverage=3.0, funding_hourly=0.0,
                        maintenance_margin_frac=0.05).run(_strat(3.0, 80, 3.0))
    eq_tight = Backtest(c, max_leverage=3.0, funding_hourly=0.0,
                        maintenance_margin_frac=0.20).run(_strat(3.0, 80, 3.0))
    # MMR alto (20%) liquida prima, lascia 0.20*30000=6000 > 0.05*30000=1500
    assert eq_tight["equity"].iloc[-1] > eq_loose["equity"].iloc[-1]
