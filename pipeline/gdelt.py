"""GDELT DOC API (gratis, no key) — condiviso tra fetch storico e live.

Rate limit: 1 req/5s, 429 frequenti → pacing + backoff esponenziale.
news_events_live() = stessa semantica di data/news/gdelt_events.parquet
(ts, topic, z, tone) ma calcolata sugli ultimi giorni: alimenta il segnale
news_event in paper/live trading.
"""

import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

API = "https://api.gdeltproject.org/api/v2/doc/doc"
HEADERS = {"User-Agent": "Mozilla/5.0 (defi-ai-vault research)"}
PACE_S = 6

# Bucket allineati all'universo HL: crypto perps + commodities/equity xyz_*
TOPICS = {
    "crypto": '(bitcoin OR ethereum OR cryptocurrency OR "crypto market") sourcelang:english',
    "fed_macro": '("federal reserve" OR "interest rate" OR inflation OR CPI OR FOMC) sourcelang:english',
    "commodities": '("gold price" OR "oil price" OR OPEC OR "crude oil" OR "natural gas price") sourcelang:english',
    "equities": '("stock market" OR "S&P 500" OR nasdaq OR "wall street") sourcelang:english',
    "geopolitics": '(war OR sanctions OR conflict OR military) (market OR economy) sourcelang:english',
}


def get(params: dict, max_retries: int = 8) -> dict | None:
    """GET con pacing e backoff su 429/errori."""
    for attempt in range(max_retries):
        time.sleep(PACE_S if attempt == 0 else min(PACE_S * 2**attempt, 300))
        try:
            r = requests.get(API, params=params, headers=HEADERS, timeout=60)
        except requests.RequestException as e:
            print(f"  retry {attempt+1}: {e}", flush=True)
            continue
        if r.status_code == 200:
            try:
                return r.json()
            except ValueError:
                continue
        print(f"  retry {attempt+1}: HTTP {r.status_code}", flush=True)
    return None


def timeline_df(query: str, start: datetime, end: datetime) -> pd.DataFrame | None:
    """Serie volume (+quota) e tono per una query su [start, end]. 2 richieste."""
    rows = {}
    for mode, col in (("timelinevolraw", "vol"), ("timelinetone", "tone")):
        d = get({"query": query, "mode": mode, "format": "json",
                 "startdatetime": start.strftime("%Y%m%d%H%M%S"),
                 "enddatetime": end.strftime("%Y%m%d%H%M%S")})
        if d is None:
            return None
        for series in d.get("timeline", []):
            for pt in series.get("data", []):
                ts = pd.Timestamp(pt["date"]).tz_localize(None)
                rows.setdefault(ts, {})[col] = pt["value"]
                if mode == "timelinevolraw" and "norm" in pt:
                    rows[ts]["vol_total"] = pt["norm"]
    if not rows:
        return None
    df = pd.DataFrame.from_dict(rows, orient="index").sort_index()
    df.index.name = "ts"
    return df.reset_index()


def news_events_live(days: int = 14, min_z: float = 3.0) -> pd.DataFrame | None:
    """Burst di news negli ultimi `days` giorni — (ts, topic, z, tone).
    Baseline = media/std della finestra stessa (conservativo: i burst la alzano)."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    out = []
    for topic, query in TOPICS.items():
        df = timeline_df(query, start, end)
        if df is None or df.empty:
            continue
        share = (df["vol"] / df["vol_total"]) if df.get("vol_total") is not None \
            and df["vol_total"].notna().any() else df["vol"]
        sd = share.std()
        if not sd or pd.isna(sd):
            continue
        zs = (share - share.mean()) / sd
        last = None
        for i in zs[zs > min_z].index:
            ts = df.loc[i, "ts"]
            if last is not None and (ts - last) < pd.Timedelta(hours=48):
                last = ts
                continue
            out.append({"ts": ts, "topic": topic, "z": float(zs[i]),
                        "tone": float(df.loc[i, "tone"]) if "tone" in df else None})
            last = ts
    return pd.DataFrame(out).sort_values("ts").reset_index(drop=True) if out else None
