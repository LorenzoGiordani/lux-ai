"""Report event study: come reagisce ogni asset HL agli eventi news GDELT.

Uso: .venv/bin/python scripts/event_study.py [--min-events 5]
Output: stampa matrice ordinata per |t| + salva data/news/event_study.csv
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from backtest.events import ROOT, load_events, reaction_matrix


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-events", type=int, default=5)
    args = ap.parse_args()

    events = load_events()
    print(f"eventi: {len(events)} | per topic: "
          f"{events.groupby('topic').size().to_dict()}\n")

    symbols = sorted(p.stem for p in (ROOT / "data" / "candles").glob("*.parquet"))
    mx = reaction_matrix(symbols, events, min_events=args.min_events)
    if mx.empty:
        sys.exit("Matrice vuota — servono eventi e candele sovrapposti nel tempo")

    mx = mx.sort_values("t", key=abs, ascending=False)
    mx.to_csv(ROOT / "data" / "news" / "event_study.csv", index=False)

    pd.set_option("display.width", 160)
    fmt = mx.copy()
    for col in ("mean_ret", "abn_ret", "mean_abs_ret"):
        fmt[col] = (fmt[col] * 100).round(2)
    fmt["t"] = fmt["t"].round(2)
    fmt["tone_hit"] = fmt["tone_hit"].round(2)
    print(fmt.head(30).to_string(index=False))
    print(f"\n{len(mx)} righe → data/news/event_study.csv (ret in %)")
    sig = mx[mx["t"].abs() >= 2]
    print(f"reazioni con |t|≥2: {len(sig)}")


if __name__ == "__main__":
    main()
