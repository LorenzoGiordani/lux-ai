"""Exchange simulato per backtest su candele 1h (perps Hyperliquid).

Modello: una posizione per asset, esposizione target ∈ [-max_lev, +max_lev]
come frazione dell'equity. Fill all'open della candela successiva (no lookahead),
fee taker + slippage su ogni variazione, funding orario sulle posizioni aperte,
liquidazione mark-to-market su account equity (con MMR) oppure approssimazione
legacy 1/leva, stop-loss opzionale per posizione.

Limiti noti: nessuno di rilevante. Lo slippage è fisso (legacy) di default, ma
supporta un modello di market impact square-root (Almgren 2005) opt-in via
`impact_k`: slip_eff = base + k·σ·√(Q/V) con σ e V entrambi orari (orizzonte
coerente). Additivo (mai sotto il base), anti-lookahead (ADV/σ su dati passati).
Il funding è storico se si passa `funding_hist` (colonne ts, rate); in assenza
ricade sulla costante legacy. La liquidazione è mark-to-market su account equity
se si passa `maintenance_margin_frac` (MMR); in assenza ricade sull'approssimazione
legacy (soglia 1/leva fissa sull'entry).
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from backtest.risk import open_levels, step_exit

HL_TAKER_FEE = 0.00045          # tier base Hyperliquid
DEFAULT_SLIPPAGE = 0.0002       # 2 bps
DEFAULT_FUNDING_HOURLY = 0.0000125  # ≈0.01%/8h, tipico regime neutro (fallback)


def _funding_rate_lookup(candles: pd.DataFrame, funding_hist,
                         default_hourly: float) -> np.ndarray:
    """Tasso di funding orario allineato barra-per-barra alle candele.

    funding_hist: colonne [ts, rate], rate = tasso di settlement (Binance ~ogni
    8h). Lo si proietta sulla griglia oraria delle candele con merge_asof
    (last-known rate, direction backward) e si converte in tasso orario
    dividendo per lo step orario inferito dai ts. Se funding_hist manca o è
    vuoto, torna la costante default_hourly (behavior legacy)."""
    n = len(candles)
    if funding_hist is None or len(funding_hist) == 0 or "rate" not in funding_hist.columns:
        return np.full(n, default_hourly)
    fr = funding_hist[["ts", "rate"]].dropna().sort_values("ts").reset_index(drop=True)
    if len(fr) >= 2:
        span_s = (fr["ts"].iloc[-1] - fr["ts"].iloc[0]).total_seconds()
        step_h = max(round(span_s / 3600 / (len(fr) - 1)), 1)
    else:
        step_h = 8
    fr = fr.assign(rate_h=fr["rate"] / step_h)
    order = candles[["ts"]].reset_index().rename(columns={"index": "_order"})
    m = pd.merge_asof(order.sort_values("ts"), fr[["ts", "rate_h"]],
                      on="ts", direction="backward")
    out = m.sort_values("_order")["rate_h"].to_numpy(dtype=float)
    return np.where(np.isfinite(out), out, default_hourly)


def _liquidity_arrays(df: pd.DataFrame, window_h: int) -> tuple[np.ndarray, np.ndarray]:
    """ADV (USD/ora) e volatilità oraria per barra, anti-lookahead: rolling su
    dati ≤ i (la decisione al bar i usa la candela chiusa di i, fill a i+1).
    volume è in valuta base → moltiplico per close per avere il notionale USD.
    σ oraria (NON scalata a giornaliera): deve essere coerente col V orario
    nella legge square-root, altrimenti l'impact viene gonfiato di √24."""
    w = max(2, window_h)
    vol_usd = df["volume"].astype(float) * df["close"].astype(float)
    adv = vol_usd.rolling(w, min_periods=max(2, w // 4)).mean().to_numpy(dtype=float)
    rets = np.log(df["close"].astype(float)).diff()
    sigma_h = rets.rolling(w, min_periods=max(2, w // 4)).std().to_numpy(dtype=float)
    return adv, sigma_h


@dataclass
class Backtest:
    candles: pd.DataFrame                      # ts, open, high, low, close, volume
    fee: float = HL_TAKER_FEE
    slippage: float = DEFAULT_SLIPPAGE                 # base slippage (floor, sempre applicato)
    funding_hourly: float = DEFAULT_FUNDING_HOURLY   # fallback se funding_hist assente
    funding_hist: object = None                       # pd.DataFrame [ts, rate] storico reale
    impact_k: object = None                           # coeff. square-root (None = slippage fisso legacy)
    impact_window_h: int = 24                         # finestra rolling per ADV/σ
    maintenance_margin_frac: object = None            # MMR (None = liquidazione legacy 1/leva)
    max_leverage: float = 3.0
    start_equity: float = 10_000.0

    equity_curve: list = field(default_factory=list)
    trades: list = field(default_factory=list)

    def _effective_slippage(self, i: int, notional_usd: float) -> float:
        """Slippage effettivo per un ordine di `notional_usd` alla barra i.
        Modello square-root (Almgren 2005): slip = base + k·σ·√(partecipazione),
        con σ e V entrambi orari (orizzonte coerente). Additivo (≥ base, non
        lusinga mai), partecipazione clampata a 1 (asset illiquidi → impact
        saturato invece che esplodere). impact_k None → base."""
        if not self.impact_k:
            return self.slippage
        adv = self._adv_usd[i] if self._adv_usd is not None else 0.0
        sig = self._sigma_h[i] if self._sigma_h is not None else 0.0
        if not np.isfinite(adv) or adv <= 0 or not np.isfinite(sig) or sig <= 0:
            return self.slippage
        participation = min(1.0, notional_usd / adv)
        return self.slippage + float(self.impact_k) * sig * np.sqrt(participation)

    def run(self, strategy) -> pd.DataFrame:
        """strategy(history: df ≤ t) -> esposizione target. Ritorna equity curve.
        Uscita (stop/partial/target/trailing) delegata a backtest.risk.step_exit:
        unica fonte condivisa col paper engine."""
        df = self.candles.reset_index(drop=True)
        fund_rate = _funding_rate_lookup(df, self.funding_hist, self.funding_hourly)
        if self.impact_k:
            self._adv_usd, self._sigma_h = _liquidity_arrays(df, self.impact_window_h)
        else:
            self._adv_usd = self._sigma_h = None
        equity = self.start_equity
        pos = None  # dict da risk.open_levels + {exposure, size_usd}, oppure None

        for i in range(1, len(df)):
            row = df.iloc[i]

            # 1. gestione posizione sulla candela corrente
            if pos is not None:
                sign = pos["sign"]
                remaining = pos["remaining"]
                # liquidazione: mark-to-market su account equity se MMR attivo,
                # altrimenti approssimazione legacy (soglia 1/leva fissa sull'entry).
                # Il check MTM cattura funding accumulato e P&L realizzato da
                # partial (equity e' gia' aggiornata dalle barre precedenti),
                # come i veri exchange in regime cross-margin.
                if self.maintenance_margin_frac:
                    worst_px = row.low if sign > 0 else row.high
                    mmr = self.maintenance_margin_frac * pos["size_usd"] * remaining
                    unreal = pos["size_usd"] * remaining * (worst_px / pos["entry_px"] - 1) * sign
                    if equity + unreal <= mmr:
                        equity_before = equity
                        # liquidazione standard: equity si ferma al margine di
                        # mantenimento residuo (clamp difensivo se gia' in default)
                        equity = min(equity_before, mmr) if equity_before >= mmr else max(0.0, equity + unreal)
                        self._log_trade(pos, worst_px, remaining, row.ts, "liquidated",
                                        pnl_override=equity - equity_before)
                        pos = None
                if pos is not None:
                    lev = abs(pos["exposure"])
                    liq_px = pos["entry_px"] * (1 - sign / lev)
                    if (row.low <= liq_px) if sign > 0 else (row.high >= liq_px):
                        equity -= pos["size_usd"] * pos["remaining"] / lev  # margine residuo perso
                        self._log_trade(pos, liq_px, pos["remaining"], row.ts, "liquidated")
                        pos = None
                if pos is not None:
                    slip = self._effective_slippage(i, pos["size_usd"] * pos["remaining"])
                    for frac, px, reason in step_exit(pos, row.high, row.low, slip):
                        equity += pos["size_usd"] * frac * (px / pos["entry_px"] - 1) * sign
                        equity -= pos["size_usd"] * frac * self.fee
                        self._log_trade(pos, px, frac, row.ts, reason)
                    if pos["remaining"] <= 1e-9:
                        pos = None
                    else:  # funding sul nozionale residuo (long paga se rate>0)
                        equity -= pos["size_usd"] * pos["remaining"] * fund_rate[i] * sign

            if equity <= 0:
                equity = 0.0
                self.equity_curve.append((row.ts, 0.0))
                break

            # 2. equity mark-to-market per la curva
            mtm = equity
            if pos is not None:
                mtm += pos["size_usd"] * pos["remaining"] * (row.close / pos["entry_px"] - 1) * pos["sign"]
            self.equity_curve.append((row.ts, mtm))

            # 3. decisione della strategia su dati ≤ t, fill all'open di t+1
            if i + 1 >= len(df):
                break
            out = strategy(df.iloc[: i + 1])
            stop_pct, atrp, exit_cfg = out.get("stop_pct"), out.get("atr_pct"), out.get("exit_cfg", {})
            lev_cap = float(exit_cfg.get("max_leverage", self.max_leverage))
            target = float(np.clip(out["exposure"], -lev_cap, lev_cap))
            cur_exp = pos["exposure"] if pos is not None else 0.0
            if target != cur_exp:
                next_open = df.iloc[i + 1].open
                # chiudi posizione esistente (residuo)
                if pos is not None:
                    slip = self._effective_slippage(i, pos["size_usd"] * pos["remaining"])
                    px = next_open * (1 - slip if pos["sign"] > 0 else 1 + slip)
                    equity += pos["size_usd"] * pos["remaining"] * (px / pos["entry_px"] - 1) * pos["sign"]
                    equity -= pos["size_usd"] * pos["remaining"] * self.fee
                    self._log_trade(pos, px, pos["remaining"], df.iloc[i + 1].ts, "closed")
                    pos = None
                # apri nuova
                if target != 0.0 and equity > 0 and stop_pct:
                    sign = 1 if target > 0 else -1
                    size = abs(target) * equity
                    slip = self._effective_slippage(i, size)
                    px = next_open * (1 + slip if target > 0 else 1 - slip)
                    equity -= size * self.fee
                    pos = open_levels(exit_cfg, px, sign, stop_pct, atrp)
                    pos["exposure"], pos["size_usd"] = target, size

        return pd.DataFrame(self.equity_curve, columns=["ts", "equity"])

    def _log_trade(self, pos: dict, exit_px: float, frac: float, ts, reason: str,
                   pnl_override: float | None = None) -> None:
        pnl = pnl_override
        if pnl is None:
            pnl = pos["size_usd"] * frac * (exit_px / pos["entry_px"] - 1) * pos["sign"]
            if reason == "liquidated":
                pnl = -pos["size_usd"] * frac / abs(pos["exposure"])
        self.trades.append({
            "ts": ts, "exposure": pos["exposure"], "entry_px": pos["entry_px"],
            "exit_px": exit_px, "frac": frac, "pnl_usd": pnl, "reason": reason})
