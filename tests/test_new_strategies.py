"""Test del nuovo segnale volume_profile e delle strategie di ricerca 2026-06-22."""
import json
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


def test_agents_decision_source_routing():
    from scripts.agents_paper import _matches_source
    untagged = {"proposal": {}}                                  # decisione del desk storico
    assert _matches_source(untagged, "agents-v1")                # → agents-v1
    assert _matches_source(untagged, "agents-rr2-v1") is False   # NON la variante (usa --source agents-v1)
    assert _matches_source(untagged, "claude-strategy-v1") is False  # NON claude (era il bug)
    assert _matches_source({"strategy": "claude-strategy-v1"}, "claude-strategy-v1")
    assert _matches_source({"strategy": "geopolitics-v1"}, "agents-v1") is False


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


# --- test del nuovo segnale Nadaraya-Watson (firma DaviddTech, 2026-06-26) ---

NW_STRATS = ["lux-nw-continuation-v1", "lux-nw-tsmom-v1", "lux-nw-liq-v1",
             "lux-regime-3leg-v1"]


def _nw_candles(n: int = 200, base: float = 100.0) -> pd.DataFrame:
    """Serie piatta con piccolo rumore, poi uno spike rialzista netto e sostenuto
    alla fine: il kernel baseline (peak sulla barra corrente) resta vicino al livello
    piatto, lo spike rompe la banda MAD superiore sulle barre di transizione."""
    ts = pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC")
    rng = np.random.default_rng(42)
    close = base + rng.normal(0, 0.05, n)         # piatta e poco volatile
    close[-6:] = base * 1.20                       # spike netto +20% sostenuto
    high, low = close * 1.001, close * 0.999
    vol = np.full(n, 1000.0)
    return pd.DataFrame({"ts": ts, "open": close, "high": high, "low": low,
                         "close": close, "volume": vol})


def test_nadaraya_watson_in_registry():
    assert "nadaraya_watson" in SIGNALS


def test_nadaraya_watson_extension_up():
    from backtest.signals import nadaraya_watson
    c = _nw_candles()
    out = nadaraya_watson({"candles": c}, lookback=72, bandwidth=12.0, mult=2.0)
    assert len(out) == len(c)
    assert set(np.unique(out.to_numpy())).issubset({-1, 0, 1})
    assert (out.iloc[:71] == 0).all()               # burn-in: niente lettura senza kernel
    assert (out.iloc[-10:] == 1).any()              # lo spike rompe la banda superiore
    # controllo: serie totalmente piatta (niente spike) → sempre neutro
    flat = c.copy(); flat.close = 100.0; flat.high = flat.close * 1.001; flat.low = flat.close * 0.999
    assert (nadaraya_watson({"candles": flat}, lookback=72, bandwidth=12.0, mult=2.0) == 0).all()


def test_nadaraya_watson_edge_only_transition():
    from backtest.signals import nadaraya_watson
    c = _nw_candles()
    persistent = nadaraya_watson({"candles": c}, lookback=72, bandwidth=12.0, mult=2.0)
    edge = nadaraya_watson({"candles": c}, lookback=72, bandwidth=12.0, mult=2.0,
                           edge_only=True)
    # edge_only NON aggiunge mai estensioni: ⊆ del persistente
    assert ((edge != 0) <= (persistent != 0)).all()
    # lo spike genera almeno una barra attiva in entrambi, ma edge_only ne attiva di meno
    # o uguali (solo la transizione): mai piu' del persistente
    assert (edge != 0).sum() <= (persistent != 0).sum()


def test_nadaraya_watson_short_series_neutral():
    from backtest.signals import nadaraya_watson
    c = _nw_candles(n=50)                           # < lookback (72)
    out = nadaraya_watson({"candles": c}, lookback=72)
    assert (out == 0).all()                         # finestra insufficiente → neutro


def test_nw_strategies_load_and_compile():
    c = _nw_candles(n=400)
    data = {"candles": c, "symbol": "BTC", "funding": None, "flow": None,
            "news_events": None, "cot": None}
    for sid in NW_STRATS:
        spec = load(ROOT / "strategies" / "generated" / f"{sid}.yaml")
        strat, sigs = compile_strategy(spec, data)
        out = strat(c)
        assert "exposure" in out and "target_r" in out


# --- regime filter efficiency_ratio (Kaufman, 2026-06-26) ---

def test_efficiency_ratio_in_registry():
    from backtest.signals import SIGNALS
    assert "efficiency_ratio" in SIGNALS


def test_efficiency_ratio_trending_vs_chop():
    """Una serie con trend pulito netto deve essere trending; una piatta rumorosa no."""
    from backtest.signals import efficiency_ratio
    n = 600
    ts = pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC")
    # trend pulito: close sale monotonically
    trend_close = np.linspace(100, 150, n)
    rng = np.random.default_rng(0)
    chop_close = 100 + rng.normal(0, 0.3, n)          # piatta e rumorosa
    for close, expect_nonzero in [(trend_close, True), (chop_close, False)]:
        c = pd.DataFrame({"ts": ts, "open": close, "high": close * 1.001,
                          "low": close * 0.999, "close": close, "volume": np.full(n, 1000.0)})
        out = efficiency_ratio({"candles": c}, lookback=168, trend_pct=60)
        assert set(np.unique(out.to_numpy())).issubset({0, 1})
        assert (out.iloc[:167] == 0).all()           # burn-in
        if expect_nonzero:
            assert (out == 1).any()                  # il trend pulito e' riconosciuto trending


def test_xsection_cache_refresh_covers_window():
    """La cache xsection era stale (201g vs 360g candele, degradava a neutro i primi
    5 mesi). Rigenerata a 12m il 26/06. Sanity: ora copre ~tutto l'arco candele."""
    c = pd.read_parquet(ROOT / "data/candles/BTC.parquet").tail(12 * 30 * 24)
    xs = pd.read_parquet(ROOT / "data/xsection/BTC.parquet")
    candle_span = (c.ts.max() - c.ts.min()).days
    cache_span = (xs.ts.max() - xs.ts.min()).days
    assert cache_span > candle_span * 0.8         # cache copre >=80% dell'arco candele
    assert 0 <= xs.rank_pct.min() and xs.rank_pct.max() <= 100


# --- engine:portfolio ripresa 26/06 (strumentazione paper) ---

def test_portfolio_stats_reads_rebalance_equity(tmp_path, monkeypatch):
    """xsmom-port fu ritirata solo perche' la strumentazione paper non registrava
    trade chiusi (logga rebalance/heartbeat con equity, non open/close). paper_stats
    ora deriva Sharpe/ret/maxDD dall'equity curve sintetica per engine:portfolio."""
    import backtest.lifecycle as L
    fake = tmp_path / "journal.jsonl"
    events = [10000, 10100, 9950, 10300, 10600, 10500, 10800]
    lines = []
    for i, eq in enumerate(events):
        lines.append(json.dumps({"type": "rebalance", "strategy": "xsmom-port-v1",
                                 "equity": eq, "logged_at": f"2026-06-0{i+1}"}))
    fake.write_text("\n".join(lines) + "\n")
    monkeypatch.setattr(L, "JOURNAL", fake)
    st = L.paper_stats("xsmom-port-v1")
    assert st["total_pnl"] == 800.0          # 10800 - 10k
    assert st["sharpe_r"] > 0                # curva crescente
    assert st["n_closed"] == 7               # 7 letture equity
    # schema compatibile con promote/dashboard: stessi campi
    for k in ("total_pnl", "sharpe_r", "equity_dd_pct", "basket_mean_r", "basket_sharpe_r"):
        assert k in st


def test_portfolio_stats_empty_neutral():
    """Nessun evento rebalance → stats neutri (non crash, coerenza schema)."""
    import backtest.lifecycle as L
    st = L._portfolio_stats([])
    assert st["n_closed"] == 0 and st["total_pnl"] == 0.0 and st["sharpe_r"] == 0.0


def test_xsmom_port_active_and_not_in_per_symbol_loop():
    """xsmom-port-v1 e' ripresa (status challenger) ma resta FUORI dal loop
    per-simbolo (paper_all) perche' ha il suo runner (engine:portfolio)."""
    from backtest.lifecycle import active_specs
    spec = load(ROOT / "strategies/generated/xsmom-port-v1.yaml")
    assert spec["engine"] == "portfolio"
    assert spec["status"] == "challenger"          # ripresa 26/06
    active = [s["id"] for _, s in active_specs()]
    assert "xsmom-port-v1" not in active            # non nel loop per-simbolo


def test_portfolio_backtest_12m_edge_holds():
    """L'edge cross-sectional a portafoglio e' confermato a 12m (regression gate).
    Era +29.4% a 6m nel deploy originale; a 12m e' +79.8% Sharpe 2.11. Questo test
    blocca regressioni sull'engine portfolio se qualcuno tocca xs_momentum_weights."""
    from backtest.portfolio import PortfolioBacktest, xs_momentum_weights, equal_weight_bh
    cols = {}
    for s in ["BTC", "ETH", "SOL", "XRP", "SUI", "NEAR", "WLD", "ZEC", "CRV"]:
        cols[s] = pd.read_parquet(ROOT / f"data/candles/{s}.parquet").tail(12*30*24).set_index("ts")["close"]
    px = pd.DataFrame(cols).sort_index()
    bt = PortfolioBacktest(px)
    eq, ret, meta = bt.run(xs_momentum_weights, lookback_h=168, rebalance_h=168)
    total_ret = float(eq.iloc[-1] - 1)
    sharpe = float(ret.mean() / ret.std() * np.sqrt(24*365)) if ret.std() else 0
    assert total_ret > 0.5, f"edge scomparso: ret {total_ret:.2f}"
    assert sharpe > 1.5, f"sharpe degradato: {sharpe:.2f}"
    # benchmark: dollar-neutral batte equal-weight B&H
    bheq = equal_weight_bh(px)
    assert total_ret > float(bheq.iloc[-1] - 1)


def test_xsmom_multihorizon_active_and_conservative():
    """xsmom-multihorizon-v1 e' il compagno conservativo di xsmom-port: stesso edge,
    DD minore (-16% vs -19%). engine:portfolio, in produzione."""
    from backtest.lifecycle import all_specs
    spec = load(ROOT / "strategies/generated/xsmom-multihorizon-v1.yaml")
    assert spec["engine"] == "portfolio"
    assert spec["status"] == "challenger"
    assert spec["portfolio"]["lookbacks_h"] == [96, 168, 336]
    active = [s["id"] for _, s in all_specs() if s.get("engine") == "portfolio"
             and s["status"] in ("champion", "challenger")]
    assert "xsmom-multihorizon-v1" in active
    assert "xsmom-port-v1" in active           # il core resta


def test_funding_carry_factor_is_weak():
    """Il funding carry NON esplode a portfolio come xsmom (era l'ipotesi). Test di
    documentazione onesta: l'edge carry e' debole anche come book (Sharpe < 1).
    Blocca futuri tentativi di riviverlo senza nuova evidenza."""
    from scripts.backtest_portfolio_factors import carry_weights
    cols = {}
    for s in ["BTC", "ETH", "SOL", "XRP", "SUI", "NEAR", "WLD", "ZEC", "CRV"]:
        cols[s] = pd.read_parquet(ROOT / f"data/funding/{s}.parquet").set_index("ts")["rate"]
    fund = pd.DataFrame(cols).sort_index().ffill()
    # sanity: carry_weights e' dollar-neutral (somma ~0) e long/short equal-gamba
    w = carry_weights(fund.iloc[-1], gross=1.0)
    assert abs(w.sum()) < 0.01                      # dollar-neutral
    assert (w > 0).any() and (w < 0).any()          # ha long e short


def test_crossasset_expansion_degrades_edge():
    """L'espansione cross-asset di xsmom e' FALSIFICATA (research_crossasset.py 26/06):
    - crypto-only IC +0.089 t+21 (il nostro edge forte)
    - cross-asset vol-normalizzato IC +0.023 t+5.6 (degradato)
    - commodities-only portfolio -33% (market-neutral fallisce in trend up)
    Regression gate: blocca se l'IC crypto degrada o se cross-asset supera crypto."""
    from scripts.research_crossasset import panel, row_ic
    px_all = panel(["BTC","ETH","SOL","XRP","SUI","NEAR","WLD","ZEC","CRV",
                    "xyz_GOLD","xyz_SILVER","xyz_CL","xyz_BRENTOIL","xyz_NATGAS"], 12)
    crypto = ["BTC","ETH","SOL","XRP","SUI","NEAR","WLD","ZEC","CRV"]
    px_crypto = px_all[crypto]
    raw_crypto = px_crypto.pct_change(168)
    fwd_crypto = px_crypto.pct_change(168).shift(-168)
    ic_c, _, t_c = row_ic(raw_crypto, fwd_crypto)
    # l'edge crypto deve restare forte (regression guard sul nostro asset principale)
    assert ic_c > 0.05 and t_c > 10, f"edge crypto degradato: IC {ic_c:.3f} t {t_c:.1f}"
    # cross-asset vol-normalizzato deve restare PIU' DEBOLE di crypto-only
    vol = px_all.pct_change().rolling(168, min_periods=84).std()
    volnorm = (px_all.pct_change(168) / vol.replace(0, np.nan)).fillna(0)
    fwd_all = px_all.pct_change(168).shift(-168)
    ic_xa, _, t_xa = row_ic(volnorm, fwd_all)
    assert t_xa < t_c, "cross-asset non dovrebbe superare crypto-only (falsificato 26/06)"


# --- HIGH-VOL: 2° edge ortogonale forte trovato (26/06) ---

def test_highvol_factor_is_strong_and_orthogonal():
    """HIGH-VOL (long asset piu' volatili) e' il 2° edge FORTE del progetto, ortogonale
    a xsmom. Regression gate: Sharpe>1.5 E correlazione rendimenti con xsmom <0.5
    (se sale, e' momentum mascherato, non edge separato). Trovato nello zoo a 8 fattori."""
    from scripts.backtest_factor_zoo import grid_panel, run_factor, terzile_weights, stats
    from backtest.portfolio import PortfolioBacktest
    CRYPTO = ["BTC","ETH","SOL","XRP","SUI","NEAR","WLD","ZEC","CRV"]
    px = grid_panel(CRYPTO, 12)
    bt = PortfolioBacktest(px)
    vol = px.pct_change().rolling(72, min_periods=36).std()
    eq, ret, _ = run_factor(bt, vol.reindex(columns=px.columns), terzile_weights, 168)
    r, sh, dd = stats(eq, ret)
    assert sh > 1.5, f"high-vol edge degradato: Sharpe {sh:.2f}"
    assert r > 0.5, f"high-vol return crollato: {r:.2f}"
    # ortogonalita': correlazione rendimenti con xsmom deve restare bassa
    xs = px.pct_change(168)
    eqx, retx, _ = run_factor(bt, xs.reindex(columns=px.columns), terzile_weights, 168)
    corr = ret.corr(retx)
    assert abs(corr) < 0.5, f"high-vol e xsmom troppo correlati ({corr:+.2f}) — non e' ortogonale"


def test_highvol_strategies_load_and_active():
    """highvol-port-v1 e xsmom-highvol-combo-v1 sono engine:portfolio attivi."""
    from backtest.lifecycle import all_specs
    spec = load(ROOT / "strategies/generated/highvol-port-v1.yaml")
    assert spec["engine"] == "portfolio"
    assert spec["portfolio"]["factor"] == "highvol"
    assert spec["portfolio"]["vol_lookback_h"] == 72
    combo = load(ROOT / "strategies/generated/xsmom-highvol-combo-v1.yaml")
    assert combo["portfolio"]["factors"] == ["xsmom", "highvol"]
    assert combo["portfolio"]["weights"] == [0.7, 0.3]
    active = [s["id"] for _, s in all_specs() if s.get("engine") == "portfolio"
             and s["status"] in ("champion", "challenger")]
    assert "highvol-port-v1" in active
    assert "xsmom-highvol-combo-v1" in active


def test_portfolio_runner_supports_highvol_factor():
    """portfolio_paper.py dispatcha su vol_signal quando factor=highvol."""
    import scripts.portfolio_paper as pp
    assert callable(pp.vol_signal)
    assert callable(pp.combo_signal)


# --- test delle modifiche 25/06 (lux-flow-confluence + GLM gate + geo time_stop) ---

def test_lux_flow_confluence_active_and_valid():
    """lux-flow-confluence-v1 e' la base di conoscenza (parent lineage) ma e' stata
    RITIRATA il 26/06: Sharpe 0.71/DSR 0.87 e' rumore colorato vs xsmom-port 2.11.
    Le per-simbolo sono state bocciate; il loop e' ora tutto engine:portfolio.
    Questo test verifica la storia: rimozione kronos (falsificato) + retirement 26/06."""
    from backtest.lifecycle import active_specs
    spec = load(ROOT / "strategies/generated/lux-flow-confluence-v1.yaml")
    assert spec["parent"] == "lux-confluence-rr2-v1"   # lineage: rimuove la gamba kronos
    assert "kronos_forecast" not in str(spec["signals"])  # kronos falsificato, non piu gambo AND
    assert spec["status"] == "retired"                  # bocciata 26/06 (per-simbolo mediocre)
    active = [s["id"] for _, s in active_specs()]
    assert "lux-flow-confluence-v1" not in active       # fuori dal loop


def test_glm_gate_fallback_conviction():
    """Il gate GLM (25/06) accetta tsmom+xsection allineati (via preferenziale) OPPURE
    tsmom + conviction>=2 dai vote (via di fallback quando xsection degrada a neutro
    per cache assente in cloud). Il gate originale AND a 2 gambe era sempre chiuso."""
    from scripts.glm_strategy import gate_candidates
    ctx = {"assets": {
        "BTC": {"signals": {"tsmom": 1, "xsection_momentum": 1, "news_event": 0,
                            "kronos_vol": 0, "funding_percentile": 0,
                            "hmm_regime": 1, "taker_flow": 1, "smart_money_ratio": 0,
                            "oi_trend": 0}, "atr_pct": 3.0},   # core allineato
        "ETH": {"signals": {"tsmom": 1, "xsection_momentum": 0, "news_event": 0,
                            "kronos_vol": 0, "funding_percentile": 0,
                            "hmm_regime": 1, "taker_flow": 1, "smart_money_ratio": 1,
                            "oi_trend": 0}, "atr_pct": 2.5},  # fallback conviction=3
        "SOL": {"signals": {"tsmom": 1, "xsection_momentum": 0, "news_event": 0,
                            "kronos_vol": 0, "funding_percentile": 0,
                            "hmm_regime": 0, "taker_flow": 0, "smart_money_ratio": 0,
                            "oi_trend": 0}, "atr_pct": 2.0},  # conviction 0 → scartato
    }}
    cands = {c["symbol"]: c for c in gate_candidates(ctx)}
    assert "BTC" in cands and cands["BTC"]["core_aligned"] is True
    assert "ETH" in cands and cands["ETH"]["core_aligned"] is False   # via fallback
    assert "SOL" not in cands                                        # conviction insufficiente


def test_geo_time_stop_fallback(monkeypatch, tmp_path):
    """open_from_decision usa 96h di fallback se l'LLM emette time_stop_h=0
    (bug latente: posizione eterna senza time-stop). Fix geopolitics 25/06.

    Isolamento: log_event scrive sul journal REALE se non monkeypatchato →
    inquinerebbe paper/journal.jsonl (e il cron lo committeva). Redirect a tmp."""
    import importlib, scripts.geopolitics_paper as geo
    import scripts.paper_trade as pt
    importlib.reload(geo)
    fake_journal = tmp_path / "journal.jsonl"
    monkeypatch.setattr(pt, "JOURNAL", fake_journal)
    monkeypatch.setattr(geo, "log_event", pt.log_event)
    # proposta con time_stop_h=0 (LLM malfatto)
    d = {"proposal": {"symbol": "BTC", "direction": "long", "leverage": 1,
                      "risk_pct": 1.0, "stop_pct": 4.0, "target_r": 2.0,
                      "time_stop_h": 0, "thesis": "t", "invalidation": "i"},
         "risk": {"size_multiplier": 1.0, "verdict": "approve"}, "logged_at": "2026-06-25T00:00:00+00:00"}
    # monkeypatch fetch_live per non toccare la rete
    monkeypatch.setattr(geo, "fetch_live", lambda sym, lookback_h=50: {"candles": _candles()})
    pos = geo.open_from_decision(d, 10000.0)
    assert pos is not None
    assert pos["time_stop_h"] == 96          # fallback, non 0 (che era il bug)
    # l'evento open va nel journal REDIRECT (tmp), non in quello reale
    assert fake_journal.exists() and json.loads(fake_journal.read_text())["thesis"] == "t"


def test_agents_time_stop_fallback(monkeypatch, tmp_path):
    """agents_paper.open_from_decision usa lo stesso fallback 96h del desk geo se
    l'LLM emette time_stop_h=0 (bug latente simmetrico: 0h uscirebbe a ogni candela).
    Fix consistenza 25/06. Journal redirect a tmp (vedi test geo per la motivazione)."""
    import importlib, scripts.agents_paper as ag
    import scripts.paper_trade as pt
    importlib.reload(ag)
    fake_journal = tmp_path / "journal.jsonl"
    monkeypatch.setattr(pt, "JOURNAL", fake_journal)
    d = {"proposal": {"symbol": "BTC", "direction": "long", "leverage": 1,
                      "risk_pct": 1.0, "stop_pct": 4.0, "target_r": 2.0,
                      "time_stop_h": 0, "thesis": "t", "invalidation": "i"},
         "risk": {"size_multiplier": 1.0, "verdict": "approve"}, "logged_at": "2026-06-25T00:00:00+00:00"}
    monkeypatch.setattr(ag, "fetch_live", lambda sym, lookback_h=50: {"candles": _candles()})
    pos = ag.open_from_decision(d, 10000.0)
    assert pos is not None
    assert pos["time_stop_h"] == 96          # fallback, non 0
    assert fake_journal.exists() and json.loads(fake_journal.read_text())["thesis"] == "t"

