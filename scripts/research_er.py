"""Valida efficiency_ratio come GATE di regime (sessione 26/06, idea [C]).

Il principio DaviddTech (regime filter) e' valido; lux-regime-3leg era fallito
per implementazione (hmm troppo stretto + cache mancante su SOL). ER non ha cache
→ disponibile ovunque. Prima di costruire, misuro se 'trending' (ER alto) predice
un fwd return con MAGGIORE persistenza direzionale ( Sharpe del ritorno firmato)
rispetto al chop. Se il trend e' pulito quando ER alto, il gate ha senso.

Metrica: per ogni asset, fwd return sign(tsмом) a orizzonte hz, mediato nei 2 regimi
ER. Un gate utile: |fwd firmato| trending > |fwd firmato| chop (il momentum 'funziona'
nel trending). Inoltre la frazione di tempo 'trending' (per tarare la soglia e non
soffocare: voglio ~40-50% trending, non 5%).

Uso: uv run scripts/research_er.py [--symbols CSV] [--months 12]
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(ROOT))
from backtest.signals import efficiency_ratio, tsmom

CRYPTO = "BTC,ETH,SOL,XRP,SUI,NEAR,WLD,ZEC,CRV"


def load(symbol, months):
    p = ROOT / f"data/candles/{symbol}.parquet"
    if not p.exists():
        return None
    return pd.read_parquet(p).tail(months * 30 * 24).reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=CRYPTO)
    ap.add_argument("--months", type=int, default=12)
    a = ap.parse_args()
    syms = a.symbols.split(",")

    print("Efficiency Ratio (Kaufman) come regime gate")
    print("Metrica: fwd return firmato (sign tsmom) medio nei 2 regimi ER, + frazione tempo trending\n")
    print(f"{'symbol':<6} {'trend_pct':>3} | {'fwd@48 trend':>13} {'chop':>10} {'Δ':>8} | {'fwd@168 trend':>14} {'chop':>10} | {'%time trend':>11}")
    print("-" * 95)

    agg_t, agg_c, agg_t168, agg_c168, agg_frac = [], [], [], [], []
    for symbol in syms:
        c = load(symbol, a.months)
        if c is None:
            continue
        t = tsmom({"candles": c}, short_h=168, long_h=720)
        for tp in [50, 60]:
            er = efficiency_ratio({"candles": c}, lookback=168, trend_pct=tp)
            trending = er == 1
            frac = float(trending.mean())
            results = []
            for hz in [48, 168]:
                fw = (c.close.pct_change(hz).shift(-hz) * t).to_numpy()  # firmato col trend
                tr = np.nanmean(fw[trending])
                ch = np.nanmean(fw[~trending])
                results.extend([tr, ch])
            if tp == 60:
                agg_t.append(results[0]); agg_c.append(results[1])
                agg_t168.append(results[2]); agg_c168.append(results[3]); agg_frac.append(frac)
            print(f"{symbol:<6} {tp:>3} | {results[0]:>+13.4f} {results[1]:>+10.4f} {results[0]-results[1]:>+8.4f} | "
                  f"{results[2]:>+14.4f} {results[3]:>+10.4f} | {frac:>10.0%}")
    print("-" * 95)
    if agg_t:
        dt48 = np.nanmean(agg_t) - np.nanmean(agg_c)
        dt168 = np.nanmean(agg_t168) - np.nanmean(agg_c168)
        print(f"{'MEDIA':<6}     | {np.nanmean(agg_t):>+13.4f} {np.nanmean(agg_c):>+10.4f} {dt48:>+8.4f} | "
              f"{np.nanmean(agg_t168):>+14.4f} {np.nanmean(agg_c168):>+10.4f} | {np.nanmean(agg_frac):>10.0%}")
        print("\nΔ (trend - chop) > 0 = il gate ER ISOLA i periodi dove il momentum funziona.")
        verdict = "GATE VALIDATO" if dt48 > 0.002 and dt168 > 0.002 else ("debole" if dt48 > 0 else "INVERTITO (gate sbagliato)")
        print(f"Verdetto @trend_pct=60: {verdict}")
        print(f"Tempo trending medio {np.nanmean(agg_frac):.0%} (target 40-55% per non soffocare).")


if __name__ == "__main__":
    main()
