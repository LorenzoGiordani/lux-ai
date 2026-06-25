"""Outer loop evolutivo — generazione 1: LLM propone mutazioni, harness valuta.

Uso: uv run scripts/evolve.py strategies/<parent>.yaml BTC,ETH,SOL [n | candidati.yaml]

Valutazione multi-asset: ranking su Sharpe medio del basket (selezione su
singolo asset = overfitting, lezione gen 1).

Terzo argomento file .yaml (multi-documento, separatore ---) → salta la chiamata
LLM e valuta quei candidati. Serve quando il generatore è una sessione Claude
Code interattiva (piano Pro) invece di `claude -p`.

Flusso: valuta parent → 1 chiamata Claude (N mutazioni in YAML) → validazione
hard (registry, blocco risk forzato uguale al parent) → backtest di ogni
candidato → leaderboard → salvataggio in strategies/generated/.

LLM via `claude -p` (headless Claude Code → coperto dal piano Pro, niente API
key). Env ANTHROPIC_* rimosso dal subprocess: ~/.zshrc punta a un proxy
DashScope scaduto che dirotterebbe la chiamata.
"""

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))
from backtest.engine import Backtest
from backtest.metrics import compute
from backtest.stats import deflated_sharpe, sharpe_moments
from backtest.signals import SIGNALS
from backtest.strategy import compile_strategy, load
from backtest.walkforward import evaluate

OUT_DIR = Path("strategies/generated")

SYSTEM = (
    "Sei un ricercatore quantitativo. Proponi mutazioni di una strategia di trading "
    "su perps Hyperliquid (candele 1h). Lavori SOLO con i segnali del registry. "
    "Ogni mutazione: tesi falsificabile aggiornata, motivazione in evolution.notes, "
    "diversità tra i candidati (non solo tweak di parametri — anche rule, direction, exit). "
    "Vietato toccare il blocco risk. Obiettivo: consistenza tra fold e regimi, non massimizzare "
    "il ritorno totale (overfitting = morte). Penalizza la complessità: meno segnali se possibile. "
    'Rispondi SOLO con JSON valido: {"candidates": [{"yaml": "<strategia YAML completa>"}, ...]} '
    "— nessun testo fuori dal JSON, niente markdown fence."
)

REGISTRY_DOC = """Segnali disponibili (REGISTRY CHIUSO — solo questi, solo questi params):
- funding_percentile(lookback_h=168, extreme_pct=90): +1 funding a estremo positivo (crowding long), -1 estremo negativo
- range_breakout(range_h=48, volume_confirm_mult=2.0): +1 rottura max range con volume, -1 rottura min
- taker_flow(lookback_h=24, threshold=0.06): +1 aggressori in acquisto, -1 in vendita
- vol_compression(lookback_h=48, pct=20): +1 volatilità compressa (setup pre-espansione), mai -1
- tsmom(short_h=168, long_h=720): time-series momentum, +1/-1 se ritorni concordi su entrambi gli orizzonti (universale, solo close)
- vwap_zscore(lookback_h=168, z=2.0): +1/-1 prezzo esteso oltre z sigma dal VWAP rolling (follow o fade a scelta della strategia)
- volume_surge(lookback_h=168, pct=90): +1 volume nel percentile alto (conferma partecipazione), mai -1
NB: funding_percentile e taker_flow esistono SOLO per crypto; su oro/petrolio/stock usare i segnali OHLCV-universali.

entry.rule: nomi segnale composti con AND/OR (es. "vol_compression AND taker_flow").
entry.direction: signal_vote | follow:<segnale> | contrarian:<segnale> | with_breakout | contrarian_funding"""

EXIT_DOC = """Knob di uscita mutabili (blocco `exit`) — esplorali, l'harness misura cosa vince:
- stop_pct (obbligatorio): stop % fisso, fallback se ATR non calcolabile.
- stop_atr_mult (opz): stop = k*ATR% → adattivo alla volatilità. Tipico 2-3. Assente ⇒ stop fisso.
  NB: l'ATR già normalizza la vol fra asset; NON stringere k per asset poco volatili (raddoppia il noise-stop).
- atr_period (opz, default 14).
- target_r: multipli del rischio. ATTENZIONE: RR≥3 colpisce raramente il TP; RR 1.5-2 ha hit-rate molto più alto
  ma su trend lenti (tsmom) un RR alto può rendere di più lasciando correre i winner — verifica, non assumere.
- time_stop_h: ore max in posizione.
- partial (opz): {tp1_r, tp1_frac, trail_atr_mult} = scaling out + trailing. Aiuta su strategie veloci/mean-revert;
  su trend lenti TENDE A FRAMMENTARE i trend pagando fee → spesso peggiora. Usalo con criterio, non di default.
- by_class (opz): override per asset class {crypto, stock}. HIP-3 xyz_* = stock. Es. leva maggiore su stock low-vol.
  La sizing è vol-target (exposure=risk%/stop%): stop più stretto ⇒ più leva, fino al cap."""

def ask_claude(prompt: str) -> dict:
    """Headless Claude Code (`claude -p`) — usa il piano Pro, non l'API a consumo.
    Fallback opencode-go/glm-5.2 se claude fallisce (quota/CLI)."""
    import os
    import sys
    from scripts.decide import _ask_opencode
    env = {k: v for k, v in os.environ.items() if not k.startswith("ANTHROPIC_")}
    try:
        r = subprocess.run(
            ["claude", "-p", "--output-format", "json", "--append-system-prompt", SYSTEM],
            input=prompt, capture_output=True, text=True, timeout=600, env=env,
        )
        if r.returncode != 0:
            raise RuntimeError(f"claude -p fallito: {r.stderr[:500]}")
        result = json.loads(r.stdout)["result"].strip()
        result = result.split("\n", 1)[1].rsplit("```", 1)[0] if result.startswith("```") else result
        return json.loads(result)
    except RuntimeError as e:
        print(f"[fallback] claude fallito ({str(e)[:140]}) → opencode glm-5.2", file=sys.stderr)
        return _ask_opencode(prompt, as_json=True, system=SYSTEM)


def eval_spec(spec: dict, data: dict) -> tuple[dict, pd.Series]:
    strat, _ = compile_strategy(spec, data)
    _impact = os.environ.get("EVOLVE_IMPACT_K")  # opt-in: market impact square-root
    impact_k = float(_impact) if _impact else None
    _mmr = os.environ.get("EVOLVE_MMR")           # opt-in: liquidazione mark-to-market
    mmr = float(_mmr) if _mmr else None
    bt = Backtest(data["candles"], max_leverage=spec["risk"]["max_leverage"],
                  funding_hist=data.get("funding"), impact_k=impact_k,
                  maintenance_margin_frac=mmr)
    equity = bt.run(strat)
    m = compute(equity, bt.trades)
    ev = evaluate(equity, data["candles"])
    exits = pd.Series([t["reason"] for t in bt.trades]).value_counts().to_dict() if bt.trades else {}
    res = {"metrics": m, "regimes": ev["regimes"], "consistency": ev["consistency"], "exits": exits}
    rets = equity.set_index("ts").equity.pct_change().dropna()
    return json.loads(json.dumps(res, default=float)), rets  # json: via i tipi numpy


def eval_basket(spec: dict, datasets: dict) -> dict:
    """Valuta su tutti i simboli; aggregato = media delle metriche chiave.
    'basket_rets' (ritorni orari medi cross-asset, non serializzato) serve al DSR."""
    evals = {sym: eval_spec(spec, d) for sym, d in datasets.items()}
    per_symbol = {sym: r for sym, (r, _) in evals.items()}
    basket_rets = pd.concat([rets for _, rets in evals.values()], axis=1).mean(axis=1).dropna()
    ms = [r["metrics"] for r in per_symbol.values()]
    folds_pos = sum(int(r["consistency"].split("/")[0]) for r in per_symbol.values())
    folds_tot = sum(int(r["consistency"].split("/")[1].split()[0]) for r in per_symbol.values())
    agg = {
        "mean_sharpe": sum(m["sharpe"] for m in ms) / len(ms),
        "mean_return": sum(m["total_return"] for m in ms) / len(ms),
        "worst_drawdown": min(m["max_drawdown"] for m in ms),
        "total_trades": sum(m["n_trades"] for m in ms),
        "folds": f"{folds_pos}/{folds_tot}",
        "positive_symbols": f"{sum(1 for m in ms if m['total_return'] > 0)}/{len(ms)}",
    }
    return {"aggregate": agg, "per_symbol": per_symbol, "basket_rets": basket_rets}


def complexity_penalty(spec: dict) -> float:
    """Penalità complessità (regola 10): n_segnali + n_parametri totali.
    Ogni segnale extra e ogni parametro extra aumenta il rischio di overfitting
    (più gradi di libertà = più facile fit-trap nel backtest). Ritorna un valore
    non negativo da sottrarre allo Sharpe nel leaderboard. Base: 1 segnale = 0,
    ogni extra = 0.02; ogni parametro = 0.005. Conservativa, non blocca."""
    signals = spec.get("signals", [])
    n_signals = max(0, len(signals) - 1)  # primo segnale gratis (base legittima)
    n_params = 0
    for s in signals:
        p = s.get("params", {})
        n_params += sum(1 for v in p.values() if isinstance(v, (int, float)))
    # by_class exit params contano (override per-asset-class = più gradi)
    by_class = spec.get("exit", {}).get("by_class", {})
    for cls, cfg in by_class.items():
        if isinstance(cfg, dict):
            n_params += sum(1 for v in cfg.values() if isinstance(v, (int, float)))
    return round(n_signals * 0.02 + n_params * 0.005, 3)


def validate(spec: dict, parent: dict, idx: int) -> dict:
    for s in spec["signals"]:
        if s["name"] not in SIGNALS:
            raise ValueError(f"segnale fuori registry: {s['name']}")
    declared = {s["name"] for s in spec["signals"]}
    for token in spec["entry"]["rule"].replace(" OR ", " AND ").split(" AND "):
        if token.strip() not in declared:
            raise ValueError(f"rule usa segnale non dichiarato: {token}")
    veto = spec["entry"].get("veto") or []
    for v in (veto if isinstance(veto, list) else veto.split(",")):
        if v.strip() and v.strip() not in declared:
            raise ValueError(f"veto usa segnale non dichiarato: {v}")
    if not (0.3 <= float(spec["exit"]["stop_pct"]) <= 15):
        raise ValueError(f"stop_pct fuori range: {spec['exit']['stop_pct']}")
    # blocco risk: non negoziabile, si forza quello del parent qualunque cosa dica l'LLM
    spec["risk"] = parent["risk"]
    spec["parent"] = parent["id"]
    spec["status"] = "candidate"
    spec["created"] = str(date.today())
    spec["id"] = f"{parent['id'].rsplit('-v', 1)[0]}-g{idx}"
    return spec


def load_data(symbol: str, months: int) -> dict:
    candles = pd.read_parquet(f"data/candles/{symbol}.parquet").tail(months * 30 * 24).reset_index(drop=True)
    data = {"candles": candles, "symbol": symbol}
    for kind in ("funding", "flow"):
        p = Path(f"data/{kind}/{symbol}.parquet")
        data[kind] = pd.read_parquet(p) if p.exists() else None
    ev = Path("data/news/gdelt_events.parquet")
    data["news_events"] = pd.read_parquet(ev) if ev.exists() else None
    cot = Path(f"data/cot/{symbol}.parquet")
    data["cot"] = pd.read_parquet(cot) if cot.exists() else None
    return data


def main() -> None:
    parent_path, symbols = sys.argv[1], sys.argv[2].split(",")
    arg3 = sys.argv[3] if len(sys.argv) > 3 else "4"
    candidates_file = arg3 if arg3.endswith((".yaml", ".yml")) else None
    n = 4 if candidates_file else int(arg3)
    months = 6

    datasets = {s: load_data(s, months) for s in symbols}
    parent = load(parent_path)
    parent_eval = eval_basket(parent, datasets)
    pa = parent_eval["aggregate"]
    print(f"parent {parent['id']} su {','.join(symbols)}: mean sharpe {pa['mean_sharpe']:.2f}, "
          f"mean ret {pa['mean_return']:+.2%}, fold {pa['folds']}, asset positivi {pa['positive_symbols']}")

    if candidates_file:
        specs = [d for d in yaml.safe_load_all(Path(candidates_file).read_text()) if d]
    else:
        compact = {s: r["metrics"] for s, r in parent_eval["per_symbol"].items()}
        prompt = f"""{REGISTRY_DOC}

{EXIT_DOC}

PARENT (YAML):
{Path(parent_path).read_text()}

RISULTATI PARENT su basket {','.join(symbols)}, {months} mesi (fee/slippage/funding inclusi):
aggregato: {json.dumps(pa)}
per asset: {json.dumps(compact, default=str)}

Proponi {n} mutazioni in YAML (schema identico al parent). Obiettivo: robustezza sul basket, non picchi su singolo asset."""
        specs = [yaml.safe_load(c["yaml"]) for c in ask_claude(prompt)["candidates"]]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # K per il DSR: tutti i candidati storici della cartella + questo run + parent
    n_prior = len([f for f in OUT_DIR.glob("*.yaml") if "candidates" not in f.name])
    rows = []
    for i, cand in enumerate(specs, 1):
        try:
            spec = validate(cand, parent, i)
            res = eval_basket(spec, datasets)
            rets = res.pop("basket_rets")  # non serializzabile, serve solo al DSR
            spec["backtest"] = {f"basket_{months}m": res}
            rows.append((spec, res["aggregate"], rets))
        except Exception as e:
            print(f"candidato {i} scartato: {e}", file=sys.stderr)

    # gate anti-overfitting: DSR contro il max Sharpe atteso dal rumore su K prove
    trial_srs = [sharpe_moments(r)["sr"] for _, _, r in rows]
    k_trials = n_prior + len(rows) + 1
    for spec, agg, rets in rows:
        d = deflated_sharpe(rets, k_trials, trial_srs)
        agg["dsr"] = round(d["dsr"], 3)
        agg["dsr_sr0_ann"] = d["sr0_ann"]
        agg["complexity_penalty"] = complexity_penalty(spec)
        agg["adj_sharpe"] = round(agg["mean_sharpe"] - agg["complexity_penalty"], 3)
        out = OUT_DIR / f"{spec['id']}.yaml"
        out.write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True))

    # leaderboard per adj_sharpe (mean_sharpe - complexity_penalty): penalizza
    # candidati complessi che overfittano più facilmente (regola 10)
    rows.sort(key=lambda r: r[1]["adj_sharpe"], reverse=True)
    print(f"\nLeaderboard (vs parent mean sharpe {pa['mean_sharpe']:.2f}, mean ret {pa['mean_return']:+.2%}; "
          f"gate: DSR ≥ 0.95 su K={k_trials} prove; ordine per adj_sharpe = mean_sharpe - complexity_penalty):")
    for spec, a, _ in rows:
        gate = "✓ GATE" if a["dsr"] >= 0.95 else "✗"
        print(f"  {spec['id']:<38} adj {a['adj_sharpe']:6.2f} (sharpe {a['mean_sharpe']:5.2f} - pen {a['complexity_penalty']:4.2f}) "
              f"| DSR {a['dsr']:.2f} {gate} | ret {a['mean_return']:+7.2%} | worstDD {a['worst_drawdown']:7.2%} | "
              f"trades {a['total_trades']:>3} | fold {a['folds']} | asset+ {a['positive_symbols']}")



if __name__ == "__main__":
    main()
