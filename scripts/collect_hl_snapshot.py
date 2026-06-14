"""Snapshot OI + funding + prezzi da Hyperliquid → storico che ci manca.

Hyperliquid espone OI/funding solo CORRENTI (niente storico gratis). Questo script
campiona `metaAndAssetCtxs` e accumula righe orarie in data/hl_oi/<YYYY-MM>.parquet.
Forward-collection: girando ogni ora costruisce lo storico per i futuri segnali di
posizionamento/liquidazione (squeeze = OI in crescita + funding estremo; deleveraging
= calo brusco di OI). Niente flag liquidazione pubblico su HL → l'OI-delta è il proxy.

Idempotente: una riga per (ora, coin); rilanci nella stessa ora non duplicano.

Uso:  .venv/bin/python scripts/collect_hl_snapshot.py
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data/hl_oi"
HL_INFO = "https://api.hyperliquid.xyz/info"


def snapshot() -> pd.DataFrame:
    r = requests.post(HL_INFO, json={"type": "metaAndAssetCtxs"}, timeout=30).json()
    meta, ctxs = r[0]["universe"], r[1]
    ts = pd.Timestamp(datetime.now(timezone.utc)).floor("h")  # ancora all'ora (come le candele)
    rows = []
    for m, c in zip(meta, ctxs):
        try:
            rows.append({
                "ts": ts, "coin": m["name"],
                "oi": float(c["openInterest"]),
                "funding": float(c["funding"]),
                "mark": float(c["markPx"]),
                "oracle": float(c["oraclePx"]) if c.get("oraclePx") else None,
                "premium": float(c["premium"]) if c.get("premium") else None,
                "day_ntl_vlm": float(c["dayNtlVlm"]) if c.get("dayNtlVlm") else None,
            })
        except (KeyError, TypeError, ValueError):
            continue
    return pd.DataFrame(rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = snapshot()
    if df.empty:
        sys.exit("snapshot vuoto — API HL non raggiungibile?")
    month = pd.Timestamp(df["ts"].iloc[0]).strftime("%Y-%m")
    path = OUT_DIR / f"{month}.parquet"
    if path.exists():
        old = pd.read_parquet(path)
        df = pd.concat([old, df], ignore_index=True)
    # dedup: tieni l'ultima riga per (ts, coin) — rilanci nella stessa ora sovrascrivono
    df = df.drop_duplicates(subset=["ts", "coin"], keep="last").sort_values(["ts", "coin"])
    df.to_parquet(path, index=False)
    hours = df["ts"].nunique()
    print(f"snapshot HL: {df['coin'].nunique()} coin, {hours} ore in {path.name} ({len(df)} righe)")


if __name__ == "__main__":
    main()
