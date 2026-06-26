"""Studio d'edge PRE-strategia per il segnale Nadaraya-Watson (firma DaviddTech).

Regola del progetto #4: nessun segnale entra nel registry senza edge documentato.
Il NW restituisce una lettura di ESTENSIONE (+1/-1 vs la baseline kernel). Ha due
letture direzionali opposte, ed e' cruciale misurare quale (se mai) ha alpha nel
regime corrente prima di costruire strategie:

  FADE (mean-reversion)    segnale -1  ->  ritorno futuro  > 0   (IC atteso +)
  CONTINUATION (breakout)  segnale +1  ->  ritorno futuro  > 0   (IC atteso +)

Output: IC (correlazione cross-section su rank, come research_edges.py) del segnale
NW vs ritorno futuro, calcolato PER-ASSET e aggregato, per 3 set di parametri e 2
orizzonti. Niente trading, solo misura. Uso:
  uv run scripts/research_nw.py [--symbols CSV] [--months 12]
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(ROOT))
from backtest.signals import nadaraya_watson

CRYPTO = "BTC,ETH,SOL,XRP,SUI,NEAR,WLD,ZEC,CRV"
PARAM_GRID = [
    dict(lookback=48, bandwidth=8.0, mult=1.5),    # corto: reversion veloce
    dict(lookback=72, bandwidth=12.0, mult=2.0),   # medio: envelope standard
    dict(lookback=120, bandwidth=20.0, mult=2.5),  # lungo: trend filter
]


def load_close(symbol, months):
    p = ROOT / f"data/candles/{symbol}.parquet"
    if not p.exists():
        return None
    c = pd.read_parquet(p).tail(months * 30 * 24).reset_index(drop=True)
    return c


def fwd_returns(candles, horizon):
    return candles.close.pct_change(horizon).shift(-horizon)


def per_asset_ic(sig_arr, fwd_arr):
    """IC = corr(rank sig, rank fwd) sui punti con entrambi non-null (rank Pearson)."""
    mask = np.isfinite(sig_arr) & np.isfinite(fwd_arr) & (sig_arr != 0)
    if mask.sum() < 30:
        return np.nan, 0
    s = sig_arr[mask]
    f = fwd_arr[mask]
    rs = pd.Series(s).rank().to_numpy()
    rf = pd.Series(f).rank().to_numpy()
    rs = rs - rs.mean()
    rf = rf - rf.mean()
    den = np.sqrt((rs ** 2).sum() * (rf ** 2).sum())
    return float(rs @ rf / den) if den > 0 else np.nan, int(mask.sum())


def aggregate_ic(sig_panel, fwd_panel):
    """IC cross-section per timestamp (rank across assets), poi media + t-stat."""
    common = [c for c in sig_panel.columns if c in fwd_panel.columns]
    if len(common) < 4:
        return np.nan, 0, 0.0
    s = sig_panel[common]
    f = fwd_panel[common]
    # solo righe con >=4 asset attivi sul segnale
    valid = (s != 0).sum(axis=1) >= 4
    s, f = s[valid], f[valid]
    rs = s.rank(axis=1).sub(s.rank(axis=1).mean(axis=1), axis=0)
    rf = f.rank(axis=1).sub(f.rank(axis=1).mean(axis=1), axis=0)
    num = (rs * rf).sum(axis=1)
    den = np.sqrt((rs ** 2).sum(axis=1) * (rf ** 2).sum(axis=1)).replace(0, np.nan)
    ic = (num / den).dropna()
    if len(ic) < 5 or ic.std() == 0:
        return np.nan, len(ic), 0.0
    tstat = ic.mean() / ic.std() * np.sqrt(len(ic))
    return float(ic.mean()), len(ic), float(tstat)


def run(symbol, months, params, horizons):
    c = load_close(symbol, months)
    if c is None:
        return None
    out = {"symbol": symbol}
    for p in params:
        sig = nadaraya_watson({"candles": c}, **p)
        out[p["lookback"]] = sig
    for hz in horizons:
        out[f"fwd{hz}"] = fwd_returns(c, hz)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=CRYPTO)
    ap.add_argument("--months", type=int, default=12)
    a = ap.parse_args()
    syms = a.symbols.split(",")
    horizons = [12, 24, 48, 168]            # 12h, 1g, 2g, 1 settimana

    rows = [run(s, a.months, PARAM_GRID, horizons) for s in syms]
    rows = [r for r in rows if r is not None]
    print(f"Nadaraya-Watson edge study — basket {len(rows)} asset, {a.months}m")
    print(f"param grid: {PARAM_GRID}\n")

    # --- pannello cross-section per l'IC aggregato (lettura fade e continuation) ---
    print(f"{'params':<22} {'hz':>4} {'IC fade':>9} {'t':>6}  {'IC cont':>9} {'t':>6}  {'xsec IC':>8} {'t':>6}")
    print("-" * 80)
    for p in PARAM_GRID:
        col = p["lookback"]
        for hz in horizons:
            fcol = f"fwd{hz}"
            # per-asset IC: fade = -sig (estensione rialzista -> ritorno futuro NEGATIVO atteso)
            ics_f, ics_c = [], []
            for r in rows:
                ic, _ = per_asset_ic(-r[col].to_numpy(), r[fcol].to_numpy())
                if np.isfinite(ic):
                    ics_f.append(ic)
                ic, _ = per_asset_ic(r[col].to_numpy(), r[fcol].to_numpy())
                if np.isfinite(ic):
                    ics_c.append(ic)
            icf = float(np.mean(ics_f)) if ics_f else np.nan
            icc = float(np.mean(ics_c)) if ics_c else np.nan
            tf = float(np.mean(ics_f) / np.std(ics_f) * np.sqrt(len(ics_f))) if len(ics_f) > 1 else 0
            tc = float(np.mean(ics_c) / np.std(ics_c) * np.sqrt(len(ics_c))) if len(ics_c) > 1 else 0
            # cross-section IC (market-neutral long-short sul rank)
            sig_panel = pd.DataFrame({r["symbol"]: r[col] for r in rows})
            fwd_panel = pd.DataFrame({r["symbol"]: r[fcol] for r in rows})
            xic, _, xt = aggregate_ic(sig_panel, fwd_panel)
            print(f"lb={col} bw={p['bandwidth']:<2} m={p['mult']:<3} {hz:>4} "
                  f"{icf:>+9.4f} {tf:>+6.1f}  {icc:>+9.4f} {tc:>+6.1f}  "
                  f"{xic:>+8.4f} {xt:>+6.1f}")

    print("\nLegenda: IC fade = ritorno futuro dopo ESTENSIONE alta (segno -). "
          "IC cont = dopo estensione con STESSO segno.")
    print("t > +2 = edge significativo (validato). Il verdetto dice quale lettura costruire.")


if __name__ == "__main__":
    main()
