# DeFi AI Vault — trading research autonoma con agenti AI

Piattaforma di trading research che **impara in pubblico**: agenti LLM propongono trade con tesi falsificabili, li eseguono su un conto paper (balance fittizio, prezzi reali), scrivono post-mortem degli errori, e fanno evolvere le strategie di generazione in generazione. Il prodotto è la trasparenza: ogni tesi, errore e lezione è tracciata.

> **Stato: paper trading. Nessun fondo reale. Niente in questo repo è consulenza finanziaria.**

## Visione

- **Fase 1 (ora)**: validare il sistema — backtest onesti, paper trading live, learning loop dimostrabile
- **Prodotto 1**: "ricerca in pubblico" — journal tesi + lezioni + lineage evolutivo pubblici (stile Alpha Arena/nof1, ma continuo)
- **Prodotto 2** (solo a track record dimostrato): vault on-chain su Hyperliquid (HyperEVM ERC-4626), depositi pubblici gestiti dal champion

Design doc completo in Obsidian (`Projects/Active/DeFi AI Vault`).

## Architettura — due loop

```
INNER LOOP (tattico, ogni 4h)                 OUTER LOOP (evolutivo, giorni)
─────────────────────────────                 ──────────────────────────────
contesto live (prezzi/funding/OI/news)        strategia = artefatto YAML versionato
   → Analyst → debate bull/bear                  → LLM propone N mutazioni motivate
   → Strategist (tesi falsificabile)             → harness valuta su basket multi-asset
   → HARD LIMITS nel codice (insindacabili)      → walk-forward per fold e regime
   → Risk Manager LLM (approve/reduce/veto)      → selezione → challenger → paper
   → executor paper → stop/target reali          → champion (gate statistico)
   → Reviewer post-mortem → LEZIONI
   → recall lezioni nei prompt  ←── il loop si chiude
```

Principi non negoziabili:
- **Tesi falsificabile obbligatoria** su ogni trade e ogni strategia
- **Blocco risk immutabile dall'LLM**: leva ≤2, rischio ≤1%/trade, stop obbligatorio, max 3 posizioni
- **Backtest solo su dati post-cutoff** del modello o forward test (lezione: FINSABER, Profit Mirage — i backtest LLM pubblicati sono contaminati)
- **Niente indicatori mainstream/lagging** (no SMA/RSI/MACD): solo segnali leading/strutturali da registry chiuso
- **Selezione multi-asset** (mean Sharpe su basket): mai promuovere su singolo asset

## Componenti

| Path | Cosa fa |
|---|---|
| `scripts/fetch_universe.py` | Universo asset Hyperliquid (mainnet, volumi reali) filtrato per liquidità |
| `scripts/fetch_candles.py` | Candele 1h 12 mesi: Binance (crypto), yfinance (commodities/stock), HL fallback |
| `scripts/fetch_derivs.py` | Funding + taker flow storici (Binance fapi) |
| `backtest/engine.py` | Exchange simulato: fill t+1 (anti-lookahead), fee/slippage/funding, stop/target intrabar, liquidazioni |
| `backtest/signals.py` | **Registry segnali** (chiuso, l'LLM compone ma non inventa codice) |
| `backtest/strategy.py` | Artefatto YAML → callback engine (rule AND/OR, direction, sizing) |
| `backtest/walkforward.py` | Metriche per fold temporali e regime bull/bear/chop |
| `strategies/FORMAT.md` | Schema artefatto strategia (tesi, segnali, exit, risk immutabile, lineage) |
| `scripts/run_strategy.py` | Backtest singola strategia su un asset |
| `scripts/evolve.py` | **Loop evolutivo**: LLM propone mutazioni → valutazione basket → leaderboard |
| `scripts/decide.py` | **Pipeline agenti**: contesto live → ruoli LLM → hard limits → Risk Manager |
| `scripts/agents_paper.py` | Executor paper delle decisioni pipeline |
| `scripts/paper_trade.py` | Paper trading challenger segnale-based (cron) |
| `scripts/review.py` | Reviewer: post-mortem trade chiusi → `paper/lessons.jsonl` |
| `scripts/dashboard.py` | Dashboard statica (HTML, zero dipendenze) |
| `scripts/cron_run.sh` | Run unificato ogni 4h (crontab) |
| `pipeline/live.py` | Dati live: Binance (crypto), yfinance (xyz_*), OI, news RSS 6 fonti |
| `paper/*.jsonl` | Journal: trade, decisioni con tesi, lezioni — il "prodotto pubblico" |
| `db/schema.sql` | Schema Postgres/Supabase (journal + lessons pgvector) — da collegare |

I dati storici (`data/`) non sono nel repo: si rigenerano con i 3 script fetch (~5 min).

## Registry segnali

| Segnale | Tipo | Asset | Note |
|---|---|---|---|
| `funding_percentile` | posizionamento | solo crypto | estremi di crowding |
| `taker_flow` | flusso aggressori | solo crypto | soglia calibrata su dati reali (p90≈0.02) |
| `range_breakout` | struttura | tutti | rottura range con conferma volume |
| `vol_compression` | regime | tutti | setup pre-espansione |
| `tsmom` | momentum | tutti | Moskowitz-Ooi-Pedersen, orizzonti 7g+30g |
| `vwap_zscore` | estensione | tutti | deviazione dal VWAP rolling |
| `volume_surge` | partecipazione | tutti | percentile volume relativo |

## Risultati finora (backtest 6 mesi, fee/slippage inclusi; paper live dal 11/06/2026)

**Evoluzione famiglia funding-squeeze (3 generazioni, crypto)**
| Strategia | Mean Sharpe (basket 9) | Esito |
|---|---|---|
| v1 breakout+funding | -1.04 (solo BTC) | baseline, perde nel chop |
| g2 fade del crowding | -0.43 | vince nel chop, travolto dai trend (SOL -15%) |
| g2-g1 +gate vol_compression | -0.13 | gate confermato |
| g2-g1-g2 (challenger) | -0.09, ret +0.03% | plateau → famiglia a breakeven, stop alle mutazioni (= overfitting) |

**TSMOM multi-asset** (BTC, ETH, SOL, GOLD, CL, BRENT, SILVER, SP500, MU)
- **Mean Sharpe 1.69, ret medio +11.3%, 8/9 asset positivi** — conferma la letteratura → challenger in paper

**Tesi falsificate** (documentate in `paper/lessons.jsonl`): scalp-exit su crowding, flow-confirmed breakout, fade VWAP (7/7 asset), stop più stretti dell'invalidazione. Pattern: il regime 2026-H1 premia il trend, punisce il mean-reversion.

**Learning loop dimostrato**: ZEC long (tesi squeeze) → stop -50.92$ (=0.5% budgettato, il reduce del Risk Manager ha dimezzato il danno) → 2 lezioni → recall attivo nei prompt.

## Come gira

```bash
uv sync                                          # dipendenze
uv run scripts/fetch_universe.py && uv run scripts/fetch_candles.py && uv run scripts/fetch_derivs.py
uv run scripts/run_strategy.py strategies/tsmom-v1.yaml BTC 6   # backtest
uv run scripts/decide.py BTC,ETH,SOL --pack      # pipeline (LLM in sessione)
uv run scripts/dashboard.py && open dashboard/index.html
sh scripts/cron_run.sh                           # run completo (in crontab ogni 4h)
```

**Backend LLM**: `claude -p` headless (piano Pro Claude Code) quando la CLI nativa è installata; in alternativa modalità `--pack`/file-candidati con sessione Claude Code interattiva. Nessuna API key richiesta. ⚠️ Lo `~/.zshrc` locale ha un `ANTHROPIC_BASE_URL` (proxy DashScope, key scaduta) — gli script lo strippano dall'env.

## Roadmap

- [x] M1 — dati, harness, registry, formato strategia, loop evolutivo (3 generazioni)
- [x] M2 (parziale) — paper trading live in cron, pipeline agenti end-to-end, reflection loop
- [ ] CLI nativa → pipeline completamente autonoma (decisioni + review in cron)
- [ ] COT report CFTC (posizionamento commodities = analogo del funding)
- [ ] Champion/challenger con gate statistico formale (deflated Sharpe)
- [ ] Journal → Supabase (pgvector recall semantico)
- [ ] Interfaccia v2 (design in corso, `dashboard/design-prompt.md`) → Cloudflare Pages
- [ ] M4 — testnet Hyperliquid (API wallet solo-trading)
- [ ] M5 — vault HyperEVM (solo a track record dimostrato)

## Riferimenti

[TradingAgents](https://github.com/TauricResearch/TradingAgents) (pattern, non i numeri) · [Kronos](https://github.com/shiyu-coder/Kronos) · [FINSABER](https://arxiv.org/abs/2505.07078) · [Profit Mirage](https://arxiv.org/abs/2510.07920) · [TSMOM](https://quantpedia.com/strategies/time-series-momentum-effect) · [nof1 Alpha Arena](https://nof1.ai/)
