"""Test: veto stop<ATR nel desk (decide.hard_check) + filtro universe.exclude."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest.lifecycle import paper_symbols
from scripts.decide import hard_check

BASE = {"action": "trade", "symbol": "WLD", "direction": "long", "leverage": 1.5,
        "risk_pct": 1.0, "stop_pct": 3.0, "target_r": 2.0, "thesis": "x", "invalidation": "y"}


def test_stop_below_atr_vetoed():
    # ATR 4% → stop 3% è dentro il rumore → veto
    errs = hard_check({**BASE, "stop_pct": 3.0}, atr_by_symbol={"WLD": 4.0})
    assert any("ATR" in e for e in errs)


def test_stop_above_atr_ok():
    # ATR 2% → stop 3% sta fuori dal rumore → nessun veto
    errs = hard_check({**BASE, "stop_pct": 3.0}, atr_by_symbol={"WLD": 2.0})
    assert errs == []


def test_atr_rule_skipped_without_context():
    # senza atr_by_symbol (es. --check) la regola ATR non si applica
    errs = hard_check({**BASE, "stop_pct": 3.0})
    assert errs == []


def test_absolute_range_still_enforced():
    errs = hard_check({**BASE, "stop_pct": 0.04}, atr_by_symbol={"WLD": 0.01})
    assert any("range" in e for e in errs)


def test_no_trade_passes():
    assert hard_check({"action": "no_trade"}, atr_by_symbol={"WLD": 9.0}) == []


def test_universe_exclude_filters():
    spec = {"universe": {"exclude": ["WLD", "CRV"]}, "paper_symbols": "BTC,ETH,WLD,CRV,SOL"}
    assert paper_symbols(spec) == "BTC,ETH,SOL"


def test_universe_exclude_csv_form():
    spec = {"universe": {"exclude": "WLD"}, "paper_symbols": ["BTC", "WLD", "SOL"]}
    assert paper_symbols(spec) == "BTC,SOL"


def test_no_exclude_keeps_all():
    spec = {"paper_symbols": "BTC,ETH,SOL"}
    assert paper_symbols(spec) == "BTC,ETH,SOL"


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
