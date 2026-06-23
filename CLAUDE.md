# defi-ai-vault — istruzioni progetto

## Documentazione — SEMPRE aggiornata
A fine di ogni sessione di lavoro (o dopo ogni milestone): aggiorna README.md
(sezioni "Risultati finora", "Roadmap", tabella componenti se cambiata) e fai
`git push` su origin (repo privata GitHub). Il README è la documentazione
canonica dello stato; Obsidian resta per decisioni e knowledge.

## Regole progetto

### 1. LLM come giudice, non oracolo
L'LLM aggiunge valore sintetizzando contesto e giudicando rischio/correlazione,
NON prevedendo il prezzo. Event study e lezioni ripetute: forecast direzionale
LLM = niente alpha. Il gate sistematico (segnali registry) è l'edge primario;
l'LLM è strato di giudizio avverso sopra il gate. Mai usare l'LLM come generatore
di segnale price-predictor.

### 2. Paper trading only
Mai codice che muove fondi reali senza richiesta esplicita. `execute_testnet.py`
esiste ma non è in nessun workflow. Separazione paper/live = gate più importante.

### 3. Risk management two-tier
Due sistemi di limiti, deliberately separati per tipo di strategia:
- **Desk LLM** (`agents-v1`, `claude-strategy-v1`, `glm-regime-confluence-v1`,
  `geopolitics-v1`): `HARD_LIMITS` in `scripts/decide.py` (leva ≤2, risk ≤1%,
  max 3 posizioni). Enforced da `hard_check()` — insindacabile dall'LLM.
- **Strategie meccaniche** (tsmom, xsmom, funding-squeeze, ecc.): blocco
  `risk:` nello YAML, per-strategy. Validato da `validate_spec_risk()` in
  `backtest/lifecycle.py` contro global caps (leva ≤4 con justification,
  max_concurrent ≤12, risk_per_trade ≤2%). Il runner `paper_all.py` warna
  sulle violazioni ma non blocca (così il loop evolutivo può esplorare).

I limiti dei desk LLM sono più stretti (3 pos, leva 2) perché l'LLM può
concentrare rischio su una tesi; le meccaniche diversificano su basket più
ampi (fino a 12 pos) perché l'edge è statistico, non conviction-based.

### 4. Segnali = edge validato, non "non lagging"
Registry chiuso in `backtest/signals.py`. Criterio di ammissione: edge
documentato su basket multi-asset (`scripts/research_edges.py` con IC + t-stat)
oppure tesi accademica robusta (es. Moskowitz-Ooi-Pedersen per tsmom).
Il vecchio divieto "no SMA/RSI/MACD perché lagging" era dogmatico e
incoerente (vwap_zscore e funding_percentile sono anch'essi lagging).
Criterio reale: **edge misurato o tesi accademica**, non estetica del segnale.
Niente segnali aggiunti al registry senza backtest pubblico o paper di riferimento.

### 5. Selezione su basket multi-asset (mean Sharpe per-asset)
Promozione/retrocessione in `scripts/promote.py` usa `basket_sharpe_r` e
`basket_mean_r` da `paper_stats()` in `backtest/lifecycle.py`: Sharpe/mean R
calcolato **per-symbol** poi mediato sul basket. Una strategia che vince su
BTC e perde su 8 alt non passa — il pooled stat maschererebbe la concentrazione.
Mai promuovere su singolo asset.

### 6. Tesi falsificabile obbligatoria
Su ogni trade (JSON strategist: `thesis` + `invalidation`) e ogni strategia
(YAML: campo `thesis` + clausola `Falsificata se:` misurabile). Lezioni
documentano quando la tesi era wrong. `hard_check` vetoa proposte LLM senza
tesi/invalidazione.

### 7. Lezioni unificate
`paper/lessons.jsonl` è il canale unico. `scripts/review.py --add` per le
lezioni da post-mortem trade. `scripts/promote.py` scrive lezioni di
retirement/promozione via `add_lesson()` (schema compatibile: `trade_key`,
`symbol=basket`, `verdict`, `lesson`, `tags`). `recall_lessons` in decide.py
legge entrambi.

### 8. LLM backend con fallback
Env `ANTHROPIC_*` strippato dal subprocess LLM (proxy DashScope scaduto in
zshrc dirotta le chiamate). Backend primario: `claude -p` (piano Pro Claude
Code). Fallback automatico: `opencode run -m opencode-go/glm-5.2` se claude
fallisce (quota/429/CLI mancante). Trasparente per i chiamanti (`_ask` in
`decide.py`). In cloud: `paper-run.yml` installa opencode + scrive `auth.json`
da secret `OPENCODE_GO_API_KEY`.

### 9. Architettura cloud-first
Paper-run su GitHub Actions (orario via Cloudflare Worker = clock affidabile,
scheduler nativo GitHub salta i repo privati). Dashboard statica su Cloudflare
Pages (`lux-ai.pages.dev`, deploy da `paper-run.yml`). Mac = dev box, niente
processi produttivi residenti. Precompute pesanti (Kronos, GDELT, xsection,
HMM) in workflow dedicati fuori dall'hot path orario.

### 10. Loop evolutivo: walk-forward sempre
Mai promuovere su backtest solo — il paper trading è il gate finale
(`FORMAT.md`). `promote.py` ritira su performance paper (mean_r < 0 con
campione, o drawdown equity ≤ -15% precoce). Gate statistico formale
(deflated Sharpe, complessità penalty) = roadmap. Penalità per complessità
(n. segnali e parametri) da implementare.
