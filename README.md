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
| `backtest/engine.py` | Exchange simulato: fill t+1 (anti-lookahead), fee, **funding storico** (opz.), **slippage size-aware** square-root (opz. `impact_k`), **liquidazione mark-to-market** su account equity (opz. `maintenance_margin_frac`), stop/target intrabar |
| `backtest/signals.py` | **Registry segnali** (chiuso, l'LLM compone ma non inventa codice) |
| `backtest/strategy.py` | Artefatto YAML → callback engine (rule AND/OR, direction, sizing) |
| `backtest/walkforward.py` | Metriche per fold temporali e regime bull/bear/chop |
| `strategies/FORMAT.md` | Schema artefatto strategia (tesi, segnali, exit, risk immutabile, lineage) |
| `scripts/run_strategy.py` | Backtest singola strategia su un asset |
| `scripts/evolve.py` | **Loop evolutivo**: LLM propone mutazioni → valutazione basket → leaderboard |
| `scripts/decide.py` | **Pipeline agenti**: contesto live → ruoli LLM → hard limits → Risk Manager. Fallback LLM: claude→opencode glm-5.2 |
| `scripts/agents_paper.py` | Executor paper delle decisioni pipeline |
| `scripts/claude_strategy.py` | Strategia ibrida: gate tsmom+liq_imbalance → PM LLM avverso |
| `scripts/glm_strategy.py` | **Strategia glm-5.2**: gate tsmom+xsection (ortogonale) + veto event/crowding → auditor LLM correlazione |
| `scripts/paper_trade.py` | Paper trading challenger segnale-based (cron) |
| `scripts/review.py` | Reviewer: post-mortem trade chiusi → `paper/lessons.jsonl` |
| `scripts/dashboard.py` | Dashboard statica (HTML, zero dipendenze) — include sezione **Backtest** onesto || `scripts/backtest_report.py` | Backtest basket multi-asset delle strategie attive (funding storico + slippage size-aware) → `paper/backtests.json` → sezione Backtest |
| `scripts/cron_run.sh` | Run unificato ogni 4h (crontab) |
| `pipeline/live.py` | Dati live: Binance (crypto), yfinance (xyz_*), OI, news RSS 6 fonti |
| `paper/*.jsonl` | Journal: trade, decisioni con tesi, lezioni — il "prodotto pubblico" |
| `db/schema.sql` | Schema Postgres/Supabase: trades, decisions, lessons (pgvector), equity_snapshots |
| `scripts/sync_supabase.py` | Sync incrementale journal→Supabase (idempotente via source_key, no-op senza credenziali) |

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

**Onestà del backtest (funding storico + slippage size-aware).** Il funding è ora storico reale per-asset (la costante legacy sovrastimava di ~8x e nascondeva i flip di segno nei mesi bear). Lo slippage è opzionalmente un modello square-root (Almgren 2005, additivo sul base). Slippage size-aware (square-root, Almgren 2005) e liquidazione mark-to-market su account equity (con MMR) opt-in. Su CRV (illiquido) l'impact smaschera un Profit Mirage: Sharpe 0.73→0.16 a $10k. Su BTC (liquido) l'edge regge fino a $10M AUM (1.37→1.33). La liquidazione MTM coincide col legacy a leva ragionevole (≤5, nessuna posizione attiva la rischia) ma a leva 8 + flash crash lascia il margine residuo realistico (1088$ vs 0 del legacy rigido). `run_strategy.py --impact 0.5 --mmr 0.01` per attivarli.

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

**Backend LLM**: `claude -p` headless (piano Pro Claude Code) come primario; **fallback automatico** su `opencode run -m opencode-go/glm-5.2` se claude fallisce (quota esaurita, CLI mancante, 429). Trasparente per i chiamanti (`_ask` in `decide.py`). In cloud: il workflow installa opencode + scrive `auth.json` dal secret `OPENCODE_GO_API_KEY`. Nessuna API key Anthropic richiesta. ⚠️ Lo `~/.zshrc` locale ha un `ANTHROPIC_BASE_URL` (proxy DashScope, key scaduta) — gli script lo strippano dall'env.

## Roadmap

Stato reale (audit giugno 2026). M1–M4 costruiti; l'unico gate rimasto prima dei fondi reali è il **track record paper nel tempo** (mesi, non ingegneria).

- [x] M1 — dati, harness, registry, formato strategia, loop evolutivo (3 generazioni)
- [x] M2 — paper trading live in cron, pipeline agenti end-to-end, reflection loop, **CLI nativa autonoma** in cloud (paper-run.yml: decide+review+promote+evolve orari)
- [x] COT report CFTC (posizionamento commodities = analogo del funding)
- [x] Champion/challenger con gate statistico formale (**deflated Sharpe ≥0.95** enforced in `promote.py`)
- [x] Journal → Supabase (schema + `sync_supabase.py` idempotente + workflow cloud gated; il recall semantico pgvector è cablato, l'embedding da popolare a progetto creato)
- [x] Interfaccia v2 → Cloudflare Pages (`lux-ai.pages.dev`, deploy nel workflow)
- [x] M4 — testnet Hyperliquid (`execute_testnet.py` dry-run sicuro, isolato per regola #2 — va in cron solo con `HL_API_SECRET` configurato)
- [ ] **M5 — vault HyperEVM** (ERC-4626, solo a track record paper dimostrato su mesi). Gate di tempo, non di codice.

**Cosa manca a M5**: niente ingegneria — serve che le strategie paper accumulate dimostrino nel tempo un edge robusto (deflated Sharpe, basket multi-asset) prima di muovere un euro reale on-chain. `promote.py` è il gate formale che decide quando il track record è "dimostrato".

## Riferimenti

[TradingAgents](https://github.com/TauricResearch/TradingAgents) (pattern, non i numeri) · [Kronos](https://github.com/shiyu-coder/Kronos) · [FINSABER](https://arxiv.org/abs/2505.07078) · [Profit Mirage](https://arxiv.org/abs/2510.07920) · [TSMOM](https://quantpedia.com/strategies/time-series-momentum-effect) · [nof1 Alpha Arena](https://nof1.ai/)
