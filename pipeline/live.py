"""Dati live per pipeline e paper trading (Binance fapi + RSS news, gratis)."""

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
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


# universo perp live da Hyperliquid: TUTTI i dex (core "" + HIP-3 builder). Niente
# file (i runner cloud non hanno data/universe.csv). I nomi sono gia dex-qualificati
# (es. "xyz:SP500", "hyna:HYPE"); HL li serve via candleSnapshot. Cache di modulo.
_INFO = "https://api.hyperliquid.xyz/info"
_PERP_CACHE: dict = {}


# Pattern per riconoscere un qualificatore di venue HIP-3 (es. "xyz:NATGAS",
# "hyna:HYPE") o il prefisso legacy "xyz_NATGAS": vanno preservati tali e quali
# (Hyperliquid li serve via candleSnapshot con i due punti), non normalizzati.
import re as _re
_QUOTE_SUFFIXES = ("USDT", "USDC", "USD", "BUSD", "TUSD", "PERP")

# Alias commodity -> base coin canonico. L'LLM (desk geopolitico) emette nomi
# incoerenti per lo stesso underlying: NG / NATGAS / NG1! sono tutti natural
# gas, WTI e' crude oil. Senza questo aliasing le decisioni su "NG" non si
# riconciliano con la posizione "NATGAS" in state -> feed e posizioni discordano.
_COMMODITY_ALIASES = {
    "NG": "NATGAS", "NG1": "NATGAS", "NG1!": "NATGAS", "NATGAS": "NATGAS", "NATURALGAS": "NATGAS",
    "WTI": "CL", "CRUDE": "CL", "CL": "CL",
    "BRENT": "BRENTOIL", "BRENTOIL": "BRENTOIL",
    "XAUUSD": "GOLD", "XAU": "GOLD", "GOLD": "GOLD",
    "XAGUSD": "SILVER", "XAG": "SILVER", "SILVER": "SILVER",
}


def canonical_symbol(symbol) -> str:
    """Normalizza un simbolo emesso dall'LLM nel BASE coin canonico usato dal sistema.

    L'LLM produce di tutto ("SOL/USDT", "SOLUSDT", "SOL-PERP", "ETH/USDT PERP",
    "SOL/USDT:USDT", "SUI-USDT-PERP"...) mentre lo stato, il journal e le API
    Hyperliquid usano solo il base coin pulito ("SOL", "ETH"). Senza questa
    normalizzazione le decisioni non vengono riconciliate con le posizioni reali:
    il feed mostra "tante decisioni" senza esito, staccate dalle posizioni aperte.

    I qualificatori HIP-3 ("xyz:NATGAS", "hyna:HYPE") e il legacy "xyz_NATGAS"
    vengono preservati (sono nomi di venue, non da normalizzare)."""
    if symbol is None:
        return ""
    s = str(symbol).strip()
    if not s:
        return ""
    # preserva asset HIP-3 / legacy: la parte prima di ':' o 'xyz_' e' la venue
    # (xyz:NATGAS, hyna:HYPE). MA se prima dei ':' c'e' gia' uno slash o un quote
    # ("SOL/USDT:USDT" e' il market-type di Binance), quello dopo ':' si butta.
    if s.startswith("xyz_"):
        return s
    if ":" in s:
        head = s.split(":", 1)[0]
        if "/" in head or any(head.endswith(q) for q in _QUOTE_SUFFIXES):
            s = head            # market-type dopo i ':' -> scartato
        else:
            return s            # qualificatore venue HIP-3 -> preserva tale e quale
    s = s.upper()
    s = _re.sub(r"\s+", "", s)
    # stacca ripetutamente i suffissi quote separati da - o / o appiciccolati.
    # gestisce "SUI-USDT-PERP" -> "SUI" e "SOL/USDT" -> "SOL"
    changed = True
    while changed:
        changed = False
        for sep in ("-", "/"):
            for q in _QUOTE_SUFFIXES:
                tag = sep + q
                if s.endswith(tag) and len(s) > len(tag):
                    s = s[: -len(tag)]
                    changed = True
        for q in _QUOTE_SUFFIXES:  # quote appiccicato: "SOLUSDT" -> "SOL"
            if s.endswith(q) and len(s) > len(q):
                s = s[: -len(q)]
                changed = True
    s = s.replace("/", "").replace("-", "")
    # alias commodity: NG/NG1!/WTI/XAUUSD -> NATGAS/CL/GOLD (stesso underlying,
    # nomi diversi emessi dall'LLM). Solo sui base coin puliti.
    return _COMMODITY_ALIASES.get(s, s)


def _perp_dexs() -> list[str]:
    dexs = requests.post(_INFO, json={"type": "perpDexs"}, timeout=20).json()
    return [""] + [d["name"] for d in dexs if d and d.get("name")]


def _dedup_by_underlying(rows: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """Una sola variante per underlying. Lo stesso asset puo essere listato su piu
    venue (es. core 'HYPE' + builder 'hyna:HYPE', o commodity su piu dex) → tenerne
    due = doppia esposizione sullo stesso rischio. Con rows ordinate desc per volume,
    tiene la prima (la piu liquida). Base = parte dopo l'ultimo ':' (dex-qualificato)."""
    seen, out = set(), []
    for name, vol in rows:
        base = name.split(":")[-1].upper()
        if base not in seen:
            seen.add(base)
            out.append((name, vol))
    return out


def perp_universe(min_vol_usd: float = 250_000) -> list[tuple[str, float]]:
    """(nome, volume 24h) di tutti i perp HL >= soglia, su tutti i dex, ordinati per
    liquidita. Esclude i delisted. Lista vuota se l'API non risponde (il chiamante fa
    fallback). Il floor e solo un bound di compute: il vero gate liquidita e per-trade
    (in paper_trade). Cache per-processo, chiave = soglia."""
    key = round(min_vol_usd)
    if key in _PERP_CACHE:
        return _PERP_CACHE[key]
    rows: list[tuple[str, float]] = []
    try:
        for dex in _perp_dexs():
            meta, ctxs = requests.post(_INFO,
                json={"type": "metaAndAssetCtxs", "dex": dex}, timeout=20).json()
            rows += [(a["name"], float(c["dayNtlVlm"]))
                     for a, c in zip(meta["universe"], ctxs) if not a.get("isDelisted")]
    except Exception:
        return []
    rows = _dedup_by_underlying(sorted((t for t in rows if t[1] >= min_vol_usd), key=lambda t: -t[1]))
    _PERP_CACHE[key] = rows
    return rows


def all_perp_symbols(min_vol_usd: float = 1_000_000) -> str:
    """Perp di tutti i dex sopra soglia come stringa CSV pronta per paper_trade.
    Floor 1M$/24h = coerente con fetch_universe (sotto, troppo illiquido per noi)."""
    return ",".join(s for s, _ in perp_universe(min_vol_usd))


# cache fetch per-run su disco: piu strategie nello stesso run riusano il fetch di
# uno stesso perp (chiave = symbol + ora UTC), cosi 295 perp si scaricano 1 volta
# sola invece di N×strategie → runtime sotto il timeout CI.
import pickle  # noqa: E402
import tempfile  # noqa: E402

_LIVE_CACHE_DIR = Path(tempfile.gettempdir()) / "luxai_live_cache"


def fetch_live_cached(symbol: str, lookback_h: int = 1000) -> dict:
    hr = int(time.time() // 3600)
    safe = symbol.replace(":", "_").replace("/", "_")
    fp = _LIVE_CACHE_DIR / f"{safe}.{hr}.pkl"
    if fp.exists():
        try:
            return pickle.loads(fp.read_bytes())
        except Exception:
            pass
    data = fetch_live(symbol, lookback_h)
    try:
        _LIVE_CACHE_DIR.mkdir(exist_ok=True)
        fp.write_bytes(pickle.dumps(data))
    except Exception:
        pass
    return data


def fetch_live(symbol: str, lookback_h: int = 1000) -> dict:
    """Candele 1h chiuse + funding da HYPERLIQUID — fonte UNICA. Niente Binance:
    geo-blocca i runner cloud US e ogni tanto restituisce dati corrotti che
    facevano crashare il run intero. Stesso formato del backtest. xyz_* (vecchie
    posizioni commodity, solo in uscita) → yfinance, l'unica fonte per quei nomi.
    HL non espone taker flow → il segnale taker_flow degrada a neutro (nessuna
    strategia attiva lo usa)."""
    if symbol.startswith("xyz_"):
        return _fetch_yf(symbol)
    return _fetch_hl(symbol, lookback_h)   # crypto core + HIP-3 (xyz:/builder-dex): tutto da HL


HL_INFO = "https://api.hyperliquid.xyz/info"


def atomic_write_text(path, text: str) -> None:
    """Scrive un file di testo atomicamente: prima su un temporaneo nello STESSO
    direttorio, poi os.replace (atomico su POSIX/Windows sullo stesso filesystem).

    Elimina le race condition in cui un lettore — la dashboard che legge
    paper/state.json o paper/backtests.json mentre un paper runner o il backtest
    report lo stanno riscrivendo — vede un file troncato a meta scrittura e lo
    interpreta come JSON invalido (sintomo: backtest/posizioni che a volte
    spariscono dalla dashboard). Lascia sempre o il vecchio contenuto o il nuovo,
    mai uno stato intermedio."""
    import os as _os
    import tempfile as _tf
    from pathlib import Path as _Path
    p = _Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = _tf.mkstemp(dir=p.parent, prefix=p.name + ".", suffix=".tmp")
    try:
        with _os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        _os.replace(tmp, p)
    except BaseException:
        try:
            _os.unlink(tmp)
        except OSError:
            pass
        raise


def _fetch_hl(symbol: str, lookback_h: int) -> dict:
    """Hyperliquid public info API: candele + funding. Niente taker flow
    (il segnale taker_flow resta neutro — degradazione esplicita, non errore)."""
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - min(lookback_h, 5000) * 3_600_000
    kl = requests.post(HL_INFO, json={"type": "candleSnapshot", "req": {
        "coin": symbol, "interval": "1h", "startTime": start_ms, "endTime": end_ms}},
        timeout=30).json()
    if not isinstance(kl, list) or not kl:   # risposta vuota/errore → errore pulito, il chiamante salta il simbolo
        raise RuntimeError(f"HL: candele assenti per {symbol}")
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
