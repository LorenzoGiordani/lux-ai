"""Studio d'edge per 3 pivot (sessione 26/06 — ispirazione DaviddTech).

Regola del progetto #4: nessun segnale/strategia entra senza edge misurato.

  [A] PULLBACK-IN-TREND (DaviddTech autentico: compra il ritorno nel trend)
      Quando il trend e' confermato (tsmom concorde), un pullback (prezzo tornato
      verso/oltre la baseline kernel) predice un ritorno futuro MIGLIORE di un
      ingresso a prezzo gia' esteso? Misura: fwd return medio condizionato a
        - trend_long  AND  NW = -1 (pullback: prezzo sotto banda, contro trend locale)
        - trend_long  AND  NW = +1 (estensione: prezzo sopra banda, col trend locale)
      Ipotesi DaviddTech: il pullback ha fwd return PIU' ALTO (prezzo migliore).
      (NW standalone era continuation; qui e' *filtro di timing* dentro il trend.)

  [B] FUNDING CARRY come segnale (short-high-funding paga)
      research_edges.py ha misurato IC panel funding↔fwdRet = -0.024 (t -5.7). Qui
      lo misuro come SEGNALE per-asset: contrarian:funding_percentile (short quando
      funding a estremo positivo = crowding long) ha IC positivo come standalone?
      Se sì, e' un diversificatore carry ortogonale a tutto il book (trend).

  [C] REGIME VETO effect (cura del lux-regime-3leg falsificato)
      Non e' un edge separato: misura quanto il veto di hmm_regime sui periodi chop
      migliorerebbe il drawdown del champion senza distruggere i trade. Calcola la
      frazione di tempo in chop e la volatilita' media dei ritorni in chop vs trend
      (se chop e' molto piu' noisy, il veto ha senso come vol-reducer).

Uso: uv run scripts/research_pivot.py [--symbols CSV] [--months 12]
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(ROOT))
from backtest.signals import nadaraya_watson, tsmom, funding_percentile

CRYPTO = "BTC,ETH,SOL,XRP,SUI,NEAR,WLD,ZEC,CRV"


def load(symbol, months):
    p = ROOT / f"data/candles/{symbol}.parquet"
    if not p.exists():
        return None
    c = pd.read_parquet(p).tail(months * 30 * 24).reset_index(drop=True)
    fp = ROOT / f"data/funding/{symbol}.parquet"
    funding = pd.read_parquet(fp) if fp.exists() else None
    return c, funding


def fwd(c, hz):
    return c.close.pct_change(hz).shift(-hz)


def per_asset_ic(sig, fwd_arr):
    mask = np.isfinite(sig) & np.isfinite(fwd_arr) & (sig != 0)
    if mask.sum() < 30:
        return np.nan, 0
    s = sig[mask]
    f = fwd_arr[mask]
    rs = pd.Series(s).rank().to_numpy()
    rf = pd.Series(f).rank().to_numpy()
    rs, rf = rs - rs.mean(), rf - rf.mean()
    den = np.sqrt((rs ** 2).sum() * (rf ** 2).sum())
    return float(rs @ rf / den) if den > 0 else np.nan, int(mask.sum())


def study_pullback(symbol, months, nw_params, hz):
    """fwd return medio nei 2 regimi (trend_long concorde): pullback vs extension."""
    d = load(symbol, months)
    if d is None:
        return None
    c, _ = d
    t = tsmom({"candles": c}, short_h=168, long_h=720)
    nw = nadaraya_watson({"candles": c}, **nw_params)
    fw = fwd(c, hz)
    # condiziona al trend long (tsmom=+1) e short (tsmom=-1) separatamente
    out = {}
    for tsign, name in [(1, "long"), (-1, "short")]:
        trend_on = t == tsign
        pull = (nw == -tsign) & trend_on      # prezzo tornato contro il trend locale
        ext = (nw == tsign) & trend_on        # prezzo esteso col trend locale
        out[f"{name}_pull_n"] = int(pull.sum())
        out[f"{name}_ext_n"] = int(ext.sum())
        out[f"{name}_pull_fwd"] = float(np.nanmean(fw[pull]) * tsign) if pull.any() else np.nan
        out[f"{name}_ext_fwd"] = float(np.nanmean(fw[ext]) * tsign) if ext.any() else np.nan
    out["symbol"] = symbol
    return out


def study_carry(symbol, months, hz):
    d = load(symbol, months)
    if d is None:
        return None
    c, funding = d
    if funding is None:
        return None
    data = {"candles": c, "funding": funding, "symbol": symbol}
    # contrarian:funding = -funding_percentile (short quando crowding long estremo)
    fp = -funding_percentile(data, lookback_h=168, extreme_pct=90)
    fw = fwd(c, hz)
    ic, n = per_asset_ic(fp.to_numpy(), fw.to_numpy())
    return {"symbol": symbol, "ic": ic, "n": n, "hz": hz}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=CRYPTO)
    ap.add_argument("--months", type=int, default=12)
    a = ap.parse_args()
    syms = a.symbols.split(",")

    nw_params = dict(lookback=72, bandwidth=12.0, mult=2.0)

    # --- [A] PULLBACK-IN-TREND ---
    print("=" * 78)
    print("[A] PULLBACK-IN-TREND — fwd return medio (segno allineato al trend)")
    print("    Ipotesi: pullback_fwd > ext_fwd (il ritorno nel trend paga di piu')")
    print("=" * 78)
    for hz in [12, 24, 48, 168]:
        rows = [study_pullback(s, a.months, nw_params, hz) for s in syms]
        rows = [r for r in rows if r]
        pl = np.nanmean([r["long_pull_fwd"] for r in rows if np.isfinite(r["long_pull_fwd"])])
        ex = np.nanmean([r["long_ext_fwd"] for r in rows if np.isfinite(r["long_ext_fwd"])])
        pls = np.nanmean([r["short_pull_fwd"] for r in rows if np.isfinite(r["short_pull_fwd"])])
        exs = np.nanmean([r["short_ext_fwd"] for r in rows if np.isfinite(r["short_ext_fwd"])])
        n_pl = sum(r["long_pull_n"] for r in rows)
        n_ex = sum(r["long_ext_n"] for r in rows)
        delta = pl - ex
        print(f"  hz={hz:>3}h | LONG pull {pl:+.4f} (n={n_pl:>5}) vs ext {ex:+.4f} (n={n_ex:>5}) "
              f"| Δ {delta:+.4f}  {'PULLBACK VINCE' if delta > 0.005 else ('EXT VINCE' if delta < -0.005 else 'neutro')}")
        print(f"         | SHORT pull {pls:+.4f} vs ext {exs:+.4f} | Δ {pls-exs:+.4f}")

    # --- [B] FUNDING CARRY come segnale ---
    print("\n" + "=" * 78)
    print("[B] FUNDING CARRY (contrarian:funding_percentile) — IC per-asset")
    print("    Ipotesi: IC > 0 (short high-funding = crowding long estremo reverte)")
    print("=" * 78)
    for hz in [24, 48, 168, 336]:
        rows = [study_carry(s, a.months, hz) for s in syms]
        rows = [r for r in rows if r]
        ics = [r["ic"] for r in rows if np.isfinite(r["ic"])]
        m = np.mean(ics) if ics else np.nan
        tstat = m / np.std(ics) * np.sqrt(len(ics)) if len(ics) > 1 else 0
        verdict = "SEGNALE (short high funding)" if tstat > 2 else ("debole" if abs(tstat) < 2 else " SEGNALE opposto")
        print(f"  hz={hz:>3}h | IC medio {m:+.4f} (t {tstat:+.1f}, {len(ics)} asset) → {verdict}")
        print("           per-asset: " + " ".join(f"{r['symbol']}:{r['ic']:+.3f}" for r in rows if np.isfinite(r['ic'])))

    # --- [C] REGIME VETO effect ---
    print("\n" + "=" * 78)
    print("[C] REGIME VETO — volatilita' dei ritorni in chop vs trend (giustifica il veto)")
    print("=" * 78)
    try:
        from backtest.walkforward import regimes
    except Exception:
        print("  (modulo walkforward non disponibile)"); return
    for symbol in syms[:4]:
        d = load(symbol, a.months)
        if d is None:
            continue
        c, _ = d
        reg = regimes(c).to_numpy()
        rets = c.close.pct_change().to_numpy()
        for name in ["bull", "bear", "chop"]:
            mask = reg == name
            if mask.sum() > 0:
                vol = np.nanstd(rets[mask])
                print(f"  {symbol:5} {name:5}: vol/ora {vol:.5f} ({mask.mean():.0%} del tempo)")
        print()


if __name__ == "__main__":
    main()
