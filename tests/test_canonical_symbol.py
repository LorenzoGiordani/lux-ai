"""Regressione per canonical_symbol + atomic_write_text (pipeline/live).

Il bug storico: l'LLM emetteva simboli non normalizzati (\"SOL/USDT\", \"SOLUSDT\",
\"SOL-PERP\", \"ETH/USDT PERP\", \"SOL/USDT:USDT\"...) nelle decisioni; la dashboard
non riusciva a riconciliarli con le posizioni reali in state (sempre \"SOL\") e il
feed mostrava decisioni fantasma senza esito, staccate dalle posizioni aperte.
Questo test blocca la regressione.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.live import atomic_write_text, canonical_symbol


def test_canonical_strips_quote_suffixes():
    cases = {
        "SOL": "SOL",
        "SOL/USDT": "SOL",
        "SOLUSDT": "SOL",
        "SOL/USD": "SOL",
        "SOL-PERP": "SOL",
        "SOL/USDT-PERP": "SOL",
        "SUIUSDT": "SUI",
        "SUI-USDT-PERP": "SUI",
        "SUI-PERP": "SUI",
        "SUI/USDT": "SUI",
        "ETH/USDT PERP": "ETH",   # spazio + market type
        "ETHUSDT": "ETH",
        "ZEC/USD": "ZEC",
        "ZEC/USDT": "ZEC",
        "ZECUSDT": "ZEC",
        "SOL/USDT:USDT": "SOL",   # market-type di Binance dopo ':'
        "BTC/USDT:USDT": "BTC",
    }
    for raw, expected in cases.items():
        got = canonical_symbol(raw)
        assert got == expected, f"canonical({raw!r}) = {got!r}, expected {expected!r}"


def test_canonical_commodity_aliases():
    # l'LLM emette nomi incoerenti per lo stesso underlying (desk geopolitico):
    # NG / NATGAS / NG1! sono tutti natural gas. Devono convergere a NATGAS.
    assert canonical_symbol("NG") == "NATGAS"
    assert canonical_symbol("NG1!") == "NATGAS"
    assert canonical_symbol("NATGAS") == "NATGAS"
    assert canonical_symbol("WTI") == "CL"
    assert canonical_symbol("CL") == "CL"
    assert canonical_symbol("XAUUSD") == "GOLD"
    assert canonical_symbol("BRENT") == "BRENTOIL"


def test_clean_symbol_strips_venue_for_matching():
    # clean_symbol (dashboard) riduce al base coin: xyz:CL -> CL, cosi' la
    # decisione "CL" e la posizione "xyz:CL" in state riconciliano nello stesso key.
    from scripts.dashboard import clean_symbol
    assert clean_symbol("xyz:CL") == "CL"
    assert clean_symbol("xyz_NATGAS") == "NATGAS"
    assert clean_symbol("xyz:NATGAS") == "NATGAS"
    assert clean_symbol("CL") == "CL"
    assert clean_symbol("NG") == "NATGAS"


def test_canonical_preserves_hip3_and_legacy():
    # i qualificatori di venue HIP-3 (con ':') e il legacy 'xyz_' vanno preservati
    assert canonical_symbol("xyz:NATGAS") == "xyz:NATGAS"
    assert canonical_symbol("xyz_NATGAS") == "xyz_NATGAS"
    assert canonical_symbol("hyna:HYPE") == "hyna:HYPE"


def test_canonical_handles_empty_and_none():
    assert canonical_symbol(None) == ""
    assert canonical_symbol("") == ""
    assert canonical_symbol("  ") == ""
    assert canonical_symbol("BTC ") == "BTC"   # trim degli spazi


def test_canonical_uppercases():
    assert canonical_symbol("sol") == "SOL"
    assert canonical_symbol("eth") == "ETH"


def test_atomic_write_never_truncates():
    # simula la race che faceva sparire backtest/posizioni: 100 scritture
    # concorrenti-virtuali, ognuna deve sempre essere leggibile come JSON valido
    import tempfile

    d = Path(tempfile.mkdtemp())
    fp = d / "state.json"
    for i in range(100):
        atomic_write_text(fp, json.dumps({"i": i, "pad": "x" * 2000}))
        json.loads(fp.read_text())   # mai un JSONDecodeError


def test_atomic_write_replaces_old_content():
    import tempfile

    d = Path(tempfile.mkdtemp())
    fp = d / "f.txt"
    fp.write_text("VECCHIO")
    atomic_write_text(fp, "NUOVO")
    assert fp.read_text() == "NUOVO"
    # non deve lasciare temporanei in giro
    leftovers = [p for p in d.iterdir() if ".tmp" in p.name]
    assert leftovers == [], f"temporanei non puliti: {leftovers}"


def _mk_candles(rows):
    """rows: list of (ts_str, low, high, close). Restituisce un DataFrame candele."""
    import pandas as pd
    ts = pd.to_datetime([r[0] for r in rows], utc=True)
    return pd.DataFrame({
        "ts": ts,
        "low": [r[1] for r in rows], "high": [r[2] for r in rows],
        "close": [r[3] for r in rows],
    })


def test_simulate_exit_short_uses_correct_direction():
    # bug storico: simulate_exit usava la logica long per gli short, dando target
    # falsi (es. 'target hit' quando il prezzo NON era sceso al target dello short).
    # Per uno SHORT: stop SOPRA entry, target SOTTO entry.
    from scripts.backfill_lost_positions import simulate_exit
    import pandas as pd
    # entry 100, short. stop 105 (sopra), target 90 (sotto)
    candles = _mk_candles([
        ("2026-06-27 09:00", 98, 102, 100),   # entry hour: non tocca ne stop ne target
        ("2026-06-27 10:00", 89, 99, 90),    # low 89 <= target 90 -> target hit (short scende)
    ])
    ex = simulate_exit(candles, pd.Timestamp("2026-06-27 09:00", tz="UTC"),
                       "short", stop_px=105, target_px=90, time_stop_h=72)
    assert ex is not None
    exit_px, reason, _ = ex
    assert reason == "target", f"short deve chiudere in target, non {reason}"
    assert exit_px == 90


def test_simulate_exit_long_uses_correct_direction():
    from scripts.backfill_lost_positions import simulate_exit
    import pandas as pd
    # entry 100, long. stop 95 (sotto), target 110 (sopra)
    candles = _mk_candles([
        ("2026-06-27 09:00", 98, 102, 100),
        ("2026-06-27 10:00", 96, 111, 110),  # high 111 >= target 110 -> target hit (long sale)
    ])
    ex = simulate_exit(candles, pd.Timestamp("2026-06-27 09:00", tz="UTC"),
                       "long", stop_px=95, target_px=110, time_stop_h=72)
    assert ex is not None
    exit_px, reason, _ = ex
    assert reason == "target"
    assert exit_px == 110


def test_simulate_exit_short_stop_above():
    # short stoppato: il prezzo SALE sopra lo stop (non scende sotto)
    from scripts.backfill_lost_positions import simulate_exit
    import pandas as pd
    candles = _mk_candles([
        ("2026-06-27 09:00", 98, 102, 100),
        ("2026-06-27 10:00", 99, 106, 105),  # high 106 >= stop 105 -> stop hit (short sale)
    ])
    ex = simulate_exit(candles, pd.Timestamp("2026-06-27 09:00", tz="UTC"),
                       "short", stop_px=105, target_px=90, time_stop_h=72)
    assert ex is not None
    _, reason, _ = ex
    assert reason == "stop"
