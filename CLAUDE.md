# defi-ai-vault — istruzioni progetto

## Documentazione — SEMPRE aggiornata
A fine di ogni sessione di lavoro (o dopo ogni milestone): aggiorna README.md
(sezioni "Risultati finora", "Roadmap", tabella componenti se cambiata) e fai
`git push` su origin (repo privata GitHub). Il README è la documentazione
canonica dello stato; Obsidian resta per decisioni e knowledge.

## Regole progetto
- Paper trading only: MAI codice che muove fondi reali senza richiesta esplicita
- Blocco `risk` delle strategie: immutabile dall'LLM, hard limits in `scripts/decide.py`
- Niente indicatori lagging (SMA/RSI/MACD) — solo registry `backtest/signals.py`
- Selezione strategie SOLO su basket multi-asset (mean Sharpe), mai singolo asset
- Tesi falsificabile obbligatoria su ogni trade e strategia
- Nuove lezioni → `paper/lessons.jsonl` via `scripts/review.py --add`
- LLM backend: `claude -p` (piano Pro) o modalità --pack in sessione; MAI assumere ANTHROPIC_API_KEY (zshrc ha proxy DashScope scaduto — strippare env)
- Mac 8GB: niente processi residenti, dashboard statica, cron leggeri
