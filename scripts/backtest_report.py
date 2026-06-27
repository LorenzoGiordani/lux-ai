"""Backtest onesto (basket multi-asset) delle strategie attive → paper/backtests.json.

Regola #5: MAI backtest su singolo asset. Ogni strategia è valutata sul suo basket
dichiarato (paper_symbols), metrica aggregata = media per-symbol (mean Sharpe, non
pooled: una strategia che vince su BTC e perde su 8 alt non passa).

Realismo engine (tutto opt-in, onesto in entrambe le direzioni):
  - funding STORICO reale per-symbol (la costante legacy sovrastimava e nascondeva
    i flip di segno nei mesi bear) — abilitato dove ci sono i dati;
  - slippage size-aware square-root (k=0.5): rivela i Profit Mirage sugli asset
    illiquidi, certifica la robustezza sui liquidi.

Output: paper/backtests.json con, per strategia: aggregate + per-symbol + finestra.
Letto da dashboard.py → sezione "Backtest" della dashboard pubblica.

Uso:
  uv run scripts/backtest_report.py                # 6 mesi trailing, strategie attive + riferimento
  uv run scripts/backtest_report.py --months 12    # finestra più lunga
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np

from backtest.engine import Backtest
from backtest.metrics import HOURS_PER_YEAR, compute
from backtest.portfolio import PortfolioBacktest, xs_momentum_weights
from backtest.strategy import compile_strategy, load
from backtest.walkforward import evaluate

DATA = ROOT / "data"
OUT = ROOT / "paper" / "backtests.json"
MONTHS_DEFAULT = 6
IMPACT_K = 0.5   # square-root market impact (Almgren 2005) — rivela mirage su illiquidi

# Strategie da mostrare: tutte le challenger attive + il benchmark documentato (tsmom).
# Aggiornato leggendo lo status dagli artefatti.
BENCHMARK = "tsmom-v1"


def _read(path: Path) -> pd.DataFrame | None:
    return pd.read_parquet(path) if path.exists() else None


def _load_candles(symbol: str) -> pd.DataFrame | None:
    """Candele orarie per un simbolo: dal parquet storico se presente (locale,
    dati precomputati), ALTRIMENTI via fetch live con cache su disco.

    Il backtest report girava solo dove data/candles/*.parquet esisteva gia'
    (locale). Nel cloud quei file sono gitignored e il checkout e' vuoto, quindi
    _dataset ritornava None per ogni simbolo → backtest con 0 strategie
    (sintomo: i backtest sparivano dalla dashboard nei run cloud). Ora cade
    su fetch_live_cached (rete + cache oraia in /tmp) come fa paper_trade, cosi'
    il report funziona ovunque ci sia connettivita' alle API Hyperliquid."""
    import sys
    cp = DATA / "candles" / f"{symbol}.parquet"
    if cp.exists():
        return pd.read_parquet(cp)
    # fallback rete: cache di modulo riusata tra simboli e strategie nello stesso run
    sys.path.insert(0, str(ROOT))
    from pipeline.live import fetch_live_cached
    try:
        # lookback ampio: serve la finestra massima dei segnali (tsmom long_h=720)
        return fetch_live_cached(symbol, lookback_h=5000)["candles"]
    except Exception:
        return None


def _dataset(symbol: str, months: int) -> dict | None:
    """Candles + dati ausiliari per un simbolo, finestra trailing coerente."""
    candles = _load_candles(symbol)
    if candles is None:
        return None
    candles = candles.tail(months * 30 * 24).reset_index(drop=True)
    if len(candles) < 30 * 24:   # troppi pochi dati
        return None
    return {
        "candles": candles, "symbol": symbol,
        "funding": _read(DATA / "funding" / f"{symbol}.parquet"),
        "flow": _read(DATA / "flow" / f"{symbol}.parquet"),
        "cot": _read(DATA / "cot" / f"{symbol}.parquet"),
        "news_events": _read(DATA / "news" / "gdelt_events.parquet"),
    }


def _eval_symbol(spec: dict, data: dict) -> dict | None:
    """Una strategia su un simbolo: metriche + consistenza, con engine realistico."""
    try:
        strat, _ = compile_strategy(spec, data)
    except Exception:
        return None
    bt = Backtest(data["candles"], max_leverage=spec["risk"]["max_leverage"],
                  funding_hist=data.get("funding"), impact_k=IMPACT_K)
    equity = bt.run(strat)
    if equity.empty:
        return None
    m = compute(equity, bt.trades)
    ev = evaluate(equity, data["candles"])
    exits = pd.Series([t["reason"] for t in bt.trades]).value_counts().to_dict() if bt.trades else {}
    return {
        "symbol": data["symbol"],
        "ret": round(m["total_return"], 4),
        "sharpe": round(m["sharpe"], 2),
        "max_dd": round(m["max_drawdown"], 4),
        "trades": m["n_trades"],
        "win_rate": round(m["win_rate"], 3),
        "pf": round(m["profit_factor"], 2) if m["profit_factor"] != float("inf") else None,
        "consistency": ev["consistency"],
        "exits": exits,
    }


def _aggregate(per_symbol: list[dict]) -> dict:
    """Media per-symbol (mai pooled). Robusta a concentrazioni su un asset."""
    n = len(per_symbol)
    if not n:
        return {}
    sharpe = sum(p["sharpe"] for p in per_symbol) / n
    ret = sum(p["ret"] for p in per_symbol) / n
    worst_dd = min(p["max_dd"] for p in per_symbol)
    pos = sum(1 for p in per_symbol if p["ret"] > 0)
    folds_pos = sum(int(p["consistency"].split("/")[0]) for p in per_symbol)
    folds_tot = sum(int(p["consistency"].split("/")[1].split()[0]) for p in per_symbol)
    return {
        "mean_sharpe": round(sharpe, 2),
        "mean_return": round(ret, 4),
        "worst_drawdown": round(worst_dd, 4),
        "positive_symbols": f"{pos}/{n}",
        "consistency": f"{folds_pos}/{folds_tot}",
    }


def backtest_strategy(spec_path: Path, months: int) -> dict | None:
    spec = load(spec_path)
    symbols = [s.strip() for s in str(spec.get("paper_symbols", "")).split(",") if s.strip()]
    if not symbols:
        return None
    per_symbol = []
    for sym in symbols:
        data = _dataset(sym, months)
        if not data:
            continue
        res = _eval_symbol(spec, data)
        if res:
            per_symbol.append(res)
    if not per_symbol:
        return None
    window = _dataset(symbols[0], months)["candles"]
    return {
        "id": spec["id"],
        "status": spec.get("status", "?"),
        "thesis": spec.get("thesis", "")[:280],
        "is_benchmark": spec["id"] == BENCHMARK,
        "window": f"{window.ts.min():%Y-%m-%d} → {window.ts.max():%Y-%m-%d}",
        "basket_size": len(per_symbol),
        "aggregate": _aggregate(per_symbol),
        "per_symbol": per_symbol,
    }


# ---------- engine portfolio (cross-section, dollar-neutral) ----------
# Le strategie portfolio non hanno entry/exit per-simbolo: l'edge e' nello spread
# mantenuto tra le gambe. Si backtesta come un unico portafoglio ribilanciato, e la
# metrica e' sull'equity di portafoglio (niente breakdown per-asset: non esistono
# trade per-simbolo). Il fattore (xsmom/highvol/combo) determina COSA si ranka.

def _close_panel(symbols: list[str], months: int) -> pd.DataFrame | None:
    """Panel close allineato (inner join su ts comuni) per il basket.
    Tollerante alla assenza dei parquet storici: fa fetch live con cache se manca
    un file (vedi _load_candles) — il portfolio report non deve collassare a
    None nel cloud dove data/candles e' vuoto."""
    frames = {}
    for sym in symbols:
        c = _load_candles(sym)
        if c is None:
            return None
        c = c[["ts", "close"]].rename(columns={"close": sym})
        frames[sym] = c.set_index("ts")[sym]
    if not frames:
        return None
    panel = pd.DataFrame(frames).dropna().sort_index()
    panel = panel.tail(months * 30 * 24)
    return panel if len(panel) >= 30 * 24 else None


def _signal_panel(close: pd.DataFrame, pf: dict) -> pd.DataFrame:
    """Pannello del segnale di ranking (un valore per simbolo per ts): xsmom =
    ritorno trailing, highvol = volatilita' trailing, combo = z-score pesato.
    Anti-lookahead: ogni segnale usa solo dati <= t."""
    factors = pf.get("factors")
    if factors:
        weights = pf.get("weights", [0.5] * len(factors))
        parts = []
        for f, w in zip(factors, weights):
            if f == "highvol":
                vl = int(pf.get("vol_lookback_h", 72))
                parts.append(close.pct_change().rolling(vl).std() * w)
            else:  # xsmom
                lb = int(pf.get("lookback_h", 168))
                parts.append(close.pct_change(lb) * w)
        sig = sum(parts)
        mu = sig.mean(axis=1)
        sd = sig.std(axis=1).replace(0.0, np.nan)
        return sig.sub(mu, axis=0).div(sd, axis=0)   # z-score cross-section
    factor = pf.get("factor", "xsmom")
    if factor == "highvol":
        vl = int(pf.get("vol_lookback_h", 72))
        return close.pct_change().rolling(vl).std()
    lbs = pf.get("lookbacks_h")   # multi-horizon: media dei ritorni trailing
    if lbs:
        return sum(close.pct_change(int(lb)) for lb in lbs) / len(lbs)
    lb = int(pf.get("lookback_h", 168))
    return close.pct_change(lb)


def _portfolio_weight_fn(signal_panel: pd.DataFrame, pf: dict):
    """weight_fn per PortfolioBacktest.run: recupera il ts dalla riga (`.name`) e
    ranka il segnale di portafoglio corretto. xs_momentum_weights converte rank -> pesi."""
    kw = dict(long_q=float(pf.get("long_q", 0.66)), short_q=float(pf.get("short_q", 0.33)),
              gross=float(pf.get("gross", 1.0)), dollar_neutral=bool(pf.get("dollar_neutral", True)))

    def wf(trailing_row):
        sig = signal_panel.loc[trailing_row.name] if trailing_row.name in signal_panel.index else trailing_row
        return xs_momentum_weights(sig, **kw)
    return wf


def _apply_vol_target(port_ret: pd.Series, vt: dict) -> tuple[pd.Series, float]:
    """Overlay vol-target (Moreira-Muir): scala i rendimenti per m = target/realized
    (clip floor..cap). Approssimazione onesta del live (che scala il gross a ogni
    ribilanciamento); restituisce rets scalati + m medio."""
    if not vt or not vt.get("enabled"):
        return port_ret, 1.0
    target = float(vt.get("target_vol_ann", 0.2))
    win = int(vt.get("vol_window_h", 720))
    floor = float(vt.get("gross_floor", 0.3))
    cap = float(vt.get("gross_cap", 1.5))
    realized = port_ret.rolling(win).std() * np.sqrt(HOURS_PER_YEAR)
    m = (target / realized).clip(floor, cap).fillna(1.0)
    return port_ret * m, float(m.mean())


def backtest_portfolio_strategy(spec_path: Path, months: int) -> dict | None:
    spec = load(spec_path)
    symbols = [s.strip() for s in str(spec.get("paper_symbols", "")).split(",") if s.strip()]
    if not symbols:
        return None
    panel = _close_panel(symbols, months)
    if panel is None:
        return None
    pf = spec.get("portfolio", {}) or {}
    lookback_h = int(pf.get("lookback_h", pf.get("vol_lookback_h", 168)))
    rebalance_h = int(pf.get("rebalance_h", 168))
    bt = PortfolioBacktest(panel)
    signal_panel = _signal_panel(bt.close, pf)
    warmup = max(lookback_h, int(pf.get("vol_lookback_h", 0)), max(pf.get("lookbacks_h", [0]) or [0]))
    equity, port_ret, _ = bt.run(_portfolio_weight_fn(signal_panel, pf),
                                 lookback_h=max(lookback_h, warmup), rebalance_h=rebalance_h)
    if equity.empty:
        return None
    vt = pf.get("vol_target")
    port_ret, vt_m = _apply_vol_target(port_ret, vt)
    equity = (1.0 + port_ret).cumprod()
    eq_df = pd.DataFrame({"ts": equity.index, "equity": equity.values})
    basket = pd.DataFrame({"ts": panel.index,
                           "close": (panel / panel.iloc[0]).mean(axis=1).values})
    a = _aggregate_portfolio(eq_df, basket)
    return {
        "id": spec["id"],
        "status": spec.get("status", "?"),
        "engine": "portfolio",
        "thesis": (spec.get("thesis", "") or "")[:280],
        "is_benchmark": spec["id"] == BENCHMARK,
        "window": f"{panel.index.min():%Y-%m-%d} \u2192 {panel.index.max():%Y-%m-%d}",
        "basket_size": len(symbols),
        "vol_target": (f"on (m medio {vt_m:.2f})" if vt and vt.get("enabled") else "off"),
        "aggregate": a,
        "per_symbol": [],   # n/a: edge cross-section, non per-asset
    }


def _aggregate_portfolio(equity_df: pd.DataFrame, basket: pd.DataFrame) -> dict:
    m = compute(equity_df, [])
    ev = evaluate(equity_df, basket)
    return {
        "mean_sharpe": round(m["sharpe"], 2),
        "mean_return": round(m["total_return"], 4),
        "worst_drawdown": round(m["max_drawdown"], 4),
        "positive_symbols": "market-neutral",   # n/a per portafogli dollar-neutral
        "consistency": ev["consistency"],
    }


def _active_specs() -> list[Path]:
    """Tutte le challenger/attive + il benchmark, ordinate (benchmark per primo)."""
    paths = sorted((ROOT / "strategies").glob("*.yaml")) + sorted((ROOT / "strategies" / "generated").glob("*.yaml"))
    out = []
    for p in paths:
        try:
            s = load(p)
        except Exception:
            continue
        # i desk LLM non sono backtestabili per design (LLM = giudice, non oracolo):
        # le loro decisioni simulate sarebbero contaminazione. Li si valuta solo paper.
        if s.get("engine") == "desk":
            continue
        if s.get("id") == BENCHMARK:
            out.append(p)
        elif s.get("status") in ("challenger", "champion", "active", "paper"):
            out.append(p)
    # benchmark davanti, poi le altre per id
    out.sort(key=lambda p: (load(p).get("id") != BENCHMARK, str(p)))
    return out


def main() -> int:
    months = MONTHS_DEFAULT
    if "--months" in sys.argv:
        months = int(sys.argv[sys.argv.index("--months") + 1])

    results = []
    for spec_path in _active_specs():
        spec = load(spec_path)
        r = (backtest_portfolio_strategy(spec_path, months)
             if spec.get("engine") == "portfolio"
             else backtest_strategy(spec_path, months))
        if r:
            tag = "[portfolio]" if r.get("engine") == "portfolio" else ""
            print(f"  {r['id']:<32} mean Sharpe {r['aggregate']['mean_sharpe']:5.2f} | "
                  f"ret {r['aggregate']['mean_return']:+6.2%} | "
                  f"{r['aggregate']['positive_symbols']} {tag}")
            results.append(r)

    payload = {
        "months": months,
        "impact_k": IMPACT_K,
        "funding_mode": "storico (dove disponibile)",
        "generated_at": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M UTC"),
        "strategies": results,
    }
    atomic_write_text(OUT, json.dumps(payload, ensure_ascii=False, indent=1))
    print(f"\nbacktest report ({len(results)} strategie) → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
