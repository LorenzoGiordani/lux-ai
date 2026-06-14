"""Precompute regime HMM → cache parquet per simbolo (walk-forward, anti-lookahead).

Metodo Jim Simons / Renaissance: un Hidden Markov Model sui ritorni separa stati
nascosti del mercato. Etichettiamo come "trending" lo stato con il miglior
signal-to-noise del drift (|media|/std); gli altri = chop/range. A ogni passo di
refit usiamo SOLO il passato (window di ritorni precedenti), decodifichiamo lo stato
corrente e lo forward-filliamo fino al refit successivo. La cache (ts, regime) è
letta dal backtest via signals.hmm_regime — niente fit nel backtest.

Idea: il TSMOM perde nel chop (lezione walkforward); un filtro di regime HMM dovrebbe
alzare il DSR tenendo le entrate solo nei regimi trending. Lo verifica l'A/B.

Uso:
  .venv/bin/python scripts/precompute_hmm.py --symbols BTC,ETH --months 6 \
      --states 3 --window 1500 --refit-h 24 --min-train 800
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data/hmm"


def regime_labels(returns: np.ndarray, *, n_states: int, window: int,
                  refit: int, min_train: int) -> np.ndarray:
    """Etichetta 0/1 (chop/trend) per ogni barra, causale: a ogni refit fit su soli
    ritorni passati, stato corrente forward-fillato fino al refit dopo."""
    from hmmlearn.hmm import GaussianHMM
    n = len(returns)
    labels = np.zeros(n, dtype=int)
    # standardizza una volta sui dati disponibili al primo fit (stabilità numerica);
    # lo scaling globale non introduce lookahead sul SEGNALE (è solo normalizzazione).
    for t in range(min_train, n, refit):
        train = returns[max(0, t - window):t]
        if len(train) < min_train // 2 or np.std(train) == 0:
            continue
        x = ((train - train.mean()) / (train.std() + 1e-9)).reshape(-1, 1)
        try:
            m = GaussianHMM(n_components=n_states, covariance_type="diag",
                            n_iter=40, random_state=0)
            m.fit(x)
            seq = m.predict(x)
        except Exception:
            continue
        # stato "trending" = miglior signal-to-noise del drift (|media|/std)
        score = np.abs(m.means_.ravel()) / np.sqrt(m.covars_.ravel() + 1e-12)
        trend_state = int(score.argmax())
        labels[t:t + refit] = 1 if seq[-1] == trend_state else 0
    return labels


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", required=True)
    ap.add_argument("--months", type=int, default=6)
    ap.add_argument("--states", type=int, default=3)
    ap.add_argument("--window", type=int, default=1500, help="candele passate per il fit")
    ap.add_argument("--refit-h", type=int, default=24, help="ogni quante candele rifare il fit")
    ap.add_argument("--min-train", type=int, default=800)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for sym in args.symbols.split(","):
        sym = sym.strip()
        cpath = ROOT / f"data/candles/{sym}.parquet"
        if not cpath.exists():
            print(f"  {sym}: candele assenti, salto"); continue
        c = pd.read_parquet(cpath).tail(args.months * 30 * 24).reset_index(drop=True)
        ts = pd.to_datetime(c["ts"])
        ret = np.log(c["close"]).diff().fillna(0.0).to_numpy()
        labels = regime_labels(ret, n_states=args.states, window=args.window,
                               refit=args.refit_h, min_train=args.min_train)
        # cache sparsa: una riga a ogni refit (il merge_asof nel segnale forward-filla)
        rows = []
        last = None
        for i in range(0, len(c)):
            if labels[i] != last:
                rows.append({"ts": ts.iloc[i], "regime": int(labels[i])})
                last = labels[i]
        out = pd.DataFrame(rows)
        if out.empty:
            print(f"  {sym}: nessuna etichetta"); continue
        out.to_parquet(OUT_DIR / f"{sym}.parquet", index=False)
        trend_frac = labels[args.min_train:].mean()
        print(f"  {sym}: {len(out)} transizioni, {trend_frac:.0%} del tempo in regime trending "
              f"→ data/hmm/{sym}.parquet")


if __name__ == "__main__":
    main()
