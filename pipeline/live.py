"""Dati live per pipeline e paper trading (Binance fapi + RSS news, gratis)."""

import time
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree

import pandas as pd
import requests

FAPI = "https://fapi.binance.com"
RSS_FEEDS = {
    "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "decrypt": "https://decrypt.co/feed",
}


def fetch_live(symbol: str, lookback_h: int = 1000) -> dict:
    """Candele 1h chiuse + taker flow + funding — stesso formato del backtest."""
    pair = f"{symbol}USDT"
    kl = requests.get(f"{FAPI}/fapi/v1/klines", params={
        "symbol": pair, "interval": "1h", "limit": min(lookback_h, 1000)}, timeout=30).json()
    candles = pd.DataFrame({
        "ts": pd.to_datetime([k[0] for k in kl], unit="ms", utc=True),
        "open": [float(k[1]) for k in kl], "high": [float(k[2]) for k in kl],
        "low": [float(k[3]) for k in kl], "close": [float(k[4]) for k in kl],
        "volume": [float(k[5]) for k in kl]})
    flow = pd.DataFrame({"ts": candles.ts, "volume": candles.volume,
                         "taker_buy": [float(k[9]) for k in kl]})
    fr = requests.get(f"{FAPI}/fapi/v1/fundingRate", params={
        "symbol": pair, "limit": 1000}, timeout=30).json()
    funding = pd.DataFrame({
        "ts": pd.to_datetime([r["fundingTime"] for r in fr], unit="ms", utc=True),
        "rate": [float(r["fundingRate"]) for r in fr]})
    time.sleep(0.1)
    # ultima candela è in corso → si decide sull'ultima CHIUSA
    return {"candles": candles.iloc[:-1].reset_index(drop=True), "flow": flow, "funding": funding}


def open_interest_24h(symbol: str) -> dict | None:
    """OI corrente + variazione 24h (storico Binance: solo 30 giorni, ok per live)."""
    try:
        hist = requests.get(f"{FAPI}/futures/data/openInterestHist", params={
            "symbol": f"{symbol}USDT", "period": "1h", "limit": 25}, timeout=30).json()
        if not isinstance(hist, list) or len(hist) < 2:
            return None
        now, prev = float(hist[-1]["sumOpenInterestValue"]), float(hist[0]["sumOpenInterestValue"])
        return {"oi_usd": now, "oi_change_24h": now / prev - 1}
    except Exception:
        return None


def news_headlines(max_age_h: int = 36) -> list[dict]:
    """Titoli RSS recenti, timestampati. Fonti gratuite e affidabili."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_h)
    out = []
    for source, url in RSS_FEEDS.items():
        try:
            r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            root = ElementTree.fromstring(r.content)
            for item in root.iter("item"):
                title = item.findtext("title", "").strip()
                pub = item.findtext("pubDate", "")
                try:
                    ts = pd.to_datetime(pub, utc=True)
                except Exception:
                    continue
                if title and ts >= cutoff:
                    out.append({"source": source, "ts": str(ts), "title": title})
        except Exception:
            continue
    return sorted(out, key=lambda x: x["ts"], reverse=True)
