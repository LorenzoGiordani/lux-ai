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
| `scripts/decide.py` | **Pipeline agenti**: contesto live → ruoli LLM → hard limits → Risk Manager. LLM: GLM-5.2 (Z.ai Coding Plan) |
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
| `xsection_momentum` | momentum relativo | tutti | rank nel basket (IC +0.089, t +21) |
| `nadaraya_watson` | struttura prezzo | tutti | envelope kernel-regression (DaviddTech); continuation IC +0.105 (t +5) |

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

**Scoperta nuove strategie (sessione 26/06, ispirazione DaviddTech)** — basket 9 crypto, 12m walk-forward, fee/slippage inclusi, DSR vs champion:

| Strategia | Mean Sharpe | DSR | Ret | worstDD | Esito |
|---|---|---|---|---|---|
| **lux-flow-confluence** (champion tsmom+liq) | 0.71 | 0.87 | +11.0% | -22% | live edge di riferimento |
| **lux-nw-liq** (NW kernel + liq) | 0.59 | 0.87 | +9.6% | -24% | challenger competitivo: NW può sostituire tsmom |
| lux-nw-continuation (NW puro) | 0.18 | 0.33 | +2.2% | -25% | edge reale ma modesto standalone |
| lux-nw-tsmom (NW + tsmom) | -0.30 | 0.11 | -5.4% | -40% | **FALSIFICATA**: gambe correlate |
| lux-regime-3leg (champion + hmm gate) | 0.08 | 0.34 | +1.1% | -26% | **FALSIFICATA**: gate AND soffoca |

**Approfondimento 2° giro (26/06, tutto falsificato onestamente)** — validati prima via research IC, poi backtest:

| Idea | Edge misurato | Backtest | Esito |
|---|---|---|---|
| Pullback-in-trend (DaviddTech) | fwd ext +0.012 vs pull −0.007 | — | **FALSIFICATO**: il regime premia l'estensione, non il ritorno |
| Funding carry standalone | IC +0.094 ma t +1.6 (336h) | — | **FALSIFICATO**: edge troppo debole, non passa il gate |
| Efficiency Ratio (Kaufman) come gate | basket Δ ~0 (eterogeneo) | — | **FALSIFICATO**: valido su subset (BTC/ETH/SUI/ZEC), invertito su altri |
| Champion + xsection (3 gambe) | conditional IC TOP +0.032 vs BOT +0.015 | Sharpe −0.45/−0.75 | **FALSIFICATO**: edge reale ma richiede concordanza, non catturabile per-simbolo |

- **Lezione capitale**: l'edge cross-sectional (`xsection_momentum`, IC +0.089 t+21 — il piú forte mai misurato) **resta non sfruttato**. La cache era stale (201g vs 360g, ora rigenerata a 12m), e l'edge NON è catturabile nel motore per-simbolo (richiede concordanza direzionale). Abita nell'**engine a portafoglio dollar-neutral** (`xsmom-port-v1`, backtest +29% vs −20%, ritirata solo per strumentazione paper). É il filone prioritario da riprendere.
- **La cura del regime filter**: l'implementazione DaviddTech corretta è un **VETO** sui periodi chop (sospende), non una terza gamba AND (soffoca). Lezione documentata in `paper/lessons.jsonl`.

**🏆 FILONE PRINCIPALE RIAPERTO (26/06): cross-sectional momentum a PORTAFOGLIO.**
`xsmom-port-v1` ripresa in produzione. L'edge cross-sectional (`xsection_momentum`, IC +0.089 t+21 — il piu' forte misurato) non era sfruttato perche': (a) la cache era stale a 201g vs 360g candele (rigenerata a 12m); (b) l'edge NON e' catturabile nel motore per-simbolo (falsificato: Sharpe -0.27/-0.45/-0.75 su 3 varianti — richiede concordanza, non attività). Abita nell'**engine a portafoglio dollar-neutral**. Backtest basket 9 crypto, 12m walk-forward, fee+slippage inclusi:

| Config | Ret | Sharpe | maxDD | DSR | vs benchmark |
|---|---|---|---|---|---|
| **xs-mom dollar-neutral lb168 reb168 g1** | **+79.8%** | **2.11** | **-19%** | 0.91 | benchmark equal-weight **-8.8%** (maxDD -59%) |
| xs-mom dollar-neutral lb168 reb24 g1 | +94.7% | 2.34 | -17% | 0.94 | ribilanciamento +frequente |
| xs-mom long-only lb168 reb168 g1 | +72.7% | 1.08 | **-65%** | 0.62 | senza netting → DD 3x peggio |

Il dollar-neutral e' cruciale (abbatte il DD del 46pp). Era stata ritirata il 25/06 **solo per strumentazione paper** (logga `rebalance`/`heartbeat` con equity, non `open`/`close` → appariva con 0 trade). Fix: `paper_stats` deriva ora Sharpe/ret/maxDD dall'equity curve per `engine:portfolio`. Runner ripristinato in `cron_run.sh` e `paper-run.yml`.

**Sweep edge portfolio ortogonali (26/06, 8 configurazioni testate)** — cercavo un secondo edge forte, onestamente non c'e':

| Config | Sharpe | maxDD | Verdetto |
|---|---|---|---|
| **xsmom** (core) | **2.11** | -19% | l'unico davvero forte |
| **xsmom-multihorizon** (lb 96+168+336) | 1.85 | **-16%** | compagno conservativo, DD minore |
| funding carry book | 0.39-0.77 | -24/39% | debole, NON esplode a portfolio |
| TSMOM long vol-target | 1.01 | **-68%** | drawdown inaccettabile |
| xsmom vol-weighted | 1.05 | -23% | peggio dell'equal-weight |
| xsmom+tsmom-long combo | 1.80 | -33% | DD peggiore, niente vantaggio |

**Loop per-simbolo SVUOTATO (26/06)** — tutte le strategie per-simbolo erano rumore colorato (Sharpe 0.12-0.71 vs xsmom 2.11). Ritirate lux-flow-confluence, lux-nw-liq, lux-confluence-rr2. Il loop e' ora **tutto engine:portfolio**: xsmom-port (core) + xsmom-multihorizon (conservative). Le desk LLM (agents-v1: 54% win realizzato su 13 trade) restano per il track record live dimostrativo.

- **Segnale nuovo validato**: `nadaraya_watson` (envelope kernel-regression, firma DaviddTech). Edge study (`scripts/research_nw.py`): il breakout di banda è un segnale di **continuation** (IC +0.105, t +5 a 48h), non di mean-reversion (il fade ha IC negativo → falsificato, coerente col regime trend 2026-H1).
- **Lezione chiave di falsificazione**: la confluence funziona solo fra gambe **ortogonali** per costruzione (prezzo-struttura NW × flusso liq → competitivo; prezzo-struttura NW × momentum tsmom → correlate, l'AND ammazza le entry). E un gate di regime come AND a 3 gambe soffoca l'edge; andrebbe usato come **veto** sui periodi chop, non come requisito di entry.

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

**Backend LLM** — un solo modello, **GLM-5.2** via **Z.ai Coding Plan** (pinnato, **max effort** = extended thinking di default). Nessun claude, nessun opencode: il layer unificato `scripts/llm.py` parla l'endpoint Anthropic-Messages del coding plan (`https://api.z.ai/api/anthropic`, header `x-api-key`) con un client HTTP minuscolo (requests). Prompt centralizzati e versionati in `prompts/roles.yaml` (ruolo → system + effort + schema). Il tracing di ogni chiamata finisce in `paper/llm_calls.jsonl` (`uv run scripts/llm_stats.py` per il riepilogo, sezione **LLM** nella dashboard).

Capacità del layer:
- **Effort differenziato per ruolo** — Strategist/Analyst/evolve a `max` thinking; Bull/Bear/Risk/Auditor a `low`/`medium` (sono veto, non serve 32k token) → risparmio ~60% token a parità di decisioni.
- **Structured output nativo** — i ruoli con `schema` (strategist/risk/auditor/…) rispondono via Anthropic tool use forzato → JSON già validato, niente parsing regex fragile.
- **Self-consistency** — la decisione finale dello Strategist è il majority vote di N=3 campioni (`GLM_SC_N`), riduce la varianza del flip-di-moneta di una singola chiamata LLM.
- **Cache applicativo** (`GLM_CACHE_DIR`) — memoizza per hash(prompt): eval deterministici, dedup, test a costo zero.

Credenziali (priorità): env `ZAI_API_KEY` → `.env` → config zcode locale (`~/.zcode/v2/config.json`, provider `builtin:zai-coding-plan`). In cloud il workflow legge il secret `ZAI_API_KEY`. Tunable: `GLM_MODEL` (default `GLM-5.2`), `ZAI_BASE_URL`, `GLM_THINKING_BUDGET`. `uv run scripts/llm.py` per lo smoke test. ⚠️ Il caching lato-API (`cache_control`) NON è supportato dal bridge Z.ai (verificato), quindi è tutto client-side.

## Roadmap

Stato reale (audit giugno 2026, sessione di hardening). M1–M4 costruiti; l'unico gate rimasto prima dei fondi reali è il **track record paper nel tempo** (mesi, non ingegneria).

- [x] M1 — dati, harness, registry, formato strategia, loop evolutivo (3 generazioni)
- [x] M2 — paper trading live in cron, pipeline agenti end-to-end, reflection loop, **CLI nativa autonoma** in cloud (paper-run.yml: decide+review+promote+evolve orari)
- [x] COT report CFTC (posizionamento commodities = analogo del funding)
- [x] Champion/challenger con gate statistico formale (**deflated Sharpe ≥0.95** enforced in `promote.py`)
- [x] Journal → Supabase (schema + `sync_supabase.py` idempotente + workflow cloud gated; il recall semantico pgvector è cablato, l'embedding da popolare a progetto creato)
- [x] Interfaccia v2 → Cloudflare Pages (`lux-ai.pages.dev`, deploy nel workflow)
- [x] M4 — testnet Hyperliquid (`execute_testnet.py` dry-run sicuro, isolato per regola #2 — va in cron solo con `HL_API_SECRET` configurato)
- [ ] **M5 — vault HyperEVM** (ERC-4626, solo a track record paper dimostrato su mesi). Gate di tempo, non di codice.

**Cosa manca a M5**: niente ingegneria — serve che le strategie paper accumulate dimostrino nel tempo un edge robusto (deflated Sharpe, basket multi-asset) prima di muovere un euro reale on-chain. `promote.py` è il gate formale che decide quando il track record è "dimostrato".

### Hardening & audit (25/06)
Suite di test verde (**98 pass**). Sessione di audit + bugfix:
- **Integrità del journal (finding chiave)** — i test `*_time_stop_fallback` chiamavano `open_from_decision` → `log_event` scriveva aperture **false** (`thesis:"t"`) sul journal REALE `paper/journal.jsonl`, e il cron le committeva. Bug cronico: ogni `pytest` corrompeva il "prodotto pubblico". Fix: monkeypatch del `JOURNAL` verso `tmp_path` + pulizia di 6 righe false già committate.
- **`agents_paper.py`**: floor difensivo `time_stop_h or 96` (bug latente simmetrico al desk geo: un LLM che emette `time_stop_h=0` faceva scattare l'uscita a *ogni* candela chiusa). Aggiunto test di regressione.
- **`backtest_report.py`**: `pd.Timestamp.utcnow()` deprecato in pandas → `Timestamp.now(tz="UTC")` (rottura imminente al prossimo upgrade).
- **`cron_run.sh`**: leftover strutturale (riga indentata copia-incollata dal blocco YAML del workflow cloud) + prima chiamata `agents_paper.py` senza `|| true` (un errore interrompeva tutta la catena locale).
- **Cleanup lint**: import inutilizzati, variabili morte, `NameError` latente (`notional` non definito in `test_impact.py`) risolti. `ruff --select F` pulito.
- `.gitignore`: tooling temporaneo di live-render/screenshot del design skill (`scripts/_render_*.js`, `scripts/_shot_*.png`).

## Riferimenti

[TradingAgents](https://github.com/TauricResearch/TradingAgents) (pattern, non i numeri) · [Kronos](https://github.com/shiyu-coder/Kronos) · [FINSABER](https://arxiv.org/abs/2505.07078) · [Profit Mirage](https://arxiv.org/abs/2510.07920) · [TSMOM](https://quantpedia.com/strategies/time-series-momentum-effect) · [nof1 Alpha Arena](https://nof1.ai/)
