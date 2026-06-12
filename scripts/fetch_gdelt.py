"""Scarica 12 mesi di news GDELT per topic bucket (DOC API, gratis, no key).

Strategia a 2 passate per restare nei rate limit (1 req/5s, 429 frequenti):
1. timelinevolraw + timelinetone per topic/mese → serie giornaliere volume/tono
2. solo attorno ai burst: timeline 15-min su 48h (ora esatta dell'evento) +
   artlist (titoli per contesto LLM/journal)

Anti-lookahead: seendate = quando GDELT ha visto l'articolo (point-in-time).

Output:
  data/news/gdelt_timeline.parquet  — ts (daily), topic, vol, vol_total, tone
  data/news/gdelt_events.parquet    — ts (15-min refined), topic, z, tone
  data/news/gdelt_articles.parquet  — ts, topic, title, domain, url

Uso: .venv/bin/python scripts/fetch_gdelt.py [--months 12] [--skip-articles]
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.gdelt import TOPICS, PACE_S, get as _get  # noqa: E402

OUT_DIR = ROOT / "data" / "news"


def month_windows(months: int) -> list[tuple[str, str]]:
    # una sola finestra: GDELT torna risoluzione daily anche su 12 mesi
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=30 * months)
    return [(start.strftime("%Y%m%d%H%M%S"), end.strftime("%Y%m%d%H%M%S"))]


def fetch_timeline(topic: str, query: str, windows: list) -> pd.DataFrame:
    rows = {}
    for mode, col in (("timelinevolraw", "vol"), ("timelinetone", "tone")):
        for start, end in windows:
            d = _get({"query": query, "mode": mode, "format": "json",
                      "startdatetime": start, "enddatetime": end})
            if d is None:
                print(f"  {topic} {mode} {start[:8]}: FALLITO, salto", flush=True)
                continue
            for series in d.get("timeline", []):
                for pt in series.get("data", []):
                    ts = pd.Timestamp(pt["date"]).tz_localize(None)
                    rows.setdefault(ts, {})[col] = pt["value"]
                    if mode == "timelinevolraw" and "norm" in pt:
                        rows[ts]["vol_total"] = pt["norm"]
            print(f"  {topic} {mode} {start[:8]} ok", flush=True)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame.from_dict(rows, orient="index").sort_index()
    df.index.name = "ts"
    df["topic"] = topic
    return df.reset_index()


def detect_bursts(tl: pd.DataFrame, z: float = 2.0, baseline_d: int = 14) -> pd.DataFrame:
    """Burst day = quota volume oltre z deviazioni dalla baseline rolling.
    Burst contigui (<48h, stesso topic) collassati sul primo giorno."""
    out = []
    for topic, g in tl.groupby("topic"):
        g = g.set_index("ts").sort_index()
        # quota su tutto GDELT: robusta a variazioni di copertura della fonte
        v = g["vol"] / g["vol_total"] if "vol_total" in g and g["vol_total"].notna().any() else g["vol"]
        mu = v.rolling(baseline_d, min_periods=baseline_d // 2).mean()
        sd = v.rolling(baseline_d, min_periods=baseline_d // 2).std()
        zs = (v - mu) / sd.replace(0, pd.NA)
        burst_days = zs[zs > z]
        last = None
        for ts, zval in burst_days.items():
            if last is not None and (ts - last) < pd.Timedelta(hours=48):
                last = ts
                continue
            out.append({"ts": ts, "topic": topic, "z": float(zval),
                        "tone": float(g.loc[ts, "tone"]) if "tone" in g else None})
            last = ts
    return pd.DataFrame(out).sort_values("ts") if out else pd.DataFrame()


def refine_event_ts(query: str, day: pd.Timestamp) -> pd.Timestamp | None:
    """Ora esatta del picco: timeline 15-min sulle 48h dal giorno del burst."""
    d = _get({"query": query, "mode": "timelinevolraw", "format": "json",
              "startdatetime": day.strftime("%Y%m%d%H%M%S"),
              "enddatetime": (day + pd.Timedelta(hours=48)).strftime("%Y%m%d%H%M%S")})
    if not d or not d.get("timeline"):
        return None
    pts = d["timeline"][0]["data"]
    if not pts:
        return None
    s = pd.Series({pd.Timestamp(p["date"]).tz_localize(None): p["value"] for p in pts})
    return s.rolling(4, min_periods=1).mean().idxmax()  # picco su 1h smussata


def fetch_articles(query: str, topic: str, ts: pd.Timestamp, per_event: int = 25) -> list[dict]:
    d = _get({"query": query, "mode": "artlist", "format": "json",
              "maxrecords": per_event, "sort": "hybridrel",
              "startdatetime": (ts - pd.Timedelta(hours=2)).strftime("%Y%m%d%H%M%S"),
              "enddatetime": (ts + pd.Timedelta(hours=24)).strftime("%Y%m%d%H%M%S")})
    if not d:
        return []
    return [{"ts": pd.Timestamp(a["seendate"]).tz_localize(None), "topic": topic,
             "title": a.get("title", ""), "domain": a.get("domain", ""),
             "url": a.get("url", "")} for a in d.get("articles", [])]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--skip-articles", action="store_true")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    windows = month_windows(args.months)
    print(f"{len(TOPICS)} topic × {len(windows)} mesi × 2 modi ≈ "
          f"{len(TOPICS)*len(windows)*2} richieste a {PACE_S}s", flush=True)

    tl_path = OUT_DIR / "gdelt_timeline.parquet"
    if tl_path.exists():
        tl = pd.read_parquet(tl_path)  # riprendi da run interrotto
        print(f"timeline esistente: {len(tl)} righe (riuso)", flush=True)
    else:
        frames = [fetch_timeline(t, q, windows) for t, q in TOPICS.items()]
        tl = pd.concat([f for f in frames if not f.empty], ignore_index=True)
        if tl.empty:
            sys.exit("Nessun dato timeline scaricato")
        tl.to_parquet(tl_path, index=False)
        print(f"timeline: {len(tl)} righe → gdelt_timeline.parquet", flush=True)

    # ripara topic con vol mancante (run precedenti falliti su quel modo)
    broken = [t for t, g in tl.groupby("topic") if g["vol"].isna().all()]
    if broken:
        fixed = [fetch_timeline(t, TOPICS[t], windows) for t in broken]
        tl = pd.concat([tl[~tl["topic"].isin(broken)]] + [f for f in fixed if not f.empty],
                       ignore_index=True)
        tl.to_parquet(tl_path, index=False)
        print(f"riparati {broken}: {len(tl)} righe", flush=True)

    events = detect_bursts(tl)
    print(f"eventi (burst clusterizzati): {len(events)}", flush=True)
    if events.empty:
        return

    # resume: eventi già raffinati in run precedenti (stesso topic, ts entro 48h dal burst day)
    ev_path = OUT_DIR / "gdelt_events.parquet"
    done = pd.read_parquet(ev_path) if ev_path.exists() else pd.DataFrame(columns=["ts", "topic", "z", "tone"])

    def already(topic, day):
        m = done[(done["topic"] == topic) & (done["ts"] >= day)
                 & (done["ts"] <= day + pd.Timedelta(hours=48))]
        return None if m.empty else m.iloc[0]["ts"]

    articles = []
    for _, ev in events.iterrows():
        ts = already(ev["topic"], ev["ts"])
        if ts is None:
            ts = refine_event_ts(TOPICS[ev["topic"]], ev["ts"]) or ev["ts"]
            done = pd.concat([done, pd.DataFrame([{**ev, "ts": ts}])], ignore_index=True)
            done.sort_values("ts").to_parquet(ev_path, index=False)  # salvataggio incrementale
            print(f"  evento {ev['topic']} {ev['ts'].date()} → {ts}", flush=True)
        if not args.skip_articles:
            articles += fetch_articles(TOPICS[ev["topic"]], ev["topic"], ts)
    print(f"eventi: {len(done)} → gdelt_events.parquet", flush=True)

    if articles:
        arts = pd.DataFrame(articles).drop_duplicates(subset=["topic", "title"])
        arts.to_parquet(OUT_DIR / "gdelt_articles.parquet", index=False)
        print(f"articoli: {len(arts)} → gdelt_articles.parquet", flush=True)


if __name__ == "__main__":
    main()
