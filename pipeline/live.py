"""Dati live per pipeline e paper trading (Binance fapi + RSS news, gratis)."""

import time
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree

import pandas as pd
import requests

FAPI = "https://fapi.binance.com"
RSS_FEEDS = {
    # crypto
    "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "decrypt": "https://decrypt.co/feed",
    # macro / commodities / equity
    "forexlive": "https://www.forexlive.com/feed/news",
    "oilprice": "https://oilprice.com/rss/main",
    "cnbc_markets": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    "marketwatch": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
}


# universo perp live da Hyperliquid (dex validator-operated = "core"). Niente file:
# i runner cloud non hanno data/universe.csv. Cache di modulo: 1 fetch per processo.
_PERP_CACHE: dict = {}


def core_perp_symbols(min_vol_usd: float = 1_000_000) -> str:
    """Perp core HL con volume 24h >= min_vol_usd, ordinati per liquidita, come
    stringa CSV pronta per paper_trade. Esclude i delisted. Stringa vuota se l'API
    non risponde (il chiamante fa fallback). Cache per-processo, chiave = soglia."""
    key = round(min_vol_usd)
    if key in _PERP_CACHE:
        return _PERP_CACHE[key]
    try:
        r = requests.post("https://api.hyperliquid.xyz/info",
                          json={"type": "metaAndAssetCtxs", "dex": ""}, timeout=30)
        meta, ctxs = r.json()
    except Exception:
        return ""
    rows = [(a["name"], float(c["dayNtlVlm"]))
            for a, c in zip(meta["universe"], ctxs) if not a.get("isDelisted")]
    rows = sorted((t for t in rows if t[1] >= min_vol_usd), key=lambda t: -t[1])
    out = ",".join(s for s, _ in rows)
    _PERP_CACHE[key] = out
    return out


def fetch_live(symbol: str, lookback_h: int = 1000) -> dict:
    """Candele 1h chiuse + taker flow + funding — stesso formato del backtest.
    Simboli xyz_* (commodities/stock/index) → yfinance, niente flow/funding.
    Binance geo-blocca i runner cloud (US) → fallback Hyperliquid (globale)."""
    if symbol.startswith("xyz_"):
        return _fetch_yf(symbol)
    try:
        return _fetch_binance(symbol, lookback_h)
    except Exception:
        return _fetch_hl(symbol, lookback_h)


def _fetch_binance(symbol: str, lookback_h: int) -> dict:
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
    # ultima candela è in corso → i SEGNALI si decidono sull'ultima CHIUSA;
    # "forming" (la barra in corso) serve solo per le USCITE stop/target intrabar
    return {"candles": candles.iloc[:-1].reset_index(drop=True),
            "forming": candles.iloc[-1], "flow": flow, "funding": funding}


HL_INFO = "https://api.hyperliquid.xyz/info"


def _fetch_hl(symbol: str, lookback_h: int) -> dict:
    """Hyperliquid public info API: candele + funding. Niente taker flow
    (il segnale taker_flow resta neutro — degradazione esplicita, non errore)."""
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - min(lookback_h, 5000) * 3_600_000
    kl = requests.post(HL_INFO, json={"type": "candleSnapshot", "req": {
        "coin": symbol, "interval": "1h", "startTime": start_ms, "endTime": end_ms}},
        timeout=30).json()
    candles = pd.DataFrame({
        "ts": pd.to_datetime([k["t"] for k in kl], unit="ms", utc=True),
        "open": [float(k["o"]) for k in kl], "high": [float(k["h"]) for k in kl],
        "low": [float(k["l"]) for k in kl], "close": [float(k["c"]) for k in kl],
        "volume": [float(k["v"]) for k in kl]})
    funding = None
    try:
        fr = requests.post(HL_INFO, json={"type": "fundingHistory", "coin": symbol,
                                          "startTime": start_ms}, timeout=30).json()
        if fr:
            funding = pd.DataFrame({
                "ts": pd.to_datetime([f["time"] for f in fr], unit="ms", utc=True),
                "rate": [float(f["fundingRate"]) for f in fr]})
    except Exception:
        pass
    return {"candles": candles.iloc[:-1].reset_index(drop=True),
            "forming": candles.iloc[-1], "flow": None, "funding": funding}


def _fetch_yf(symbol: str) -> dict:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.fetch_candles import from_yfinance
    # 320 giorni: gli asset a orario di mercato (stock ~7 barre/g) devono coprire
    # il lookback massimo dei segnali (tsmom long_h=720 barre)
    start = datetime.now(timezone.utc) - timedelta(days=320)
    df = from_yfinance(symbol.removeprefix("xyz_"), start)
    if df is None or df.empty:
        raise RuntimeError(f"yfinance vuoto per {symbol}")
    return {"candles": df.iloc[:-1].reset_index(drop=True),
            "forming": df.iloc[-1], "flow": None, "funding": None}


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
    out = sorted(out, key=lambda x: x["ts"], reverse=True)
    _archive_headlines(out)
    return out


def _archive_headlines(items: list[dict]) -> None:
    """Archivio point-in-time append-only (anti-lookahead per backtest futuri).
    fetched_at = quando NOI abbiamo visto il titolo; dedup su (source, title)."""
    import hashlib
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "data" / "news" / "live_archive.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    seen = set()
    if path.exists():
        with path.open() as f:
            seen = {json.loads(line)["id"] for line in f if line.strip()}
    fetched_at = str(datetime.now(timezone.utc))
    with path.open("a") as f:
        for it in items:
            hid = hashlib.sha1(f"{it['source']}|{it['title']}".encode()).hexdigest()[:16]
            if hid in seen:
                continue
            f.write(json.dumps({"id": hid, "fetched_at": fetched_at, **it},
                               ensure_ascii=False) + "\n")
