"""Executor Hyperliquid testnet (M4) — porta una strategia validata a trading reale
su testnet con guardrail DETERMINISTICI nel codice. DRY-RUN di default: senza chiave
API wallet simula gli ordini e li logga, nessun ordine reale parte.

Guardrail hard (non negoziabili — strato 1 del risk management):
- leva <= max_leverage dello spec (clamp + update_leverage isolated per asset)
- stop-loss OBBLIGATORIO: ogni entrata accompagnata da un trigger SL reduce-only;
  se il SL non si piazza, la posizione viene chiusa subito (mai posizione nuda)
- size dall'exposure dello spec (min(leva, risk_pct/stop_pct)), mai oltre
- chiusure sempre reduce_only
- l'API wallet ha permessi SOLO trading (mai prelievi/trasferimenti) — vincolo lato HL

Rete: testnet SEMPRE, salvo HL_NETWORK=mainnet esplicito (safety). Env testnet:
  HL_ACCOUNT_ADDRESS  = address del main account (0x...)
  HL_API_SECRET       = chiave privata dell'API wallet approvato via approve_agent
Assenti → dry_run (simula + logga, nessuna connessione firmata).
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from hyperliquid.info import Info
from hyperliquid.utils import constants

ROOT = Path(__file__).resolve().parent.parent
JOURNAL = ROOT / "paper/executor.jsonl"


def _round_sz(sz: float, sz_decimals: int) -> float:
    return round(sz, sz_decimals)


def _round_px(px: float, sz_decimals: int) -> float:
    """Regola HL perps: max 5 cifre significative E max (6 - szDecimals) decimali."""
    if px == 0:
        return 0.0
    from math import floor, log10
    sig = 5 - 1 - floor(log10(abs(px)))            # decimali per 5 sig-fig
    return round(px, max(0, min(sig, 6 - sz_decimals)))


class Executor:
    def __init__(self, dry_run: bool | None = None):
        mainnet = os.getenv("HL_NETWORK", "").lower() == "mainnet"
        self.base_url = constants.MAINNET_API_URL if mainnet else constants.TESTNET_API_URL
        self.network = "mainnet" if mainnet else "testnet"
        self.info = Info(self.base_url, skip_ws=True)
        self._meta = {a["name"]: a for a in self.info.meta()["universe"]}

        addr = os.getenv("HL_ACCOUNT_ADDRESS")
        secret = os.getenv("HL_API_SECRET")
        self.has_key = bool(addr and secret)
        self.dry_run = (not self.has_key) if dry_run is None else dry_run
        self.address = addr
        self.exchange = None
        if self.has_key and not self.dry_run:
            from eth_account import Account
            from hyperliquid.exchange import Exchange
            wallet = Account.from_key(secret)
            self.exchange = Exchange(wallet, self.base_url, account_address=addr)

    def log(self, event: dict) -> None:
        event["logged_at"] = datetime.now(timezone.utc).isoformat()
        event["network"] = self.network
        event["dry_run"] = self.dry_run
        JOURNAL.parent.mkdir(parents=True, exist_ok=True)
        with JOURNAL.open("a") as f:
            f.write(json.dumps(event, default=str) + "\n")

    def mid(self, coin: str) -> float:
        return float(self.info.all_mids()[coin])

    def positions(self) -> dict:
        """{coin: signed_size} delle posizioni aperte sul main account. Vuoto in dry_run senza address."""
        if not self.address:
            return {}
        st = self.info.user_state(self.address)
        out = {}
        for p in st.get("assetPositions", []):
            pos = p["position"]
            szi = float(pos["szi"])
            if szi != 0:
                out[pos["coin"]] = szi
        return out

    def open_position(self, coin: str, is_buy: bool, size_usd: float, entry_px: float,
                      stop_px: float, leverage: int) -> dict:
        """Apre a mercato + piazza SUBITO lo stop-loss trigger reduce-only. Guardrail hard."""
        a = self._meta.get(coin)
        if a is None:
            return self._reject(coin, f"asset {coin} fuori universo HL")
        max_lev = int(a.get("maxLeverage", leverage))
        lev = max(1, min(int(leverage), max_lev))                  # clamp leva
        szd = int(a["szDecimals"])
        sz = _round_sz(size_usd / entry_px, szd)
        stop_px = _round_px(stop_px, szd)
        if sz <= 0:
            return self._reject(coin, f"size nulla (size_usd={size_usd})")

        intent = {"type": "open", "coin": coin, "side": "buy" if is_buy else "sell",
                  "sz": sz, "size_usd": round(size_usd, 2), "entry_px": entry_px,
                  "stop_px": stop_px, "leverage": lev}
        if self.dry_run:
            self.log({**intent, "status": "dry_run"})
            return intent

        self.exchange.update_leverage(lev, coin, is_cross=False)    # isolated, leva capata
        o = self.exchange.market_open(coin, is_buy, sz)
        # stop-loss OBBLIGATORIO: trigger market, reduce_only, lato opposto
        sl_type = {"trigger": {"triggerPx": stop_px, "isMarket": True, "tpsl": "sl"}}
        sl = self.exchange.order(coin, not is_buy, sz, stop_px, sl_type, reduce_only=True)
        if not self._ok(sl):                                        # SL fallito → mai posizione nuda
            self.exchange.market_close(coin)
            return self._reject(coin, f"stop-loss non piazzato ({sl}) → chiusura immediata")
        self.log({**intent, "status": "filled", "order": o, "sl_order": sl})
        return intent

    def cancel_open_orders(self, coin: str) -> list:
        """Cancella i trigger reduce-only ancora appesi (SL/TP orfani) per coin.
        Su HL gli ordini trigger NON si auto-cancellano alla chiusura della posizione."""
        if self.dry_run or not self.address:
            return []
        cancels = [{"coin": o["coin"], "oid": o["oid"]}
                   for o in self.info.open_orders(self.address) if o["coin"] == coin]
        if cancels:
            self.exchange.bulk_cancel(cancels)
        return cancels

    def close_position(self, coin: str) -> dict:
        intent = {"type": "close", "coin": coin}
        if self.dry_run:
            self.log({**intent, "status": "dry_run"})
            return intent
        r = self.exchange.market_close(coin)
        canceled = self.cancel_open_orders(coin)  # rimuove SL/TP orfani dopo la chiusura
        self.log({**intent, "status": "closed", "order": r, "canceled": canceled})
        return intent

    def _reject(self, coin: str, reason: str) -> dict:
        ev = {"type": "reject", "coin": coin, "reason": reason}
        self.log(ev)
        return ev

    @staticmethod
    def _ok(resp) -> bool:
        try:
            return resp.get("status") == "ok"
        except AttributeError:
            return False
