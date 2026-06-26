"""Zoo di fattori PORTFOLIO ortogonali a xsmom (dove cercare il 2° edge).

Tutto testato come book dollar-neutral (dove l'edge abita, per la lezione xsmom).
Criterio promozione: Sharpe > 1 E DSR >= 0.5 (sotto = non costruibile).

Fattori testati (tutti rank cross-section, long-top / short-bottom):
  [1] xsmom             momentum relativo 168h (baseline, l'edge forte)
  [2] TSMOM-NEUTRAL     long asset con mom>0, short mom<0 (Jegadeesh-Titman classico)
  [3] REVERSAL-24       short-term reversal 24h (contrarian, opposto momentum)
  [4] REVERSAL-168      reversal 1 settimana
  [5] LOW-VOL           long bassa-vol / short alta-vol (low-vol anomaly)
  [6] FLOW             long heavy taker-buy / short heavy-sell (cross-section)
  [7] OI-BUILDUP        long OI crescente / short OI calante
  [8] TOP-TRADER        long dove smart money e' long / short dove short
  [9] COMBO mom+reversal media xsmom e reversal (test diversificazione)

Uso: uv run scripts/backtest_factor_zoo.py [--months 12]
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backtest.portfolio import PortfolioBacktest, equal_weight_bh
from backtest.stats import deflated_sharpe

CRYPTO = "BTC,ETH,SOL,XRP,SUI,NEAR,WLD,ZEC,CRV"
PPY = 24 * 365


def grid_panel(symbols, months, col="close", kind="candles"):
    """Panel su griglia oraria BTC (24/7). ffill per session-based."""
    btc = pd.read_parquet(ROOT / "data/candles/BTC.parquet").tail(months * 30 * 24)
    grid = pd.to_datetime(btc.ts, utc=True)
    cols = {}
    for s in symbols:
        p = ROOT / f"data/{kind}/{s}.parquet"
        if not p.exists():
            continue
        c = pd.read_parquet(p).copy()
        c["ts"] = pd.to_datetime(c.ts, utc=True)
        if col in c.columns:
            cols[s] = c.drop_duplicates("ts").set_index("ts")[col].reindex(grid, method="ffill")
    return pd.DataFrame(cols).sort_index()


def terzile_weights(signal_row, gross=1.0):
    """Long top-terzile, short bottom-terzile, dollar-neutral equal-weight."""
    s = signal_row.dropna()
    w = pd.Series(0.0, index=signal_row.index)
    if len(s) < 6:
        return w
    n = max(2, len(s) // 3)
    longs = s.nlargest(n).index
    shorts = s.nsmallest(n).index
    w[longs] = 0.5 / len(longs)
    w[shorts] = -0.5 / len(shorts)
    g = w.abs().sum()
    return w / g * gross if g > 0 else w


def sign_weights(signal_row, gross=1.0):
    """Long asset con segnale > 0, short < 0 (TSMOM-neutral construction).
    Equal-weight per gamba (non per magnitudo)."""
    s = signal_row.dropna()
    w = pd.Series(0.0, index=signal_row.index)
    longs = s[s > 0].index
    shorts = s[s < 0].index
    if len(longs):
        w[longs] = 0.5 / len(longs)
    if len(shorts):
        w[shorts] = -0.5 / len(shorts)
    g = w.abs().sum()
    return w / g * gross if g > 0 else w


def run_factor(bt, signal_panel, weight_fn, rebalance_h, gross=1.0):
    """Applica weight_fn al signal_panel, ribilancia ogni rebalance_h, anti-lookahead."""
    idx = bt.close.index
    n = len(idx)
    W = pd.DataFrame(0.0, index=idx, columns=bt.close.columns)
    turnover = pd.Series(0.0, index=idx)
    last_w = pd.Series(0.0, index=bt.close.columns)
    # burn-in: il primo rebalance dopo che il segnale e' disponibile
    first = signal_panel.dropna(how="all").index[0] if not signal_panel.dropna(how="all").empty else None
    if first is None:
        return pd.Series(1.0, index=idx), pd.Series(0.0, index=idx), 0
    start = signal_panel.index.get_loc(first) + 1
    for i in range(start, n, rebalance_h):
        w = weight_fn(signal_panel.iloc[i - 1]).reindex(bt.close.columns).fillna(0.0)
        turnover.iloc[i] = (w - last_w).abs().sum()
        last_w = w
        W.iloc[i:min(i + rebalance_h, n)] = w.to_numpy()
    port_ret = (W.shift(1) * bt.ret).sum(axis=1) - turnover * bt.cost
    eq = (1.0 + port_ret).cumprod()
    return eq, port_ret, int((turnover > 0).sum())


def stats(eq, ret):
    sharpe = ret.mean() / ret.std() * np.sqrt(PPY) if ret.std() else 0.0
    dd = float((eq / eq.cummax() - 1).min())
    return float(eq.iloc[-1] - 1), float(sharpe), dd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=CRYPTO)
    ap.add_argument("--months", type=int, default=12)
    a = ap.parse_args()
    syms = a.symbols.split(",")

    px = grid_panel(syms, a.months)
    bt = PortfolioBacktest(px)
    ret_hourly = px.pct_change()

    # pannelli segnale
    mom168 = px.pct_change(168)                          # [1] baseline
    mom_signed = px.pct_change(168)                      # [2] segno per TSMOM-neutral
    rev24 = -px.pct_change(24)                           # [3] reversal 24h (inverso del mom corto)
    rev168 = -px.pct_change(168)                         # [4] reversal 1 settimana
    vol = -ret_hourly.rolling(168, min_periods=84).std() # [5] low-vol: long BASSA vol (-vol)
    flow = grid_panel(syms, a.months, "taker_buy", "flow")   # taker_buy grezzo
    flow_vol = grid_panel(syms, a.months, "volume", "flow")
    flow_ratio = (flow / flow_vol.replace(0, np.nan) - 0.5).fillna(0)  # [6] buy ratio
    oi = grid_panel(syms, a.months, "oi", "coinalyze")
    oi_chg = oi.pct_change(3)                            # [7] OI buildup 3g
    topr = grid_panel(syms, a.months, "toptrader_pos_ratio", "metrics")  # [8] smart money

    factors = [
        ("[1] xsmom (baseline forte)",        mom168,    terzile_weights, 168),
        ("[2] TSMOM-NEUTRAL (J-T classic)",   mom_signed, sign_weights,   168),
        ("[3] REVERSAL-24 (contrarian 1g)",   rev24,     terzile_weights, 24),
        ("[4] REVERSAL-168 (contrarian 1w)",  rev168,    terzile_weights, 168),
        ("[5] LOW-VOL anomaly",               vol,       terzile_weights, 168),
        ("[6] FLOW taker-buy ratio",          flow_ratio, terzile_weights, 24),
        ("[7] OI-BUILDUP 3g",                 oi_chg,    terzile_weights, 72),
        ("[8] TOP-TRADER smart money",        topr,      terzile_weights, 168),
    ]
    results = []
    for name, sig, fn, reb in factors:
        sig = sig.reindex(columns=px.columns)            # allinea colonne
        eq, ret, nreb = run_factor(bt, sig, fn, reb)
        results.append((name, eq, ret, nreb))

    trial_srs = [r[2].mean() / r[2].std() if r[2].std() else 0 for r in results]
    beq = equal_weight_bh(px)
    br, bs, bdd = stats(beq, ret_hourly.mean(axis=1))

    print(f"basket {list(px.columns)}, {len(px)} ore ({px.index.min():%Y-%m-%d} → {px.index.max():%Y-%m-%d})")
    print("factor ZOO — 12m, fee+slippage, dollar-neutral. Promozione: Sharpe>1 & DSR≥0.5\n")
    print(f"{'fattore':<38} {'ret':>8} {'sharpe':>7} {'maxDD':>8} {'DSR':>5} {'rebal':>6} {'verdetto'}")
    print(f"{'equal-weight B&H (benchmark)':<38} {br:>+8.2%} {bs:>7.2f} {bdd:>+8.2%}")
    print("-" * 90)
    built = []
    for name, eq, ret, nreb in results:
        r, sh, dd = stats(eq, ret)
        d = deflated_sharpe(ret, len(results), trial_srs)
        ok = sh > 1.0 and d["dsr"] >= 0.5
        verdict = "✓ PROMUOVI" if ok else ("debole" if sh > 0.3 else "falsificato")
        if ok:
            built.append(name)
        print(f"{name:<38} {r:>+8.2%} {sh:>7.2f} {dd:>+8.2%} {d['dsr']:>5.2f} {nreb:>6} {verdict}")

    # [9] combo mom + miglior reversal (diversificazione)
    if built:
        print("-" * 90)
        W_xs, _ = _weights_matrix(bt, mom168, terzile_weights, 168)
        for name, sig in [("reversal168", rev168), ("reversal24", rev24)]:
            W_rev, _ = _weights_matrix(bt, sig, terzile_weights, 168 if "168" in name else 24)
            def _norm(W):
                g = W.abs().sum(axis=1).replace(0, np.nan)
                return W.div(g, axis=0).fillna(0)
            W_combo = _norm(W_xs) * 0.5 + _norm(W_rev) * 0.5
            to = W_combo.diff().abs().sum(axis=1)
            pr = (W_combo.shift(1) * bt.ret).sum(axis=1) - to * bt.cost
            eq = (1 + pr).cumprod()
            r, sh, dd = stats(eq, pr)
            d = deflated_sharpe(pr, len(results), trial_srs)
            label = f"[9] COMBO xsmom+{name} 50/50"
            print(f"{label:<38} {r:>+8.2%} {sh:>7.2f} {dd:>+8.2%} {d['dsr']:>5.2f}")

    print(f"\nFattori da costruire: {built or 'NESSUNO'}")


def _weights_matrix(bt, signal_panel, weight_fn, rebalance_h):
    idx = bt.close.index
    n = len(idx)
    W = pd.DataFrame(0.0, index=idx, columns=bt.close.columns)
    turnover = pd.Series(0.0, index=idx)
    last_w = pd.Series(0.0, index=bt.close.columns)
    signal_panel = signal_panel.reindex(columns=bt.close.columns)
    first = signal_panel.dropna(how="all").index[0] if not signal_panel.dropna(how="all").empty else None
    if first is None:
        return W, turnover
    start = signal_panel.index.get_loc(first) + 1
    for i in range(start, n, rebalance_h):
        w = weight_fn(signal_panel.iloc[i - 1]).reindex(bt.close.columns).fillna(0.0)
        turnover.iloc[i] = (w - last_w).abs().sum()
        last_w = w
        W.iloc[i:min(i + rebalance_h, n)] = w.to_numpy()
    return W, turnover


if __name__ == "__main__":
    main()
