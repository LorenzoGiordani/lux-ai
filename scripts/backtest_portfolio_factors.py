"""Backtest di EDGE PORTFOLIO ortogonali a xsmom (filone dove c'e' l'alpha reale).

Le per-simbolo sono tutte sotto Sharpe 0.8; xsmom-port fa +79.8% Sharpe 2.11.
TesL l'ipotesi: se xsmom (IC per-simbolo debole +0.028) esplode a portafoglio,
altri edge deboli per-simbolo potrebbero fare lo stesso. Tutto dollar-neutral
o vol-target, niente market direction (beta comune netto).

Edge testati (tutti a 12m, fee+slippage, walk-forward):
  [A] FUNDING CARRY book    long low-funding / short high-funding (IC -0.024 per-sym)
  [B] TSMOM vol-target book time-series momentum long-only, inverse-vol weighted
  [C] MULTI-FACTOR          xsmom + carry combo (edge ortogonali nello stesso book)
  [D] VOL-WEIGHTED xsmom    xsmom con inverse-vol sizing invece di equal-weight

Uso: uv run scripts/backtest_portfolio_factors.py [--months 12]
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backtest.portfolio import PortfolioBacktest, equal_weight_bh, xs_momentum_weights
from backtest.stats import deflated_sharpe

CRYPTO = "BTC,ETH,SOL,XRP,SUI,NEAR,WLD,ZEC,CRV"
PPY = 24 * 365


def panel(symbols, months, kind="close"):
    cols = {}
    for s in symbols:
        p = ROOT / f"data/candles/{s}.parquet"
        if p.exists():
            c = pd.read_parquet(p).tail(months * 30 * 24)
            cols[s] = c.set_index("ts")[kind]
    df = pd.DataFrame(cols).sort_index()
    return df[~df.index.duplicated()]


def funding_panel(symbols, index):
    """Funding rate 8h ffillato sulla griglia oraria."""
    cols = {}
    for s in symbols:
        p = ROOT / f"data/funding/{s}.parquet"
        if p.exists():
            f = pd.read_parquet(p).set_index("ts")["rate"]
            cols[s] = f[~f.index.duplicated()].reindex(index, method="ffill")
    return pd.DataFrame(cols)


def stats(equity, ret):
    sharpe = ret.mean() / ret.std() * np.sqrt(PPY) if ret.std() else 0.0
    dd = float((equity / equity.cummax() - 1).min())
    return float(equity.iloc[-1] - 1), float(sharpe), dd


def carry_weights(trailing_funding, gross=1.0):
    """Long i 3 asset con funding PIU' BASSO, short i 3 con funding PIU' ALTO.
    Dollar-neutral, equal-weight per gamba. (carry: short chi paga troppo)."""
    s = trailing_funding.dropna()
    w = pd.Series(0.0, index=trailing_funding.index)
    if len(s) < 6:
        return w
    n = max(2, len(s) // 3)
    longs = s.nsmallest(n).index      # funding basso = non affollato long → long
    shorts = s.nlargest(n).index      # funding alto = crowding long → short
    w[longs] = 0.5 / len(longs)
    w[shorts] = -0.5 / len(shorts)
    gabs = w.abs().sum()
    return w / gabs * gross if gabs > 0 else w


def tsmom_voltarget_weights(trailing_ret, gross=1.0):
    """Time-series momentum long-only, inverse-vol weighted (risk parity).
    Long ogni asset con ritorno trailing > 0, peso ∝ 1/vol. Non market-neutral:
    e' directional beta al trend, ma vol-targeted e diversificato."""
    s = trailing_ret.dropna()
    w = pd.Series(0.0, index=trailing_ret.index)
    if len(s) < 3:
        return w
    longs = s[s > 0]
    if len(longs) == 0:
        return w
    # inverse-vol proxy: 1/|ret| (piu' volatile = ritorno assoluto piu' grande)
    iv = 1.0 / longs.abs().replace(0, np.nan)
    w[longs.index] = (iv / iv.sum() * gross).fillna(0)
    return w


def volweighted_xs_weights(trailing_ret, gross=1.0, dollar_neutral=True):
    """xsmom con inverse-vol sizing invece di equal-weight nelle gambe."""
    s = trailing_ret.dropna()
    w = pd.Series(0.0, index=trailing_ret.index)
    if len(s) < 6:
        return w
    hi, lo = s.quantile(0.66), s.quantile(0.33)
    longs, shorts = s[s >= hi], s[s <= lo]
    if len(longs):
        ivl = 1.0 / longs.abs().replace(0, np.nan)
        w[longs.index] = (ivl / ivl.sum() * 0.5).fillna(0)
    if len(shorts):
        ivs = 1.0 / shorts.abs().replace(0, np.nan)
        w[shorts.index] = -(ivs / ivs.sum() * 0.5).fillna(0)
    gabs = w.abs().sum()
    return w / gabs * gross if gabs > 0 else w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=CRYPTO)
    ap.add_argument("--months", type=int, default=12)
    a = ap.parse_args()
    syms = a.symbols.split(",")

    px = panel(syms, a.months)
    bt = PortfolioBacktest(px)
    fund = funding_panel(syms, px.index)
    # trailing funding (medio sui 7g precedenti per stabilizzare il ranking)
    fund_trail = fund.rolling(168, min_periods=48).mean()

    print(f"basket {list(px.columns)}, {len(px)} ore ({px.index.min():%Y-%m-%d} → {px.index.max():%Y-%m-%d})")
    print("edge PORTFOLIO ortogonali — 12m, fee+slippage, dollar-neutral/vol-target\n")

    beq = equal_weight_bh(px)
    br, bs, bdd = stats(beq, px.pct_change().fillna(0.0).mean(axis=1))

    configs = [
        ("xsmom dollar-neutral (baseline forte)", 168, 168, xs_momentum_weights),
        ("[A] FUNDING CARRY book reb168",        168, 168, carry_weights),
        ("[A] FUNDING CARRY book reb24",         168, 24,  carry_weights),
        ("[B] TSMOM vol-target long reb168",     168, 168, tsmom_voltarget_weights),
        ("[B] TSMOM vol-target long reb24",      168, 24,  tsmom_voltarget_weights),
        ("[D] xsmom VOL-WEIGHTED reb168",        168, 168, volweighted_xs_weights),
    ]
    # NB: per [A]/[B] il "trailing" e' il funding/ret, non il prezzo — si fa override
    # della fonte dentro il run custom qui sotto (PortfolioBacktest.run usa close.pct_change).
    # Implementazione onesta: ridefinisco run per i fattori non-prezzo.

    print(f"{'config':<46} {'ret':>8} {'sharpe':>7} {'maxDD':>8} {'DSR':>5} {'rebal':>6}")
    print(f"{'equal-weight B&H (benchmark)':<46} {br:>+8.2%} {bs:>7.2f} {bdd:>+8.2%} {'—':>5} {'—':>6}")
    print("-" * 88)

    for name, lb, reb, fn in configs:
        if fn is carry_weights:
            # custom run: usa fund_trail invece di close.pct_change
            W, turnover = _run_custom(bt, fund_trail, fn, lb, reb)
        elif fn is tsmom_voltarget_weights:
            W, turnover = _run_custom(bt, px.pct_change(lb), fn, lb, reb)
        else:
            eq, ret, meta = bt.run(fn, lookback_h=lb, rebalance_h=reb)
            r, sh, dd = stats(eq, ret)
            d = deflated_sharpe(ret, len(configs), None)
            print(f"{name:<46} {r:>+8.2%} {sh:>7.2f} {dd:>+8.2%} {d['dsr']:>5.2f} {meta['rebalances']:>6}")
            continue
        # custom path
        port_ret = (W.shift(1) * bt.ret).sum(axis=1) - turnover * bt.cost
        eq = (1.0 + port_ret).cumprod()
        r, sh, dd = stats(eq, port_ret)
        d = deflated_sharpe(port_ret, len(configs), None)
        reb_n = int((turnover > 0).sum())
        print(f"{name:<46} {r:>+8.2%} {sh:>7.2f} {dd:>+8.2%} {d['dsr']:>5.2f} {reb_n:>6}")

    # [C] MULTI-FACTOR: combo xsmom + carry (media dei pesi normalizzati)
    print("-" * 88)
    W_xs, _ = _run_custom(bt, px.pct_change(168), xs_momentum_weights, 168, 168)
    # combo xsmom + TSMOM-long (alpha neutro + beta direzionale controllato)
    W_tsmom, _ = _run_custom(bt, px.pct_change(168), tsmom_voltarget_weights, 168, 168)
    # normalizza per gross unitario, poi media 50/50
    def _norm(W):
        g = W.abs().sum(axis=1).replace(0, np.nan)
        return W.div(g, axis=0).fillna(0)
    for label, W_combo, w_tsmom_gross in [
        ("[C1] xsmom + TSMOM-long (alpha+beta) g1.0", _norm(W_xs)*0.5 + _norm(W_tsmom)*0.5, 1.0),
        ("[C2] xsmom + TSMOM-long  (tilt 70/30)",    _norm(W_xs)*0.7 + _norm(W_tsmom)*0.3, 1.0),
    ]:
        port_ret = (W_combo.shift(1) * bt.ret).sum(axis=1)
        turnover_c = W_combo.diff().abs().sum(axis=1)
        port_ret = port_ret - turnover_c * bt.cost
        eq = (1.0 + port_ret).cumprod()
        r, sh, dd = stats(eq, port_ret)
        d = deflated_sharpe(port_ret, len(configs), None)
        print(f"{label:<46} {r:>+8.2%} {sh:>7.2f} {dd:>+8.2%} {d['dsr']:>5.2f} {int((turnover_c>0).sum()):>6}")

    # [E] MULTI-HORIZON xsmom (stesso edge, orizzonti diversi, media dei pesi)
    W_lb = []
    for lb in [96, 168, 336]:
        Wx, _ = _run_custom(bt, px.pct_change(lb), xs_momentum_weights, lb, 168)
        W_lb.append(_norm(Wx))
    W_mh = sum(W_lb) / len(W_lb)
    turnover_mh = W_mh.diff().abs().sum(axis=1)
    port_ret = (W_mh.shift(1) * bt.ret).sum(axis=1) - turnover_mh * bt.cost
    eq = (1.0 + port_ret).cumprod()
    r, sh, dd = stats(eq, port_ret)
    d = deflated_sharpe(port_ret, len(configs), None)
    print(f"{'[E] MULTI-HORIZON xsmom (lb96+168+336)':<46} {r:>+8.2%} {sh:>7.2f} {dd:>+8.2%} {d['dsr']:>5.2f} {int((turnover_mh>0).sum()):>6}")


def _run_custom(bt, trailing_df, weight_fn, lookback_h, rebalance_h):
    """Run con trailing custom (funding o ret) invece di close.pct_change."""
    idx = bt.close.index
    n = len(idx)
    W = pd.DataFrame(0.0, index=idx, columns=bt.close.columns)
    turnover = pd.Series(0.0, index=idx)
    last_w = pd.Series(0.0, index=bt.close.columns)
    for i in range(lookback_h, n, rebalance_h):
        w = weight_fn(trailing_df.iloc[i]).reindex(bt.close.columns).fillna(0.0)
        turnover.iloc[i] = (w - last_w).abs().sum()
        last_w = w
        W.iloc[i:min(i + rebalance_h, n)] = w.to_numpy()
    return W, turnover


if __name__ == "__main__":
    main()
