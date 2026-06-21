"""Exchange simulato per backtest su candele 1h (perps Hyperliquid).

Modello: una posizione per asset, esposizione target ∈ [-max_lev, +max_lev]
come frazione dell'equity. Fill all'open della candela successiva (no lookahead),
fee taker + slippage su ogni variazione, funding orario sulle posizioni aperte,
liquidazione approssimata (prezzo oltre 1/leva dall'entry → equity della posizione
azzerata), stop-loss opzionale per posizione.

Limiti noti (accettati per MVP): funding costante (non storico), slippage fisso
(no impatto da size), niente maintenance margin fine.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from backtest.risk import open_levels, step_exit

HL_TAKER_FEE = 0.00045          # tier base Hyperliquid
DEFAULT_SLIPPAGE = 0.0002       # 2 bps
DEFAULT_FUNDING_HOURLY = 0.0000125  # ≈0.01%/8h, tipico regime neutro


@dataclass
class Backtest:
    candles: pd.DataFrame                      # ts, open, high, low, close, volume
    fee: float = HL_TAKER_FEE
    slippage: float = DEFAULT_SLIPPAGE
    funding_hourly: float = DEFAULT_FUNDING_HOURLY
    max_leverage: float = 3.0
    start_equity: float = 10_000.0

    equity_curve: list = field(default_factory=list)
    trades: list = field(default_factory=list)

    def run(self, strategy) -> pd.DataFrame:
        """strategy(history: df ≤ t) -> esposizione target. Ritorna equity curve.
        Uscita (stop/partial/target/trailing) delegata a backtest.risk.step_exit:
        unica fonte condivisa col paper engine."""
        df = self.candles.reset_index(drop=True)
        equity = self.start_equity
        pos = None  # dict da risk.open_levels + {exposure, size_usd}, oppure None

        for i in range(1, len(df)):
            row = df.iloc[i]

            # 1. gestione posizione sulla candela corrente
            if pos is not None:
                sign = pos["sign"]
                lev = abs(pos["exposure"])
                # liquidazione approssimata: move avverso > 1/leva dall'entry
                liq_px = pos["entry_px"] * (1 - sign / lev)
                if (row.low <= liq_px) if sign > 0 else (row.high >= liq_px):
                    equity -= pos["size_usd"] * pos["remaining"] / lev  # margine residuo perso
                    self._log_trade(pos, liq_px, pos["remaining"], row.ts, "liquidated")
                    pos = None
                else:
                    for frac, px, reason in step_exit(pos, row.high, row.low, self.slippage):
                        equity += pos["size_usd"] * frac * (px / pos["entry_px"] - 1) * sign
                        equity -= pos["size_usd"] * frac * self.fee
                        self._log_trade(pos, px, frac, row.ts, reason)
                    if pos["remaining"] <= 1e-9:
                        pos = None
                    else:  # funding sul nozionale residuo (long paga se rate>0)
                        equity -= pos["size_usd"] * pos["remaining"] * self.funding_hourly * sign

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
                    px = next_open * (1 - self.slippage if pos["sign"] > 0 else 1 + self.slippage)
                    equity += pos["size_usd"] * pos["remaining"] * (px / pos["entry_px"] - 1) * pos["sign"]
                    equity -= pos["size_usd"] * pos["remaining"] * self.fee
                    self._log_trade(pos, px, pos["remaining"], df.iloc[i + 1].ts, "closed")
                    pos = None
                # apri nuova
                if target != 0.0 and equity > 0 and stop_pct:
                    sign = 1 if target > 0 else -1
                    px = next_open * (1 + self.slippage if target > 0 else 1 - self.slippage)
                    size = abs(target) * equity
                    equity -= size * self.fee
                    pos = open_levels(exit_cfg, px, sign, stop_pct, atrp)
                    pos["exposure"], pos["size_usd"] = target, size

        return pd.DataFrame(self.equity_curve, columns=["ts", "equity"])

    def _log_trade(self, pos: dict, exit_px: float, frac: float, ts, reason: str) -> None:
        pnl = pos["size_usd"] * frac * (exit_px / pos["entry_px"] - 1) * pos["sign"]
        if reason == "liquidated":
            pnl = -pos["size_usd"] * frac / abs(pos["exposure"])
        self.trades.append({
            "ts": ts, "exposure": pos["exposure"], "entry_px": pos["entry_px"],
            "exit_px": exit_px, "frac": frac, "pnl_usd": pnl, "reason": reason})
