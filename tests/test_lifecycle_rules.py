"""Test di paper_stats (basket Sharpe per-asset) e validate_spec_risk (regole 3, 5)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backtest.lifecycle import GLOBAL_RISK_CAPS, paper_stats, validate_spec_risk


def _write_journal(tmp_path: Path, rows: list[dict]) -> None:
    """Scrive un journal.jsonl fittizio nel tmp_path e patcha lifecycle.JOURNAL."""
    import backtest.lifecycle as lc
    jf = tmp_path / "journal.jsonl"
    jf.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    lc.JOURNAL = jf


def _write_state(tmp_path: Path, strat: str, equity: float) -> None:
    import backtest.lifecycle as lc
    paper_dir = tmp_path / "paper"
    paper_dir.mkdir(exist_ok=True)
    sf = paper_dir / "state.json"
    sf.write_text(json.dumps({strat: {"equity": equity}}))
    lc.ROOT = tmp_path


def _trade(strategy: str, sym: str, pnl: float, stop_pct: float = 0.04) -> dict:
    """Genera open+close pair per un trade con R-multiple derivato."""
    entry = 100.0
    size = 1000.0
    return [
        {"type": "open", "strategy": strategy, "symbol": sym,
         "entry_px": entry, "stop_px": entry * (1 - stop_pct), "size_usd": size},
        {"type": "close", "strategy": strategy, "symbol": sym,
         "exit_px": entry + (pnl / size) * entry, "pnl_usd": pnl},
    ]


def test_paper_stats_basket_mean_r(tmp_path, monkeypatch):
    """basket_mean_r = mean dei mean-R per-asset. Con trade count diseguali
    tra simboli, pooled e basket divergono (basket penalizza concentrazione)."""
    rows = []
    # BTC: 3 trade, tutti +100 → mean_r = 2.5
    for _ in range(3):
        rows += _trade("test-strat", "BTC", 100)
    # ZEC: 1 trade -50 → mean_r = -1.25
    rows += _trade("test-strat", "ZEC", -50)
    _write_journal(tmp_path, rows)
    monkeypatch.setattr("backtest.lifecycle.JOURNAL", tmp_path / "journal.jsonl")
    monkeypatch.setattr("backtest.lifecycle.ROOT", tmp_path)
    st = paper_stats("test-strat")
    # pooled: (3*2.5 + 1*(-1.25)) / 4 = 1.5625 → pooled mean_r alto
    assert st["mean_r"] > 1.5
    # basket: (2.5 + (-1.25)) / 2 = 0.625 → basket più basso
    assert st["basket_mean_r"] < 0.7
    assert st["basket_mean_r"] < st["mean_r"]  # concentrazione penalizzata
    assert st["symbols_traded"] == 2


def test_paper_stats_basket_concentration_penalty(tmp_path, monkeypatch):
    """Strategia che vince su 1 asset con molti trade e perde su 1 con pochi:
    pooled mean_r > basket_mean_r (concentrazione mascherata dal pooled)."""
    rows = []
    # BTC: 10 trade +50 → mean_r = 1.25 (dominante nel pooled)
    for _ in range(10):
        rows += _trade("test-strat", "BTC", 50)
    # ZEC: 1 trade -40 → mean_r = -1.0
    rows += _trade("test-strat", "ZEC", -40)
    _write_journal(tmp_path, rows)
    monkeypatch.setattr("backtest.lifecycle.JOURNAL", tmp_path / "journal.jsonl")
    monkeypatch.setattr("backtest.lifecycle.ROOT", tmp_path)
    st = paper_stats("test-strat")
    # pooled: (10*1.25 + 1*(-1)) / 11 = 1.045 → positivo
    assert st["mean_r"] > 1.0
    # basket: (1.25 + (-1.0)) / 2 = 0.125 → molto più basso
    assert st["basket_mean_r"] < 0.2
    assert st["basket_mean_r"] < st["mean_r"]  # concentrazione penalizzata
    assert st["symbols_traded"] == 2


def test_paper_stats_equity_dd_pct(tmp_path, monkeypatch):
    """equity_dd_pct legge da state.json (regola P1-b)."""
    rows = []
    rows += _trade("test-strat", "BTC", 100)
    _write_journal(tmp_path, rows)
    _write_state(tmp_path, "test-strat", 8200.0)  # -18%
    monkeypatch.setattr("backtest.lifecycle.JOURNAL", tmp_path / "journal.jsonl")
    monkeypatch.setattr("backtest.lifecycle.ROOT", tmp_path)
    st = paper_stats("test-strat")
    assert st["equity_dd_pct"] == -18.0


def test_paper_stats_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("backtest.lifecycle.JOURNAL", tmp_path / "journal.jsonl")
    monkeypatch.setattr("backtest.lifecycle.ROOT", tmp_path)
    (tmp_path / "journal.jsonl").write_text("")
    st = paper_stats("nonexistent")
    assert st["n_closed"] == 0
    assert st["basket_mean_r"] == 0.0
    assert st["basket_sharpe_r"] == 0.0
    assert st["symbols_traded"] == 0


def test_validate_spec_risk_ok():
    """Spec entro i caps → nessun warning."""
    spec = {"id": "test-ok", "risk": {"max_leverage": 2, "max_concurrent_positions": 5,
                                       "risk_per_trade_pct": 1.0}}
    assert validate_spec_risk(spec) == []


def test_validate_spec_risk_leverage_exceeds():
    spec = {"id": "test-bad", "risk": {"max_leverage": 6, "max_concurrent_positions": 3,
                                        "risk_per_trade_pct": 1.0}}
    warns = validate_spec_risk(spec)
    assert any("max_leverage 6" in w for w in warns)


def test_validate_spec_risk_concurrent_exceeds():
    spec = {"id": "test-bad", "risk": {"max_leverage": 2, "max_concurrent_positions": 20,
                                        "risk_per_trade_pct": 1.0}}
    warns = validate_spec_risk(spec)
    assert any("max_concurrent_positions 20" in w for w in warns)


def test_validate_spec_risk_by_class_override_flagged():
    """by_class.max_leverage > cap è flaggato (consentito ma surfaced)."""
    spec = {"id": "test-cls", "risk": {"max_leverage": 2, "max_concurrent_positions": 3,
                                        "risk_per_trade_pct": 1.0},
            "exit": {"by_class": {"stock": {"max_leverage": 5, "target_r": 1.8}}}}
    warns = validate_spec_risk(spec)
    assert any("by_class.stock.max_leverage 5" in w for w in warns)


def test_validate_spec_risk_missing_block():
    spec = {"id": "test-missing"}
    warns = validate_spec_risk(spec)
    assert any("risk mancante" in w for w in warns)


def test_global_caps_sane():
    """I caps globali non devono essere assurdi — sanity check del config."""
    assert GLOBAL_RISK_CAPS["max_leverage"] >= 2   # almeno quanto desk LLM
    assert GLOBAL_RISK_CAPS["max_concurrent_positions"] >= 3
    assert 0 < GLOBAL_RISK_CAPS["max_risk_per_trade_pct"] <= 5
