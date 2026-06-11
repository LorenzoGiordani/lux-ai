"""Outer loop evolutivo — generazione 1: LLM propone mutazioni, harness valuta.

Uso: uv run scripts/evolve.py strategies/<parent>.yaml BTC [n_candidati]

Flusso: valuta parent → 1 chiamata Claude (N mutazioni in YAML) → validazione
hard (registry, blocco risk forzato uguale al parent) → backtest di ogni
candidato → leaderboard → salvataggio in strategies/generated/.

Costo: 1 chiamata API per generazione. Usage stampato a fine run.
"""

import json
import sys
from datetime import date
from pathlib import Path

import anthropic
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))
from backtest.engine import Backtest
from backtest.metrics import buy_and_hold, compute
from backtest.signals import SIGNALS
from backtest.strategy import compile_strategy, load
from backtest.walkforward import evaluate

MODEL = "claude-opus-4-8"
OUT_DIR = Path("strategies/generated")

REGISTRY_DOC = """Segnali disponibili (REGISTRY CHIUSO — solo questi, solo questi params):
- funding_percentile(lookback_h=168, extreme_pct=90): +1 funding a estremo positivo (crowding long), -1 estremo negativo
- range_breakout(range_h=48, volume_confirm_mult=2.0): +1 rottura max range con volume, -1 rottura min
- taker_flow(lookback_h=24, threshold=0.06): +1 aggressori in acquisto, -1 in vendita
- vol_compression(lookback_h=48, pct=20): +1 volatilità compressa (setup pre-espansione), mai -1

entry.rule: nomi segnale composti con AND/OR (es. "vol_compression AND taker_flow").
entry.direction: signal_vote | follow:<segnale> | contrarian:<segnale> | with_breakout | contrarian_funding"""

SCHEMA = {
    "type": "object",
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "yaml": {"type": "string", "description": "Strategia completa in YAML, stesso schema del parent"},
                },
                "required": ["yaml"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["candidates"],
    "additionalProperties": False,
}


def eval_spec(spec: dict, data: dict) -> dict:
    strat, _ = compile_strategy(spec, data)
    bt = Backtest(data["candles"], max_leverage=spec["risk"]["max_leverage"])
    equity = bt.run(strat)
    m = compute(equity, bt.trades)
    ev = evaluate(equity, data["candles"])
    exits = pd.Series([t["reason"] for t in bt.trades]).value_counts().to_dict() if bt.trades else {}
    return {"metrics": m, "regimes": ev["regimes"], "consistency": ev["consistency"], "exits": exits}


def validate(spec: dict, parent: dict, idx: int) -> dict:
    for s in spec["signals"]:
        if s["name"] not in SIGNALS:
            raise ValueError(f"segnale fuori registry: {s['name']}")
    for token in spec["entry"]["rule"].replace(" OR ", " AND ").split(" AND "):
        if token.strip() not in {s["name"] for s in spec["signals"]}:
            raise ValueError(f"rule usa segnale non dichiarato: {token}")
    if not (0.3 <= float(spec["exit"]["stop_pct"]) <= 15):
        raise ValueError(f"stop_pct fuori range: {spec['exit']['stop_pct']}")
    # blocco risk: non negoziabile, si forza quello del parent qualunque cosa dica l'LLM
    spec["risk"] = parent["risk"]
    spec["parent"] = parent["id"]
    spec["status"] = "candidate"
    spec["created"] = str(date.today())
    spec["id"] = f"{parent['id'].rsplit('-v', 1)[0]}-g{idx}"
    return spec


def main() -> None:
    parent_path, symbol = sys.argv[1], sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    months = 6

    candles = pd.read_parquet(f"data/candles/{symbol}.parquet").tail(months * 30 * 24).reset_index(drop=True)
    data = {"candles": candles}
    for kind in ("funding", "flow"):
        p = Path(f"data/{kind}/{symbol}.parquet")
        data[kind] = pd.read_parquet(p) if p.exists() else None

    parent = load(parent_path)
    parent_eval = eval_spec(parent, data)
    bh = buy_and_hold(candles)
    print(f"parent {parent['id']}: ret {parent_eval['metrics']['total_return']:+.2%}, "
          f"sharpe {parent_eval['metrics']['sharpe']:.2f}, {parent_eval['consistency']}")

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        thinking={"type": "adaptive"},
        system=(
            "Sei un ricercatore quantitativo. Proponi mutazioni di una strategia di trading "
            "su perps Hyperliquid (candele 1h). Lavori SOLO con i segnali del registry. "
            "Ogni mutazione: tesi falsificabile aggiornata, motivazione in evolution.notes, "
            "diversità tra i candidati (non solo tweak di parametri — anche rule, direction, exit). "
            "Vietato toccare il blocco risk. Obiettivo: consistenza tra fold e regimi, non massimizzare "
            "il ritorno totale (overfitting = morte). Penalizza la complessità: meno segnali se possibile."
        ),
        messages=[{
            "role": "user",
            "content": f"""{REGISTRY_DOC}

PARENT (YAML):
{Path(parent_path).read_text()}

RISULTATI PARENT su {symbol}, {months} mesi (fee/slippage/funding inclusi):
{json.dumps(parent_eval, indent=1, default=str)}

Baseline buy-and-hold: ret {bh['total_return']:+.2%}, sharpe {bh['sharpe']:.2f}, maxDD {bh['max_drawdown']:.2%}

Proponi {n} mutazioni in YAML (schema identico al parent).""",
        }],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
    )

    text = next(b.text for b in response.content if b.type == "text")
    raw = json.loads(text)["candidates"]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, c in enumerate(raw, 1):
        try:
            spec = validate(yaml.safe_load(c["yaml"]), parent, i)
            res = eval_spec(spec, data)
            spec["backtest"] = {f"{symbol}_{months}m": res}
            out = OUT_DIR / f"{spec['id']}.yaml"
            out.write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True))
            rows.append((spec["id"], res, str(out)))
        except Exception as e:
            print(f"candidato {i} scartato: {e}", file=sys.stderr)

    rows.sort(key=lambda r: r[1]["metrics"]["sharpe"], reverse=True)
    print(f"\nLeaderboard generazione (vs parent sharpe {parent_eval['metrics']['sharpe']:.2f}):")
    for sid, res, path in rows:
        m = res["metrics"]
        print(f"  {sid:<40} ret {m['total_return']:+7.2%} | sharpe {m['sharpe']:6.2f} | "
              f"maxDD {m['max_drawdown']:7.2%} | trades {m['n_trades']:>3} | {res['consistency']}")

    u = response.usage
    print(f"\ncosto LLM: in {u.input_tokens} + out {u.output_tokens} token "
          f"(~${u.input_tokens * 5 / 1e6 + u.output_tokens * 25 / 1e6:.3f})")


if __name__ == "__main__":
    main()
