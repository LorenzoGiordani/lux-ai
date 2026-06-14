"""Precompute forecast Kronos → cache parquet per simbolo (offline, anti-lookahead).

Kronos (shiyu-coder, AAAI 2026) è un foundation model OHLCV: a ogni passo decisione
t prende le ultime `context` candele (≤512) e prevede `horizon` candele future.
Salviamo ret_pred = close_previsto[t+horizon]/close[t]-1 indicizzato a ts=t.
Il backtest legge la cache via signals.kronos_forecast (niente torch nel backtest).

Pesante (inferenza CPU): si lancia separatamente, non nella pipeline 4h. Su Mac 8GB
usare il modello 'mini' e pochi simboli per volta.

Setup (una tantum):
  git clone https://github.com/shiyu-coder/Kronos .kronos
  .venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
  .venv/bin/pip install einops huggingface_hub safetensors

Uso:
  .venv/bin/python scripts/precompute_kronos.py --symbols BTC,ETH --model mini \
      --months 6 --step-h 24 --horizon-h 24 --context 360
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data/kronos"

MODELS = {  # nome → (repo tokenizer, repo modello, max_context)
    "mini":  ("NeoQuasar/Kronos-Tokenizer-2k",   "NeoQuasar/Kronos-mini",  512),
    "small": ("NeoQuasar/Kronos-Tokenizer-base", "NeoQuasar/Kronos-small", 512),
    "base":  ("NeoQuasar/Kronos-Tokenizer-base", "NeoQuasar/Kronos-base",  512),
}


def load_predictor(model_key: str, kronos_path: str):
    sys.path.insert(0, str(Path(kronos_path).resolve()))
    from model import Kronos, KronosTokenizer, KronosPredictor  # repo Kronos
    tok_repo, mdl_repo, max_ctx = MODELS[model_key]
    tokenizer = KronosTokenizer.from_pretrained(tok_repo)
    model = Kronos.from_pretrained(mdl_repo)
    return KronosPredictor(model, tokenizer, device="cpu", max_context=max_ctx)


def forecast_symbol(predictor, candles: pd.DataFrame, *, context: int, horizon: int,
                    step: int, sample_count: int) -> pd.DataFrame:
    """Walk-forward: a ogni `step` candele prevede `horizon` avanti usando solo il passato."""
    cols = ["open", "high", "low", "close", "volume"]
    c = candles.reset_index(drop=True)
    ts = pd.to_datetime(c["ts"])
    rows = []
    i = context
    while i < len(c) - 1:
        x_df = c.loc[i - context:i - 1, cols].reset_index(drop=True)
        x_ts = ts.loc[i - context:i - 1].reset_index(drop=True)
        # timestamp futuri: estende a passo 1h (dati orari)
        y_ts = pd.Series([ts.iloc[i - 1] + pd.Timedelta(hours=h) for h in range(1, horizon + 1)])
        try:
            pred = predictor.predict(df=x_df, x_timestamp=x_ts, y_timestamp=y_ts,
                                     pred_len=horizon, T=1.0, top_p=0.9, sample_count=sample_count)
            last_close = float(x_df["close"].iloc[-1])
            pred_close = float(pred["close"].iloc[-1])           # close previsto a t+horizon
            ret = pred_close / last_close - 1.0 if last_close else 0.0
            rows.append({"ts": ts.iloc[i - 1], "ret_pred": ret})
        except Exception as e:  # un punto fallito non ferma la serie
            print(f"    ! skip i={i}: {type(e).__name__}: {e}")
        i += step
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", required=True, help="es. BTC,ETH,xyz_GOLD")
    ap.add_argument("--model", default="mini", choices=list(MODELS))
    ap.add_argument("--months", type=int, default=6)
    ap.add_argument("--step-h", type=int, default=24, help="ogni quante candele rifare il forecast")
    ap.add_argument("--horizon-h", type=int, default=24, help="orizzonte di previsione (candele)")
    ap.add_argument("--context", type=int, default=360, help="candele di contesto (≤512)")
    ap.add_argument("--sample-count", type=int, default=1)
    ap.add_argument("--kronos-path", default=str(ROOT / ".kronos"))
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Carico Kronos-{args.model} (CPU)…")
    predictor = load_predictor(args.model, args.kronos_path)

    for sym in args.symbols.split(","):
        sym = sym.strip()
        cpath = ROOT / f"data/candles/{sym}.parquet"
        if not cpath.exists():
            print(f"  {sym}: candele assenti, salto")
            continue
        candles = pd.read_parquet(cpath).tail(args.months * 30 * 24).reset_index(drop=True)
        print(f"  {sym}: {len(candles)} candele → forecast ogni {args.step_h}h, orizzonte {args.horizon_h}h…")
        out = forecast_symbol(predictor, candles, context=args.context, horizon=args.horizon_h,
                              step=args.step_h, sample_count=args.sample_count)
        if out.empty:
            print(f"  {sym}: nessun forecast prodotto")
            continue
        out.to_parquet(OUT_DIR / f"{sym}.parquet", index=False)
        up = (out.ret_pred > 0).mean()
        print(f"  {sym}: {len(out)} forecast salvati ({up:.0%} rialzisti) → data/kronos/{sym}.parquet")


if __name__ == "__main__":
    main()
