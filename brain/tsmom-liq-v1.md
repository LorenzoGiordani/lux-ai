# tsmom-liq-v1

[[README|← Brain index]]

## Anagrafica

- **status**: challenger
- **created**: 2026-06-14

## Tesi

Trend confermato dalle liquidazioni reali (Coinalyze): entra solo quando TSMOM e lo sbilancio liquidazioni concordano sulla direzione (segui lo squeeze). Primo edge ortogonale robusto: 100% celle griglia battono il baseline, 7/9 coin positivi. In paper per validazione forward.

## Note evoluzione

seed di ricerca

## Performance (paper)

- equity: $9,835.97
- trade chiusi: 14 · win rate: 21%
- PnL totale: $-146.74
- posizioni aperte ora: 2

### Posizioni aperte

| symbol | dir | entry | stop | target | size |
|---|---|---|---|---|---|
| SUI | short | 0.717196532 | 0.7351264452999999 | 0.6634067921 | $2,361.14 |
| BTC | short | 62932.411 | 64505.721274999996 | 58212.480175000004 | $2,360.89 |

### Trade chiusi

| symbol | reason | exit | PnL |
|---|---|---|---|
| XRP | stopped | 1.1645024534199 | $-61.57 |
| NEAR | target | 2.2725499090979997 | $178.38 |
| NEAR | target | 2.543449898262 | $180.45 |
| WLD | stopped | 0.5799299768028 | $-62.25 |
| ZEC | stopped | 521.87847912486 | $-63.35 |
| NEAR | stopped | 2.4219974031201 | $-62.96 |
| WLD | stopped | 0.58134372674625 | $-62.56 |
| ZEC | stopped | 503.50947985962 | $-62.17 |
| CRV | stopped | 0.24065924037362998 | $-61.78 |
| WLD | stopped | 0.62587197496512 | $-61.01 |
| CRV | stopped | 0.23526749058929997 | $-61.00 |
| WLD | target | 0.6872474725101 | $174.63 |
| WLD | stopped | 0.6606599735735998 | $-61.31 |
| CRV | stopped | 0.23090924076363 | $-60.24 |

## Lezioni

- **execution_issue** (XRP, $-61.57): Quando tsmom e liq_imbalance convergono (-1/-1) il segnale è solido, ma su asset ad alta volatilità intraday (XRP, ATR giornaliero > 3%) uno stop a ~2.5% cade dentro la banda di rumore e non fuori dalla tesi. Gli stop di momentum-liq vanno calibrati su 1.5-2x ATR del timeframe del segnale, non su una percentuale fissa: altrimenti ogni rimbalzo tecnico di 5h elimina il trade prima che la direzionalità si esprima. #stop_sizing #atr_calibration #tsmom #xrp_volatility #premature_stopout
- **execution_issue** (NEAR, $178.38): Exit price (2.2725) è sotto entry (2.3664) su un long, ma PnL registrato è +$178. Inoltre ts_close (02:00) precede opened_at (04:00) di 2 ore. Il record è strutturalmente corrotto: il sistema deve validare sign(exit_px - entry_px) == sign(pnl_usd) per i long e ts_close > ts_open prima di persistere su journal — ogni post-mortem su dati incoerenti produce lezioni spurie e degrada il backtest. #data-integrity #pnl-sign-mismatch #timestamp-inversion #logging-bug #tsmom-liq-v1
- **thesis_right** (NEAR, $180.45): Quando tsmom e liq_imbalance convergono entrambi a +1 (signal_vote pieno), il trade ha sufficiente conviction per giustificare R:R ≥ 3:1 con target fisso: uscire anticipatamente o ridurre il target per 'sicurezza' sarebbe stato un errore atteso-negativo. La confluenza momentum + order-flow su alt-L1 genera move intraday completi — non scalare out prima del target. #signal_confluence #tsmom #liq_imbalance #alt_l1 #intraday_momentum #full_target
- **thesis_wrong** (WLD, $-62.25): segnali tsmom+liq_imbalance su token narrativi a bassa capitalizzazione catturano spesso momentum di brevissimo termine (spike di liquidità) che si esaurisce entro poche candele: senza un filtro di regime (BTC sopra MA su H4, settore AI/L1 in risk-on) il segnale long su altcoin volatili ha tasso di falsi positivi strutturalmente alto e va ridotto in size o saltato #tsmom #false_positive #regime_filter #narrative_token #altcoin #low_cap
- **execution_issue** (ZEC, $-63.35): Doppio segnale confluente (tsmom+liq entrambi=1) su un alt ad alta volatilità segnala potenziale entry affollato: molti sistemi sistematici ricevono lo stesso trigger simultaneamente, e uno stop fisso al 2.5% viene colpito dal noise di mean-reversion prima che la tesi si dispieghi. Regola generale: su alt con ATR/day ≥ 3%, calibrare lo stop a 1× ATR(14) e ridurre la size proporzionalmente; in alternativa, attendere un micro-pullback dal primo tick di segnale per entry meno denso. #stop_sizing #atr_calibration #crowded_entry #signal_confluence #altcoin_volatility #execution
- **execution_issue** (NEAR, $-62.96): Quando tsmom + liq_imbalance si allineano su altcoin ad alta beta (NEAR, SOL-tier), uno stop fisso <3% viene consumato dal rumore intraday prima che il momentum si materializzi: il minimo stop deve essere ≥1.5× ATR daily del simbolo; in alternativa ridurre la size proporzionalmente per mantenere il risk assoluto costante con uno stop più largo. #stop_calibration #atr_sizing #tsmom #liq_imbalance #altcoin_noise
- **execution_issue** (WLD, $-62.56): Un segnale tsmom è per definizione costruito su finestre giornaliere (o multi-ora): lo stop deve essere ≥ 1× ATR-giornaliero del sottostante, altrimenti il rumore intraday esaurisce il margine prima che la tesi si materializzi. WLD ha ATR-daily ~5-8%; uno stop al 2.5% sotto l'entry entra direttamente nella fascia di rumore e viene colpito statisticamente anche quando la direzione è corretta. Regola generale: su strategie momentum a bassa frequenza, calibra lo stop sul timeframe del segnale (daily ATR), non sulla tolleranza di rischio in USD — aggiusta il size per tenere il rischio fisso, non restringere lo stop. #tsmom #stop-calibration #atr-mismatch #signal-timeframe #crypto-momentum #size-vs-stop-tradeoff
- **thesis_wrong** (ZEC, $-62.17): In fasi di downtrend strutturale su altcoin ad alta beta (ZEC), segnali tsmom+liq_imbalance rialzisti catturano spesso picchi di crowding long piuttosto che momentum genuino: il segnale si accende quando tutti sono già entrati, non quando inizia la spinta. Richiedere un regime-filter esplicito (es. BTC price > MA20 o rolling-Sharpe basket > 0) prima di approvare long su tsmom in altcoin. #tsmom #false-momentum #altcoin-beta #regime-filter #crowding-peak #ZEC
- **execution_issue** (CRV, $-61.78): Segnali tsmom+liq_imbalance su token DeFi small-cap richiedono un filtro di regime esplicito: in mercato bear/laterale, gli squilibri di liquidità su CRV-class asset sono noise e non segnale direzionale — long momentum senza conferma macro (es. BTC sopra EMA breve o realized-vol sotto soglia) producono whipsaw sistematici il cui stop-rate supera l'alpha atteso del setup. #tsmom #regime_filter #defi_small_cap #whipsaw #liq_imbalance #bear_regime
- **execution_issue** (WLD, $-61.01): Su altcoin ad alta volatilità (WLD, float basso), uno stop fisso %-based ignora l'ATR del timeframe: un'oscillazione di 2.5% in 1h è rumore ordinario, non invalidazione della tesi. I segnali tsmom+liq_imbalance erano coerenti ma lo stop è stato piazzato dentro il noise-band — regola: stop su tsmom-liq entries deve essere ≥1× ATR(4h) per sopravvivere al mean-reversion intra-candle senza che la tesi direzionale venga falsificata. #stop_sizing #atr_calibration #tsmom #liq_imbalance #altcoin_volatility #noise_vs_signal
- **thesis_wrong** (CRV, $-61.00): tsmom + liq_imbalance simultanei su token DeFi (bassa cap, alto crowding) possono riflettere momentum già esaurito al momento del segnale — non un'accelerazione in corso. Regola generale: in regime neutro/bear su BTC, esigere N ore di persistenza del segnale (es. 2+ candle di conferma) e coerenza col trend ETH prima di entrare long su DeFi; un segnale intracandle fermato in <1h indica che la liq_imbalance era noise temporaneo, non pressione direzionale sostenuta. #tsmom #liq_imbalance #signal_staleness #defi_crowding #regime_filter #entry_timing
- **execution_issue** (WLD, $174.63): Il PnL (+$174.63 su $2390.57 = 7.3%) è coerente con un fill al target (0.7286, +7.5%) ma exit_px registra 0.6872 (+1.4%) — discrepanza ~5x: il logger sta scrivendo il mark price al momento del log invece del fill price simulato. Aggravante: close.logged_at (20:16) precede open.logged_at (21:15) e open_ts == close_ts (stesso candle), indicando race condition nel pipeline. In paper trading, separare rigorosamente fill_px (prezzo di esecuzione deterministico, fissato all'istante del segnale) da mark_px (prezzo corrente al momento del log); finché il campo è ambiguo ogni post-mortem futuro è invalido indipendentemente dalla direzione del mercato. #logging_bug #exit_px_mismatch #timestamp_race_condition #paper_trading_accounting #tsmom_liq #data_quality
- **execution_issue** (WLD, $-61.31): Su token illiquidi ad alta volatilità (WLD-class), uno stop fisso al 2.5% rientra nel rumore di breve periodo: il trade è stato stoppato in 12h su movimento di ~1.7bp dal close. Gli stop devono essere calibrati sull'ATR dell'asset specifico (minimo 1×ATR daily), non su una percentuale flat derivata da asset più liquidi come BTC/ETH — altrimenti il segnale corretto viene annullato da volatilità casuale prima che la tesi possa esprimersi. #stop-sizing #atr-calibration #illiquid-altcoin #tsmom #noise-stop
- **thesis_wrong** (CRV, $-60.24): tsmom+liq_imbalance=1 su governance DeFi token con distribuzione strutturale (ve-overhang, TVL/fees in calo) cattura un ingresso crowded, non momentum organico: tutti i sistemi sistematici ricevono lo stesso trigger simultaneamente, il liq_imbalance=1 riflette gli ordini degli altri modelli tsmom, non domanda spot genuina, e la mean-reversion avviene entro 12-24h prima che la tesi si dispieghi. Regola generale: su DeFi governance token, esigere tsmom positivo su lookback ≥30g (non solo 7g) E conferma che il ratio DeFi-sector/BTC sia in uptrend settimanale prima di considerare liq_imbalance una conferma valida. #tsmom #defi_governance_token #crowded_entry #structural_decline #regime_filter #ve_overhang #false_signal

[[lessons|Tutte le lezioni]] · [[timeline|Timeline]]
