"""Event study: reazione degli asset HL agli eventi news GDELT.

Per ogni (topic, asset, orizzonte): ritorno forward dal primo close DOPO
l'evento (anti-lookahead), grezzo e firmato col tono della news
(tone>0 → ci si aspetta ret>0). Output = matrice di reazione: dove c'è
|t-stat| decente nasce una strategia event-driven candidata.
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
HORIZONS_H = (1, 4, 24)


def _naive_utc(s: pd.Series) -> pd.Series:
    s = pd.to_datetime(s)
    return s.dt.tz_convert("UTC").dt.tz_localize(None) if s.dt.tz is not None else s


def load_events(path: Path | None = None) -> pd.DataFrame:
    ev = pd.read_parquet(path or ROOT / "data" / "news" / "gdelt_events.parquet")
    ev["ts"] = _naive_utc(ev["ts"])
    return ev.sort_values("ts").reset_index(drop=True)


def asset_reactions(candles: pd.DataFrame, events: pd.DataFrame,
                    horizons=HORIZONS_H) -> pd.DataFrame:
    """Una riga per (evento, orizzonte): ritorno forward dal primo close ≥ ts evento."""
    c = candles.copy()
    c["ts"] = _naive_utc(c["ts"])
    c = c.sort_values("ts").reset_index(drop=True)
    close, ts = c["close"].to_numpy(), c["ts"].to_numpy()

    rows = []
    for _, ev in events.iterrows():
        i0 = int(np.searchsorted(ts, np.datetime64(ev["ts"])))  # primo close ≥ evento
        if i0 >= len(close) - max(horizons):
            continue
        for h in horizons:
            ret = close[i0 + h] / close[i0] - 1
            rows.append({"event_ts": ev["ts"], "topic": ev["topic"], "z": ev["z"],
                         "tone": ev.get("tone"), "horizon_h": h, "ret": ret})
    return pd.DataFrame(rows)


def reaction_matrix(symbols: list[str], events: pd.DataFrame,
                    horizons=HORIZONS_H, min_events: int = 5) -> pd.DataFrame:
    """Aggregato (topic, symbol, horizon): n, ritorno medio/abs, t-stat, hit rate col tono."""
    out = []
    for sym in symbols:
        path = ROOT / "data" / "candles" / f"{sym}.parquet"
        if not path.exists():
            continue
        candles = pd.read_parquet(path)
        r = asset_reactions(candles, events, horizons)
        if r.empty:
            continue
        # baseline: ritorno medio h-ore dell'asset (per il ritorno anomalo)
        c = candles["close"]
        for (topic, h), g in r.groupby(["topic", "horizon_h"]):
            if len(g) < min_events:
                continue
            base = c.pct_change(h).mean()
            tone_sign = np.sign(g["tone"].fillna(0))
            signed = np.where(tone_sign != 0, tone_sign * g["ret"], np.nan)
            signed = signed[~np.isnan(signed)]
            sd = g["ret"].std(ddof=1)
            out.append({
                "symbol": sym, "topic": topic, "horizon_h": h, "n": len(g),
                "mean_ret": g["ret"].mean(), "abn_ret": g["ret"].mean() - base,
                "mean_abs_ret": g["ret"].abs().mean(),
                "t": g["ret"].mean() / sd * np.sqrt(len(g)) if sd > 0 else 0.0,
                "tone_hit": float((signed > 0).mean()) if len(signed) else np.nan,
                "tone_n": len(signed),
            })
    return pd.DataFrame(out)
