"""Registry segnali leading/strutturali — gli unici componibili dalle strategie.

Niente indicatori mainstream/lagging (no SMA/RSI/MACD — decisione 11/06).
Ogni segnale: f(data, **params) -> pd.Series di {-1, 0, +1} allineata a
data["candles"] (indice 0..n-1). Il segno è la *lettura* del segnale
(es. +1 = crowding long), la direzione del trade la decide la strategia.

data: {"candles": df, "funding": df|None (ts, rate 8h), "flow": df|None (ts, volume, taker_buy),
       "news_events": df|None (ts, topic, z, tone — burst GDELT, vedi backtest/events.py),
       "cot": df|None (ts report COT settimanale, net_mm, oi, net_pct_oi)}
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
    """+1 = burst di news rilevante (GDELT) attivo nelle ultime max_age_h, 0 altrimenti.
    GATE DI RISCHIO, non direzionale: l'event study su 48 eventi (2026-06-13) ha
    falsificato l'uso direzionale del tono (tone_hit 0.38 < 0.50). Ciò che è reale è
    la VOLATILITÀ attorno all'evento: usalo come `entry.veto` per sospendere nuove
    entrate durante i burst, non per scegliere il lato. Mai -1. Vedi paper/lessons.jsonl."""
    c = data["candles"]
    ev = data.get("news_events")
    if ev is None or ev.empty:
        return pd.Series(0, index=c.index)
    wanted = [t.strip() for t in topics.split(",")]
    ev = ev[ev["topic"].isin(wanted) & (ev["z"] >= min_z)].sort_values("ts")
    if ev.empty:
        return pd.Series(0, index=c.index)
    # normalizza tz/risoluzione (parquet diversi: ms/us, naive/UTC)
    norm = lambda s: pd.to_datetime(s, utc=True).astype("datetime64[ns, UTC]")
    left = pd.DataFrame({"ts": norm(c["ts"])})
    right = pd.DataFrame({"ts": norm(ev["ts"])}).assign(ev_ts=lambda d: d["ts"])
    merged = pd.merge_asof(left, right, on="ts", direction="backward")
    active = (merged["ts"] - merged["ev_ts"]) <= pd.Timedelta(hours=max_age_h)
    return pd.Series(np.where(active.to_numpy(), 1, 0), index=c.index)


def cot_percentile(data, lookback_w: int = 26, extreme_pct: float = 85) -> pd.Series:
    """+1 = managed money net long a estremo storico (crowding long), -1 = estremo
    short. È il funding delle commodities: posizionamento speculativo dal report
    COT CFTC. Anti-lookahead: il report fotografa il martedì ma esce il venerdì
    → disponibile solo da ts+3 giorni."""
    c = data["candles"]
    cot = data.get("cot")
    if cot is None or len(cot) < lookback_w // 2:
        return pd.Series(0, index=c.index)
    cot = cot.sort_values("ts").copy()
    cot["pct"] = cot["net_pct_oi"].rolling(lookback_w, min_periods=lookback_w // 2) \
        .rank(pct=True) * 100
    # normalizza tz e risoluzione (parquet diversi: ms/us, naive/UTC)
    norm = lambda s: pd.to_datetime(s, utc=True).astype("datetime64[ns, UTC]")
    left = pd.DataFrame({"ts": norm(c["ts"])})
    right = pd.DataFrame({"ts": norm(cot["ts"] + pd.Timedelta(days=3)), "pct": cot["pct"]})
    aligned = pd.merge_asof(left, right, on="ts", direction="backward")["pct"]
    out = np.where(aligned >= extreme_pct, 1, np.where(aligned <= 100 - extreme_pct, -1, 0))
    return pd.Series(out, index=c.index)


_KRONOS_CACHE: dict = {}


def _kronos_load(symbol: str):
    """Cache forecast precomputata: data/kronos/<SYMBOL>.parquet (ts, ret_pred).
    Lazy + memoizzata. None se assente → il segnale degrada a neutro."""
    if symbol in _KRONOS_CACHE:
        return _KRONOS_CACHE[symbol]
    from pathlib import Path
    p = Path(f"data/kronos/{symbol}.parquet")
    df = pd.read_parquet(p) if p.exists() else None
    _KRONOS_CACHE[symbol] = df
    return df


def kronos_forecast(data, horizon_h: int = 24, min_move_pct: float = 1.0) -> pd.Series:
    """+1/-1 = il forecast Kronos prevede salita/discesa oltre `min_move_pct`
    sull'orizzonte `horizon_h`. Segnale LEADING strutturale (foundation model
    OHLCV, non lagging). Legge la cache precomputata offline (niente torch nel
    backtest); se la cache manca o non c'è il simbolo → neutro, niente errore.
    Anti-lookahead: merge_asof backward, ogni candela usa solo forecast a ts ≤ t."""
    c = data["candles"]
    sym = data.get("symbol")
    cache = _kronos_load(sym) if sym else None
    if cache is None or cache.empty:
        return pd.Series(0, index=c.index)
    col = "ret_pred" if "ret_pred" in cache.columns else cache.columns[-1]
    norm = lambda s: pd.to_datetime(s, utc=True).astype("datetime64[ns, UTC]")
    left = pd.DataFrame({"ts": norm(c["ts"])})
    right = pd.DataFrame({"ts": norm(cache["ts"]), col: cache[col].astype(float)}).sort_values("ts")
    ret = pd.merge_asof(left, right, on="ts", direction="backward")[col]
    thr = min_move_pct / 100.0
    out = np.where(ret >= thr, 1, np.where(ret <= -thr, -1, 0))
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
    "cot_percentile": cot_percentile,
    "kronos_forecast": kronos_forecast,
}
