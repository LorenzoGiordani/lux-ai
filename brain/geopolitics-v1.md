# geopolitics-v1

[[README|← Brain index]]

## Anagrafica

- **status**: challenger
- **created**: 2026-06-19

## Tesi

Layer LLM cross-asset gated sugli eventi geopolitici. news_event(geopolitics) — burst GDELT su war/sanctions/conflict/military — fa da TRIGGER: solo quando scoppia un catalizzatore il desk ragiona. L'edge non è il sentiment (tone falsificato come predittore, event study 2026-06-13, tone_hit 0.38<0.50) ma l'interpretazione del CANALE DI TRASMISSIONE: guerra/sanzioni → energia (oil, natgas), risk-off → safe-haven (gold) e deleveraging crypto. Il desk sceglie asset e direzione dal nesso causale, non dal segno del tono. Falsificata se: i trade gated-su-geopolitica NON battono il buy&hold cross-asset sullo stesso periodo → il catalizzatore non aggiunge edge sopra il drift.

## Note evoluzione

v1 — gate news_event(geopolitics) + desk LLM cross-asset. Prima strategia engine:desk. Possibili mutazioni: soglia min_z del burst, finestra max_age_h, universo (aggiungere indici/FX), default di exit.

## Performance (paper)

- equity: $10,000.00
- trade chiusi: 0 · win rate: 0%
- PnL totale: $0.00
- posizioni aperte ora: 0

[[lessons|Tutte le lezioni]] · [[timeline|Timeline]]
