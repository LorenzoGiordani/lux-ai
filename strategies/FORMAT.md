# Formato artefatto strategia

Una strategia è un file YAML versionato in `strategies/`. È l'unità su cui opera
il loop evolutivo: l'LLM la genera/muta, l'harness la valuta, il champion va in
paper trading e poi live. Mai logica di trading sepolta nei prompt.

Principi:
- **Tesi obbligatoria e falsificabile** — perché l'edge dovrebbe esistere. Senza tesi, no test.
- **Segnali da registry** — l'LLM compone e parametrizza segnali leading vetted
  (`backtest/signals.py`), non scrive codice arbitrario. Niente indicatori lagging.
- **Blocco `risk` immutabile** — fuori dalla portata dell'evoluzione, hard limit nel codice.
- **Lineage** — ogni mutazione punta al genitore: storia evolutiva ricostruibile (è anche il prodotto pubblico).
- **`backtest` lo scrive solo l'harness** — l'LLM non tocca i risultati.

## Schema con esempio

```yaml
id: funding-squeeze-breakout-v1
parent: null                      # id del genitore se mutazione
status: candidate                 # candidate | challenger | champion | retired
created: 2026-06-11
thesis: >
  Quando il funding è a un estremo (crowding) e il prezzo rompe un range
  multi-day con volume, lo squeeze del lato affollato alimenta il breakout.
  Falsificata se: il breakout con funding estremo non outperforma il
  breakout semplice su 6 mesi walk-forward.

universe:
  selection: top_liquidity        # filtro su data/universe.csv
  min_day_volume_usd: 1000000     # floor liquidita (sotto = troppo illiquido, noise-stop)
  max_assets: 10
  kinds: [perp]
  exclude: []                     # opz — nomi da escludere a mano (segnali senza edge ripetuto). Lista o CSV.

timeframe: 1h
decision_every_h: 4               # campionamento decisioni (costo LLM nel live)

signals:                          # nome → registry, params espliciti
  - name: funding_percentile     # posizionamento
    params: {lookback_h: 168, extreme_pct: 90}
  - name: range_breakout         # struttura prezzo
    params: {range_h: 48, volume_confirm_mult: 2.0}

entry:
  rule: funding_percentile AND range_breakout   # composizione booleana dei segnali
  direction: with_breakout        # with_breakout | contrarian_funding | signal_vote
  veto: news_event                # opz. — segnali-gate che SOSPENDONO nuove entrate
                                  #   quando attivi (filtro di rischio, non direzione).
                                  #   Devono essere dichiarati in `signals`. Lista o CSV.

exit:
  stop_pct: 2.5                   # fallback se ATR non calcolabile (obbligatorio)
  stop_atr_mult: 2.5              # opz — stop = k*ATR%: volatility-adaptive. Assente ⇒ stop fisso.
  atr_period: 14                  # periodo ATR
  target_r: 2.0                   # multipli del rischio. NB: RR alto (≥3) raramente colpisce il TP
  time_stop_h: 72                 # esci se la tesi non si realizza in tempo
  partial:                        # opz — scaling out: tp1_frac a tp1_r, BE-stop, traila il resto
    tp1_r: 1.0
    tp1_frac: 0.5
    trail_atr_mult: 3.0
  by_class:                       # opz — override per asset class (crypto | stock). HIP-3 xyz_* = stock.
    crypto: {stop_atr_mult: 2.5, target_r: 2.0}                   # alta vol: stop largo
    stock:  {stop_atr_mult: 1.5, target_r: 1.8, max_leverage: 4}  # bassa vol: stop stretto + leva alta

risk:                             # IMMUTABILE per l'evoluzione
  max_leverage: 2
  risk_per_trade_pct: 1.0         # % equity a rischio per trade
  max_concurrent_positions: 3

evolution:
  mutable: [signals, entry, exit, universe.max_assets, decision_every_h]
  notes: ""                       # l'LLM motiva qui ogni mutazione

backtest: {}                      # compilato dall'harness: metriche per periodo e regime
```

## Ciclo di vita

```
LLM genera/muta → candidate → harness (walk-forward, split per regime,
bootstrap) → sopravvive? → challenger (paper trading dati live) → batte il
champion con significatività? → champion → live. Altrimenti → retired (con
post-mortem nel journal — anche i fallimenti insegnano).
```

Anti-overfitting (non negoziabile): walk-forward sempre, mai promozione su
backtest solo (il paper trading è il gate), penalità per complessità (n. segnali
e parametri), deflated Sharpe quando i candidati testati diventano tanti.
