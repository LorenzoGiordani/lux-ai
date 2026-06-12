"""Registry segnali leading/strutturali — gli unici componibili dalle strategie.

Niente indicatori mainstream/lagging (no SMA/RSI/MACD — decisione 11/06).
Ogni segnale: f(data, **params) -> pd.Series di {-1, 0, +1} allineata a
data["candles"] (indice 0..n-1). Il segno è la *lettura* del segnale
(es. +1 = crowding long), la direzione del trade la decide la strategia.

data: {"candles": df, "funding": df|None (ts, rate 8h), "flow": df|None (ts, volume, taker_buy),
       "news_events": df|None (ts, topic, z, tone — burst GDELT, vedi backtest/events.py)}
"""

import numpy as np
import pandas as pd


def _align(candles: pd.DataFrame, other: pd.DataFrame, col: str) -> pd.Series:
    """Allinea serie esterna alle candele via merge_asof (solo dati ≤ t)."""
    merged = pd.merge_asof(candles[["ts"]], other.sort_values("ts"), on="ts", direction="backward")
    return merged[col]


def funding_percentile(data, lookback_h: int = 168, extreme_pct: float = 90) -> pd.Series:
    """+1 = funding a estremo positivo (crowding long), -1 = estremo negativo."""
    candles = data["candles"]
    if data.get("funding") is None:
        return pd.Series(0, index=candles.index)
    rate = _align(candles, data["funding"], "rate").fillna(0.0)
    pct = rate.abs().rolling(lookback_h, min_periods=lookback_h // 2).rank(pct=True) * 100
    out = np.where((pct >= extreme_pct) & (rate > 0), 1, np.where((pct >= extreme_pct) & (rate < 0), -1, 0))
    return pd.Series(out, index=candles.index)


def range_breakout(data, range_h: int = 48, volume_confirm_mult: float = 2.0) -> pd.Series:
    """+1 = chiusura sopra il massimo del range precedente con volume, -1 = sotto il minimo."""
    c = data["candles"]
    hi = c.high.rolling(range_h).max().shift(1)
    lo = c.low.rolling(range_h).min().shift(1)
    vol_ok = c.volume > volume_confirm_mult * c.volume.rolling(range_h).mean().shift(1)
    out = np.where((c.close > hi) & vol_ok, 1, np.where((c.close < lo) & vol_ok, -1, 0))
    return pd.Series(out, index=c.index)


def taker_flow(data, lookback_h: int = 24, threshold: float = 0.02) -> pd.Series:
    # threshold calibrata su BTC 12 mesi: |ratio-0.5| p90 ≈ 0.02 (24h) / 0.027 (12h)
    """+1 = aggressori in acquisto (taker buy ratio > 0.5+thr), -1 = in vendita."""
    candles = data["candles"]
    flow = data.get("flow")
    if flow is None:
        return pd.Series(0, index=candles.index)
    f = flow.copy()
    f["ratio"] = (f.taker_buy / f.volume.replace(0, np.nan)).fillna(0.5)
    ratio = _align(candles, f, "ratio").rolling(lookback_h, min_periods=lookback_h // 2).mean()
    out = np.where(ratio > 0.5 + threshold, 1, np.where(ratio < 0.5 - threshold, -1, 0))
    return pd.Series(out, index=candles.index)


def vol_compression(data, lookback_h: int = 48, pct: float = 20) -> pd.Series:
    """+1 = volatilità compressa vs storia recente (setup pre-espansione). Mai -1."""
    c = data["candles"]
    rng = (c.high - c.low) / c.close
    cur = rng.rolling(lookback_h, min_periods=lookback_h // 2).mean()
    rank = cur.rolling(lookback_h * 10, min_periods=lookback_h * 2).rank(pct=True) * 100
    return pd.Series(np.where(rank <= pct, 1, 0), index=c.index)


def tsmom(data, short_h: int = 168, long_h: int = 720) -> pd.Series:
    """Time-series momentum (Moskowitz-Ooi-Pedersen adattato a 1h): +1 se il
    ritorno su ENTRAMBI gli orizzonti è positivo, -1 se entrambi negativi.
    Universale: solo close. L'edge istituzionale più documentato (58 futures, decenni)."""
    c = data["candles"].close
    r_short, r_long = c.pct_change(short_h), c.pct_change(long_h)
    out = np.where((r_short > 0) & (r_long > 0), 1, np.where((r_short < 0) & (r_long < 0), -1, 0))
    return pd.Series(out, index=data["candles"].index)


def vwap_zscore(data, lookback_h: int = 168, z: float = 2.0) -> pd.Series:
    """Deviazione dal VWAP rolling in z-score: +1 = prezzo esteso SOPRA il vwap
    (oltre z sigma), -1 = esteso sotto. Lettura di estensione: la strategia
    decide se seguirla (trend) o farne il fade (mean reversion)."""
    c = data["candles"]
    pv = (c.close * c.volume).rolling(lookback_h, min_periods=lookback_h // 2).sum()
    v = c.volume.rolling(lookback_h, min_periods=lookback_h // 2).sum().replace(0, np.nan)
    vwap = pv / v
    dev = c.close - vwap
    zs = dev / dev.rolling(lookback_h, min_periods=lookback_h // 2).std().replace(0, np.nan)
    out = np.where(zs > z, 1, np.where(zs < -z, -1, 0))
    return pd.Series(out, index=c.index)


def volume_surge(data, lookback_h: int = 168, pct: float = 90) -> pd.Series:
    """+1 = volume corrente nel percentile alto della storia recente
    (partecipazione anomala — conferma la mossa in atto). Mai -1."""
    c = data["candles"]
    rank = c.volume.rolling(lookback_h, min_periods=lookback_h // 2).rank(pct=True) * 100
    return pd.Series(np.where(rank >= pct, 1, 0), index=c.index)


def news_event(data, topics: str = "crypto", max_age_h: int = 24, min_z: float = 3.0) -> pd.Series:
    """+1 = evento news (burst GDELT) a tono positivo nelle ultime max_age_h,
    -1 = tono negativo. Leading per costruzione: il burst È il catalizzatore.
    Seguire la reazione o farne il fade lo decide la strategia (direction)."""
    c = data["candles"]
    ev = data.get("news_events")
    if ev is None or ev.empty:
        return pd.Series(0, index=c.index)
    wanted = [t.strip() for t in topics.split(",")]
    ev = ev[ev["topic"].isin(wanted) & (ev["z"] >= min_z)].sort_values("ts")
    if ev.empty:
        return pd.Series(0, index=c.index)
    ev = ev.assign(ev_ts=ev["ts"], ev_tone=ev["tone"])
    merged = pd.merge_asof(c[["ts"]], ev[["ts", "ev_ts", "ev_tone"]], on="ts", direction="backward")
    age_ok = (merged["ts"] - merged["ev_ts"]) <= pd.Timedelta(hours=max_age_h)
    out = np.where(age_ok & (merged["ev_tone"] > 0), 1,
                   np.where(age_ok & (merged["ev_tone"] < 0), -1, 0))
    return pd.Series(out, index=c.index)


SIGNALS = {
    "funding_percentile": funding_percentile,
    "range_breakout": range_breakout,
    "taker_flow": taker_flow,
    "vol_compression": vol_compression,
    "tsmom": tsmom,
    "vwap_zscore": vwap_zscore,
    "volume_surge": volume_surge,
    "news_event": news_event,
}
