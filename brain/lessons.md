# Lezioni

[[README|← Brain index]]

_35 lezioni, clusterizzate per tag._

## #3:1_rr

- [[tsmom-conservative-v1]] · **thesis_right** (xyz_CL): Un segnale tsmom = -1 su futures energetici liquidi in trend ribassista porta il prezzo al target 3:1 entro 3-5 sessioni; non intervenire discrezionalmente sul target meccanico — l'edge della strategia si realizza lasciando girare il winner fino al livello stabilito.

## #BTC

- [[tsmom-v1]] · **thesis_wrong** (BTC): Un segnale TSMOM short su BTC dopo un drawdown multi-giorno tende a coincidere con l'esaurimento del momentum ribassista, non con la sua accelerazione. Prima di entrare short su TSMOM in contesti di alta volatilità, esigere conferma strutturale (es. incapacità di rimbalzo su daily close o break di supporto volumetrico) per distinguere trend in atto da momentum già consumato.

## #SOL

- [[agents-v1]] · **execution_issue** (SOL): Un time-stop di 24h è strutturalmente incoerente con una tesi basata su rotazione di capitale a 7 giorni e catalizzatori macro (Iran/BOJ): il regime bull e il funding negativo non erano stati invalidati, il prezzo è uscito piatto (−0.16%) non perché la tesi fosse sbagliata ma perché la finestra di holding era troppo corta per far emergere l'edge. Regola generale: il time-stop deve essere ≥ metà del lookback usato per costruire la tesi — tesi su momentum 7d → time-stop minimo 72-96h; altrimenti si vende rumore intraday su una tesi strutturale.

## #ZEC

- [[tsmom-liq-v1]] · **thesis_wrong** (ZEC): In fasi di downtrend strutturale su altcoin ad alta beta (ZEC), segnali tsmom+liq_imbalance rialzisti catturano spesso picchi di crowding long piuttosto che momentum genuino: il segnale si accende quando tutti sono già entrati, non quando inizia la spinta. Richiedere un regime-filter esplicito (es. BTC price > MA20 o rolling-Sharpe basket > 0) prima di approvare long su tsmom in altcoin.

## #alt_l1

- [[tsmom-liq-v1]] · **thesis_right** (NEAR): Quando tsmom e liq_imbalance convergono entrambi a +1 (signal_vote pieno), il trade ha sufficiente conviction per giustificare R:R ≥ 3:1 con target fisso: uscire anticipatamente o ridurre il target per 'sicurezza' sarebbe stato un errore atteso-negativo. La confluenza momentum + order-flow su alt-L1 genera move intraday completi — non scalare out prima del target.

## #altcoin

- [[tsmom-liq-v1]] · **thesis_wrong** (WLD): segnali tsmom+liq_imbalance su token narrativi a bassa capitalizzazione catturano spesso momentum di brevissimo termine (spike di liquidità) che si esaurisce entro poche candele: senza un filtro di regime (BTC sopra MA su H4, settore AI/L1 in risk-on) il segnale long su altcoin volatili ha tasso di falsi positivi strutturalmente alto e va ridotto in size o saltato

## #altcoin-beta

- [[tsmom-liq-v1]] · **thesis_wrong** (ZEC): In fasi di downtrend strutturale su altcoin ad alta beta (ZEC), segnali tsmom+liq_imbalance rialzisti catturano spesso picchi di crowding long piuttosto che momentum genuino: il segnale si accende quando tutti sono già entrati, non quando inizia la spinta. Richiedere un regime-filter esplicito (es. BTC price > MA20 o rolling-Sharpe basket > 0) prima di approvare long su tsmom in altcoin.

## #altcoin-exhaustion

- [[agents-v1]] · **thesis_wrong** (ZEC): Doppia confluenza tsmom+vwap_zscore su candele già estese segna esaurimento, non continuazione: quando la tesi stessa riconosce il crowding e risponde solo con size ridotta, il segnale qualitativo deve essere invertito. Crowding consapevole + momentum tardivo post-rally = peso contrarian implicito ignorato. La size al 50% mitiga la perdita ma non cambia il segno dell'edge atteso. Regola generale: se la tesi contiene 'il rischio X è reale ma lo gestisco con Y', X è probabilmente la causa principale del fallimento e Y è razionalizzazione.

## #altcoin_high_beta

- [[agents-v1]] · **thesis_wrong** (SUI): Un vwap_zscore=1 (1σ) in altcoin ad alta beta è sotto la soglia minima di edge: il rapporto segnale/rumore è insufficiente a sopravvivere alla normale volatilità intraday senza un catalizzatore strutturale aggiuntivo (volume >1.5x media 4h o zscore ≥1.5). La relative strength intraday punto-in-tempo (+2.8%) non è una proxy affidabile di momentum sostenuto se non è confermata da espansione volumetrica nel tick successivo all'ingresso — senza follow-through misurato entro 2h, il segnale va trattato come rumore e il trade chiuso in pareggio.

## #altcoin_noise

- [[tsmom-liq-v1]] · **execution_issue** (NEAR): Quando tsmom + liq_imbalance si allineano su altcoin ad alta beta (NEAR, SOL-tier), uno stop fisso <3% viene consumato dal rumore intraday prima che il momentum si materializzi: il minimo stop deve essere ≥1.5× ATR daily del simbolo; in alternativa ridurre la size proporzionalmente per mantenere il risk assoluto costante con uno stop più largo.

## #altcoin_volatility

- [[tsmom-liq-v1]] · **execution_issue** (ZEC): Doppio segnale confluente (tsmom+liq entrambi=1) su un alt ad alta volatilità segnala potenziale entry affollato: molti sistemi sistematici ricevono lo stesso trigger simultaneamente, e uno stop fisso al 2.5% viene colpito dal noise di mean-reversion prima che la tesi si dispieghi. Regola generale: su alt con ATR/day ≥ 3%, calibrare lo stop a 1× ATR(14) e ridurre la size proporzionalmente; in alternativa, attendere un micro-pullback dal primo tick di segnale per entry meno denso.
- [[tsmom-liq-v1]] · **execution_issue** (WLD): Su altcoin ad alta volatilità (WLD, float basso), uno stop fisso %-based ignora l'ATR del timeframe: un'oscillazione di 2.5% in 1h è rumore ordinario, non invalidazione della tesi. I segnali tsmom+liq_imbalance erano coerenti ma lo stop è stato piazzato dentro il noise-band — regola: stop su tsmom-liq entries deve essere ≥1× ATR(4h) per sopravvivere al mean-reversion intra-candle senza che la tesi direzionale venga falsificata.

## #asset-class

- [[commodities-trend-v1]] · **thesis_wrong** (basket): Specializzazione per asset-class: TSMOM sulle SOLE commodities (Sharpe 0.43) NON batte buy-and-hold (-0.70 vs B&H) — nel periodo le commodities sono semplicemente salite, holding vince. Il basket MISTO resta superiore: la diversificazione cross-asset del trend-following e' parte dell'edge, non un dettaglio. crypto-trend-flow batte il B&H crypto ma con Sharpe assoluto debole (0.33).

## #atr-calibration

- [[tsmom-liq-v1]] · **execution_issue** (WLD): Su token illiquidi ad alta volatilità (WLD-class), uno stop fisso al 2.5% rientra nel rumore di breve periodo: il trade è stato stoppato in 12h su movimento di ~1.7bp dal close. Gli stop devono essere calibrati sull'ATR dell'asset specifico (minimo 1×ATR daily), non su una percentuale flat derivata da asset più liquidi come BTC/ETH — altrimenti il segnale corretto viene annullato da volatilità casuale prima che la tesi possa esprimersi.

## #atr-mismatch

- [[tsmom-liq-v1]] · **execution_issue** (WLD): Un segnale tsmom è per definizione costruito su finestre giornaliere (o multi-ora): lo stop deve essere ≥ 1× ATR-giornaliero del sottostante, altrimenti il rumore intraday esaurisce il margine prima che la tesi si materializzi. WLD ha ATR-daily ~5-8%; uno stop al 2.5% sotto l'entry entra direttamente nella fascia di rumore e viene colpito statisticamente anche quando la direzione è corretta. Regola generale: su strategie momentum a bassa frequenza, calibra lo stop sul timeframe del segnale (daily ATR), non sulla tolleranza di rischio in USD — aggiusta il size per tenere il rischio fisso, non restringere lo stop.

## #atr_calibration

- [[tsmom-liq-v1]] · **execution_issue** (XRP): Quando tsmom e liq_imbalance convergono (-1/-1) il segnale è solido, ma su asset ad alta volatilità intraday (XRP, ATR giornaliero > 3%) uno stop a ~2.5% cade dentro la banda di rumore e non fuori dalla tesi. Gli stop di momentum-liq vanno calibrati su 1.5-2x ATR del timeframe del segnale, non su una percentuale fissa: altrimenti ogni rimbalzo tecnico di 5h elimina il trade prima che la direzionalità si esprima.
- [[tsmom-liq-v1]] · **execution_issue** (ZEC): Doppio segnale confluente (tsmom+liq entrambi=1) su un alt ad alta volatilità segnala potenziale entry affollato: molti sistemi sistematici ricevono lo stesso trigger simultaneamente, e uno stop fisso al 2.5% viene colpito dal noise di mean-reversion prima che la tesi si dispieghi. Regola generale: su alt con ATR/day ≥ 3%, calibrare lo stop a 1× ATR(14) e ridurre la size proporzionalmente; in alternativa, attendere un micro-pullback dal primo tick di segnale per entry meno denso.
- [[tsmom-liq-v1]] · **execution_issue** (WLD): Su altcoin ad alta volatilità (WLD, float basso), uno stop fisso %-based ignora l'ATR del timeframe: un'oscillazione di 2.5% in 1h è rumore ordinario, non invalidazione della tesi. I segnali tsmom+liq_imbalance erano coerenti ma lo stop è stato piazzato dentro il noise-band — regola: stop su tsmom-liq entries deve essere ≥1× ATR(4h) per sopravvivere al mean-reversion intra-candle senza che la tesi direzionale venga falsificata.

## #atr_sizing

- [[tsmom-liq-v1]] · **execution_issue** (NEAR): Quando tsmom + liq_imbalance si allineano su altcoin ad alta beta (NEAR, SOL-tier), uno stop fisso <3% viene consumato dal rumore intraday prima che il momentum si materializzi: il minimo stop deve essere ≥1.5× ATR daily del simbolo; in alternativa ridurre la size proporzionalmente per mantenere il risk assoluto costante con uno stop più largo.

## #basket_relative_strength

- [[agents-v1]] · **thesis_right** (SOL): Funding negativo strutturale su asset con regime bull confermato e outperformance spot vs paniere crea uno squeeze lento ma prevedibile: i derivati fungono da carburante direzionale anziché da resistenza. La confluenza funding-negativo + spot-outperformance-vs-basket è un setup ad alto valore con invalidazione netta e misurabile (funding flip), replicabile su qualsiasi perpetual liquido indipendentemente dall'asset specifico.

## #basket_selection

- [[agents-v1]] · **thesis_right** (ZEC): Vol compression su un asset già in bull regime primario è un setup asimmetrico: il regime trasforma un pattern neutro in un entry direzionale ad alta probabilità. La selezione per regime nel basket (1/5 in bull vs 4/5 in chop) è il filtro che converte il segnale tecnico in edge — senza quel filtro lo stesso setup su un asset in chop non avrebbe la stessa aspettativa. Generalizzazione: quando si fa basket selection, cercare il regime outlier positivo e concentrare la posizione lì, non diversificare su tutti i segnali.

## #bear-regime

- [[agents-v1]] · **thesis_wrong** (ZEC): Fade contro trend (squeeze su crowding) dopo un +5% giornaliero = comprare il rimbalzo gia esteso. In bear regime l'entry squeeze richiede conferma (retest del breakout o capitolazione OI), non anticipazione. Conferma la lezione gen1-3 del loop evolutivo: il crowding da solo non basta contro il trend.

## #bear_regime

- [[tsmom-liq-v1]] · **execution_issue** (CRV): Segnali tsmom+liq_imbalance su token DeFi small-cap richiedono un filtro di regime esplicito: in mercato bear/laterale, gli squilibri di liquidità su CRV-class asset sono noise e non segnale direzionale — long momentum senza conferma macro (es. BTC sopra EMA breve o realized-vol sotto soglia) producono whipsaw sistematici il cui stop-rate supera l'alpha atteso del setup.

## #bull_regime

- [[agents-v1]] · **thesis_right** (ZEC): Vol compression su un asset già in bull regime primario è un setup asimmetrico: il regime trasforma un pattern neutro in un entry direzionale ad alta probabilità. La selezione per regime nel basket (1/5 in bull vs 4/5 in chop) è il filtro che converte il segnale tecnico in edge — senza quel filtro lo stesso setup su un asset in chop non avrebbe la stessa aspettativa. Generalizzazione: quando si fa basket selection, cercare il regime outlier positivo e concentrare la posizione lì, non diversificare su tutti i segnali.
- [[agents-v1]] · **thesis_right** (SOL): Funding negativo strutturale su asset con regime bull confermato e outperformance spot vs paniere crea uno squeeze lento ma prevedibile: i derivati fungono da carburante direzionale anziché da resistenza. La confluenza funding-negativo + spot-outperformance-vs-basket è un setup ad alto valore con invalidazione netta e misurabile (funding flip), replicabile su qualsiasi perpetual liquido indipendentemente dall'asset specifico.

## #commodities

- [[commodities-cot-trend-v1]] · **thesis_wrong** (basket): Ipotesi 'TSMOM commodities confermato da posizionamento COT estremo' FALSIFICATA: il filtro COT peggiora lo Sharpe (da 0.43 a -0.10). Il posizionamento estremo dei fondi non e' conferma del trend ma semmai segnale di esaurimento — coerente col fatto che restringe gli ingressi proprio quando il crowd e' gia' dentro. COT resta segnale nel registry ma non come conferma di trend.

## #commodity

- [[tsmom-conservative-v1]] · **thesis_right** (xyz_CL): Un segnale tsmom = -1 su futures energetici liquidi in trend ribassista porta il prezzo al target 3:1 entro 3-5 sessioni; non intervenire discrezionalmente sul target meccanico — l'edge della strategia si realizza lasciando girare il winner fino al livello stabilito.

## #conferma

- [[tsmom-v1]] · **thesis_right** (basket): TSMOM (7g+30g concordi, exit posizionali) conferma la letteratura: Sharpe medio 1.69, 8/9 asset positivi su basket misto. I segnali universali OHLCV viaggiano cross-asset; funding/flow restano additivi solo su crypto. Nota: consistenza per fold bassa (25/54) - tipico del trend following, guadagna a strappi nei trend e resta piatto nel chop.
- [[tsmom-conservative-v1]] · **thesis_right** (basket): Ricerca profili di rischio su TSMOM: il profilo CONSERVATIVO (leva 1x, stop 2.5%, 2 posizioni) domina il base e l'aggressivo: stesso Sharpe (1.70) ma drawdown dimezzato (-9.8% vs -15%+). L'aggressivo (leva 2x, stop 6%) FALSIFICATO: Sharpe 1.56 sotto buy-and-hold, piu' rischio senza reward. Lezione: su trend-following il controllo del rischio batte la ricerca di rendimento. tsmom-conservative -> challenger in paper.

## #cot

- [[commodities-cot-trend-v1]] · **thesis_wrong** (basket): Ipotesi 'TSMOM commodities confermato da posizionamento COT estremo' FALSIFICATA: il filtro COT peggiora lo Sharpe (da 0.43 a -0.10). Il posizionamento estremo dei fondi non e' conferma del trend ma semmai segnale di esaurimento — coerente col fatto che restringe gli ingressi proprio quando il crowd e' gia' dentro. COT resta segnale nel registry ma non come conferma di trend.

## #counter-trend

- [[agents-v1]] · **thesis_wrong** (ZEC): Fade contro trend (squeeze su crowding) dopo un +5% giornaliero = comprare il rimbalzo gia esteso. In bear regime l'entry squeeze richiede conferma (retest del breakout o capitolazione OI), non anticipazione. Conferma la lezione gen1-3 del loop evolutivo: il crowding da solo non basta contro il trend.

## #cross-asset

- [[tsmom-v1]] · **thesis_right** (basket): TSMOM (7g+30g concordi, exit posizionali) conferma la letteratura: Sharpe medio 1.69, 8/9 asset positivi su basket misto. I segnali universali OHLCV viaggiano cross-asset; funding/flow restano additivi solo su crypto. Nota: consistenza per fold bassa (25/54) - tipico del trend following, guadagna a strappi nei trend e resta piatto nel chop.

## #crowded_entry

- [[tsmom-liq-v1]] · **execution_issue** (ZEC): Doppio segnale confluente (tsmom+liq entrambi=1) su un alt ad alta volatilità segnala potenziale entry affollato: molti sistemi sistematici ricevono lo stesso trigger simultaneamente, e uno stop fisso al 2.5% viene colpito dal noise di mean-reversion prima che la tesi si dispieghi. Regola generale: su alt con ATR/day ≥ 3%, calibrare lo stop a 1× ATR(14) e ridurre la size proporzionalmente; in alternativa, attendere un micro-pullback dal primo tick di segnale per entry meno denso.
- [[tsmom-liq-v1]] · **thesis_wrong** (CRV): tsmom+liq_imbalance=1 su governance DeFi token con distribuzione strutturale (ve-overhang, TVL/fees in calo) cattura un ingresso crowded, non momentum organico: tutti i sistemi sistematici ricevono lo stesso trigger simultaneamente, il liq_imbalance=1 riflette gli ordini degli altri modelli tsmom, non domanda spot genuina, e la mean-reversion avviene entro 12-24h prima che la tesi si dispieghi. Regola generale: su DeFi governance token, esigere tsmom positivo su lookback ≥30g (non solo 7g) E conferma che il ratio DeFi-sector/BTC sia in uptrend settimanale prima di considerare liq_imbalance una conferma valida.

## #crowding

- [[agents-v1]] · **thesis_wrong** (ZEC): Doppia confluenza tsmom+vwap_zscore su candele già estese segna esaurimento, non continuazione: quando la tesi stessa riconosce il crowding e risponde solo con size ridotta, il segnale qualitativo deve essere invertito. Crowding consapevole + momentum tardivo post-rally = peso contrarian implicito ignorato. La size al 50% mitiga la perdita ma non cambia il segno dell'edge atteso. Regola generale: se la tesi contiene 'il rischio X è reale ma lo gestisco con Y', X è probabilmente la causa principale del fallimento e Y è razionalizzazione.

## #crowding-exhaustion

- [[agents-v1]] · **thesis_right** (ZEC): Su asset illiquidi (ZEC-tier), la combinazione rally >15% senza catalizzatore fondamentale + primo pullback significativo con funding ancora positivo è un segnale di distribuzione ad alta fedeltà: i longs sono intrappolati e non capitolano, il che concentra la pressione sell sul successivo leg down. Il trade ha raggiunto il target (-12.5%) in 36h su 48h disponibili — conferma che il time-stop va calibrato sul tempo di esaurimento del crowding, non sulla volatilità asset. In regime bear o neutro, questo setup (funding positivo + price action negativa) è più affidabile che il fade di momentum puro perché incorpora informazione di positioning.

## #crowding-peak

- [[tsmom-liq-v1]] · **thesis_wrong** (ZEC): In fasi di downtrend strutturale su altcoin ad alta beta (ZEC), segnali tsmom+liq_imbalance rialzisti catturano spesso picchi di crowding long piuttosto che momentum genuino: il segnale si accende quando tutti sono già entrati, non quando inizia la spinta. Richiedere un regime-filter esplicito (es. BTC price > MA20 o rolling-Sharpe basket > 0) prima di approvare long su tsmom in altcoin.

## #crude_oil

- [[tsmom-conservative-v1]] · **thesis_right** (xyz_CL): Un segnale tsmom = -1 su futures energetici liquidi in trend ribassista porta il prezzo al target 3:1 entro 3-5 sessioni; non intervenire discrezionalmente sul target meccanico — l'edge della strategia si realizza lasciando girare il winner fino al livello stabilito.

## #crypto-momentum

- [[tsmom-liq-v1]] · **execution_issue** (WLD): Un segnale tsmom è per definizione costruito su finestre giornaliere (o multi-ora): lo stop deve essere ≥ 1× ATR-giornaliero del sottostante, altrimenti il rumore intraday esaurisce il margine prima che la tesi si materializzi. WLD ha ATR-daily ~5-8%; uno stop al 2.5% sotto l'entry entra direttamente nella fascia di rumore e viene colpito statisticamente anche quando la direzione è corretta. Regola generale: su strategie momentum a bassa frequenza, calibra lo stop sul timeframe del segnale (daily ATR), non sulla tolleranza di rischio in USD — aggiusta il size per tenere il rischio fisso, non restringere lo stop.

## #data-integrity

- [[tsmom-liq-v1]] · **execution_issue** (NEAR): Exit price (2.2725) è sotto entry (2.3664) su un long, ma PnL registrato è +$178. Inoltre ts_close (02:00) precede opened_at (04:00) di 2 ore. Il record è strutturalmente corrotto: il sistema deve validare sign(exit_px - entry_px) == sign(pnl_usd) per i long e ts_close > ts_open prima di persistere su journal — ogni post-mortem su dati incoerenti produce lezioni spurie e degrada il backtest.

## #data_quality

- [[tsmom-liq-v1]] · **execution_issue** (WLD): Il PnL (+$174.63 su $2390.57 = 7.3%) è coerente con un fill al target (0.7286, +7.5%) ma exit_px registra 0.6872 (+1.4%) — discrepanza ~5x: il logger sta scrivendo il mark price al momento del log invece del fill price simulato. Aggravante: close.logged_at (20:16) precede open.logged_at (21:15) e open_ts == close_ts (stesso candle), indicando race condition nel pipeline. In paper trading, separare rigorosamente fill_px (prezzo di esecuzione deterministico, fissato all'istante del segnale) da mark_px (prezzo corrente al momento del log); finché il campo è ambiguo ogni post-mortem futuro è invalido indipendentemente dalla direzione del mercato.

## #defi_crowding

- [[tsmom-liq-v1]] · **thesis_wrong** (CRV): tsmom + liq_imbalance simultanei su token DeFi (bassa cap, alto crowding) possono riflettere momentum già esaurito al momento del segnale — non un'accelerazione in corso. Regola generale: in regime neutro/bear su BTC, esigere N ore di persistenza del segnale (es. 2+ candle di conferma) e coerenza col trend ETH prima di entrare long su DeFi; un segnale intracandle fermato in <1h indica che la liq_imbalance era noise temporaneo, non pressione direzionale sostenuta.

## #defi_governance_token

- [[tsmom-liq-v1]] · **thesis_wrong** (CRV): tsmom+liq_imbalance=1 su governance DeFi token con distribuzione strutturale (ve-overhang, TVL/fees in calo) cattura un ingresso crowded, non momentum organico: tutti i sistemi sistematici ricevono lo stesso trigger simultaneamente, il liq_imbalance=1 riflette gli ordini degli altri modelli tsmom, non domanda spot genuina, e la mean-reversion avviene entro 12-24h prima che la tesi si dispieghi. Regola generale: su DeFi governance token, esigere tsmom positivo su lookback ≥30g (non solo 7g) E conferma che il ratio DeFi-sector/BTC sia in uptrend settimanale prima di considerare liq_imbalance una conferma valida.

## #defi_small_cap

- [[tsmom-liq-v1]] · **execution_issue** (CRV): Segnali tsmom+liq_imbalance su token DeFi small-cap richiedono un filtro di regime esplicito: in mercato bear/laterale, gli squilibri di liquidità su CRV-class asset sono noise e non segnale direzionale — long momentum senza conferma macro (es. BTC sopra EMA breve o realized-vol sotto soglia) producono whipsaw sistematici il cui stop-rate supera l'alpha atteso del setup.

## #derivatives_confluence

- [[agents-v1]] · **thesis_right** (SOL): Funding negativo strutturale su asset con regime bull confermato e outperformance spot vs paniere crea uno squeeze lento ma prevedibile: i derivati fungono da carburante direzionale anziché da resistenza. La confluenza funding-negativo + spot-outperformance-vs-basket è un setup ad alto valore con invalidazione netta e misurabile (funding flip), replicabile su qualsiasi perpetual liquido indipendentemente dall'asset specifico.

## #distribution

- [[agents-v1]] · **thesis_right** (ZEC): Su asset illiquidi (ZEC-tier), la combinazione rally >15% senza catalizzatore fondamentale + primo pullback significativo con funding ancora positivo è un segnale di distribuzione ad alta fedeltà: i longs sono intrappolati e non capitolano, il che concentra la pressione sell sul successivo leg down. Il trade ha raggiunto il target (-12.5%) in 36h su 48h disponibili — conferma che il time-stop va calibrato sul tempo di esaurimento del crowding, non sulla volatilità asset. In regime bear o neutro, questo setup (funding positivo + price action negativa) è più affidabile che il fade di momentum puro perché incorpora informazione di positioning.

## #diversification

- [[commodities-trend-v1]] · **thesis_wrong** (basket): Specializzazione per asset-class: TSMOM sulle SOLE commodities (Sharpe 0.43) NON batte buy-and-hold (-0.70 vs B&H) — nel periodo le commodities sono semplicemente salite, holding vince. Il basket MISTO resta superiore: la diversificazione cross-asset del trend-following e' parte dell'edge, non un dettaglio. crypto-trend-flow batte il B&H crypto ma con Sharpe assoluto debole (0.33).

## #entry_filter

- [[agents-v1]] · **thesis_wrong** (SUI): Un vwap_zscore=1 (1σ) in altcoin ad alta beta è sotto la soglia minima di edge: il rapporto segnale/rumore è insufficiente a sopravvivere alla normale volatilità intraday senza un catalizzatore strutturale aggiuntivo (volume >1.5x media 4h o zscore ≥1.5). La relative strength intraday punto-in-tempo (+2.8%) non è una proxy affidabile di momentum sostenuto se non è confermata da espansione volumetrica nel tick successivo all'ingresso — senza follow-through misurato entro 2h, il segnale va trattato come rumore e il trade chiuso in pareggio.

## #entry_timing

- [[tsmom-v1]] · **thesis_wrong** (BTC): Un segnale TSMOM short su BTC dopo un drawdown multi-giorno tende a coincidere con l'esaurimento del momentum ribassista, non con la sua accelerazione. Prima di entrare short su TSMOM in contesti di alta volatilità, esigere conferma strutturale (es. incapacità di rimbalzo su daily close o break di supporto volumetrico) per distinguere trend in atto da momentum già consumato.
- [[tsmom-liq-v1]] · **thesis_wrong** (CRV): tsmom + liq_imbalance simultanei su token DeFi (bassa cap, alto crowding) possono riflettere momentum già esaurito al momento del segnale — non un'accelerazione in corso. Regola generale: in regime neutro/bear su BTC, esigere N ore di persistenza del segnale (es. 2+ candle di conferma) e coerenza col trend ETH prima di entrare long su DeFi; un segnale intracandle fermato in <1h indica che la liq_imbalance era noise temporaneo, non pressione direzionale sostenuta.

## #event-study

- [[news-event]] · **thesis_wrong** (basket): Event study su 48 eventi GDELT (12 mesi, 5 topic) falsifica la strategia news-driven DIREZIONALE: tone_hit medio 0.38 (sotto il caso 0.50) - il tono della notizia NON predice la direzione del prezzo. Su 252 combinazioni asset/topic/orizzonte, solo 1 ha |t|>=2 E tono predittivo (ne attenderei ~12 per puro caso). I t-stat alti (LIT/VVV/HYPE +8/12%) sono microcap illiquidi: mean_ret=mean_abs_ret = trend del token, non reazione all'evento. Cosa resta vero: sui liquidi (BTC/ETH) gli eventi geopolitici creano volatilita reale (t~2.8) ma cieca sulla direzione. Riconversione: news_event da segnale direzionale a GATE DI RISCHIO (riduci size/sospendi entrate durante burst news).

## #execution

- [[agents-v1]] · **execution_issue** (ZEC): Lo stop deve coincidere con l'invalidazione dichiarata della tesi, mai essere piu stretto: qui stop 418 vs invalidazione 415 - usciti prima che la tesi morisse. Se lo stop coerente rende il rischio troppo grande, ridurre la size, non stringere lo stop.
- [[tsmom-liq-v1]] · **execution_issue** (ZEC): Doppio segnale confluente (tsmom+liq entrambi=1) su un alt ad alta volatilità segnala potenziale entry affollato: molti sistemi sistematici ricevono lo stesso trigger simultaneamente, e uno stop fisso al 2.5% viene colpito dal noise di mean-reversion prima che la tesi si dispieghi. Regola generale: su alt con ATR/day ≥ 3%, calibrare lo stop a 1× ATR(14) e ridurre la size proporzionalmente; in alternativa, attendere un micro-pullback dal primo tick di segnale per entry meno denso.

## #execution-bug

- [[tsmom-conservative-v1]] · **execution_issue** (xyz_GOLD): Se close.logged_at precede open.logged_at sulla stessa barra-timestamp, il motore valuta lo stop prima della conferma dell'ingresso (look-ahead intra-barra): la perdita non riflette un movimento di mercato reale. Fix strutturale: aggiungere guard min_hold_bars>=1 nel loop di stop affinché la logica di uscita venga saltata sulla barra di apertura. In parallelo, il pattern GOLD (4204→4231→4348 in 3 giorni, tsmom=-1 persistente) evidenzia che segnali TSMOM short su safe-haven in regime di bid strutturale generano whipsaw sistematici: filtrare gli short su gold/xau con un proxy di risk-appetite (es. VIX regime o spread TY-bund) prima dell'ingresso.

## #execution_mismatch

- [[agents-v1]] · **execution_issue** (SOL): Funding negativo mite (−0.25% APR ≈ rumore neutro) non genera squeeze meccanico materiale: la pressione di auto-liquidazione diventa concreta solo sotto −1% APR o quando il gradiente di funding accelera verso neutro (≥0.05% APR/h nelle ultime 4h). Un time-stop da 12h è incongruente con una tesi di compressione funding lenta: o si entra solo quando la compressione è già in corso (momentum del funding, non livello), oppure si estende il time-stop a ≥24h dimezzando la size. Il volume_surge era un segnale direzionale valido, ma non è un proxy del timing dello squeeze.

## #exit_px_mismatch

- [[tsmom-liq-v1]] · **execution_issue** (WLD): Il PnL (+$174.63 su $2390.57 = 7.3%) è coerente con un fill al target (0.7286, +7.5%) ma exit_px registra 0.6872 (+1.4%) — discrepanza ~5x: il logger sta scrivendo il mark price al momento del log invece del fill price simulato. Aggravante: close.logged_at (20:16) precede open.logged_at (21:15) e open_ts == close_ts (stesso candle), indicando race condition nel pipeline. In paper trading, separare rigorosamente fill_px (prezzo di esecuzione deterministico, fissato all'istante del segnale) da mark_px (prezzo corrente al momento del log); finché il campo è ambiguo ogni post-mortem futuro è invalido indipendentemente dalla direzione del mercato.

## #false-momentum

- [[tsmom-liq-v1]] · **thesis_wrong** (ZEC): In fasi di downtrend strutturale su altcoin ad alta beta (ZEC), segnali tsmom+liq_imbalance rialzisti catturano spesso picchi di crowding long piuttosto che momentum genuino: il segnale si accende quando tutti sono già entrati, non quando inizia la spinta. Richiedere un regime-filter esplicito (es. BTC price > MA20 o rolling-Sharpe basket > 0) prima di approvare long su tsmom in altcoin.

## #false_positive

- [[tsmom-liq-v1]] · **thesis_wrong** (WLD): segnali tsmom+liq_imbalance su token narrativi a bassa capitalizzazione catturano spesso momentum di brevissimo termine (spike di liquidità) che si esaurisce entro poche candele: senza un filtro di regime (BTC sopra MA su H4, settore AI/L1 in risk-on) il segnale long su altcoin volatili ha tasso di falsi positivi strutturalmente alto e va ridotto in size o saltato

## #false_signal

- [[tsmom-v1]] · **thesis_wrong** (xyz_GOLD): Un segnale tsmom=-1 su un asset con forte tailwind macro (oro in regime risk-off / dollaro debole) ha edge vicino a zero: il momentum di breve periodo è rumore rispetto al flusso dominante. I segnali tsmom short su safe-haven richiedono un filtro regime (es. dollaro in trend rialzista O risk appetite positivo) prima di entrare — senza conferma macro, il fade è contro la corrente più forte.
- [[tsmom-liq-v1]] · **thesis_wrong** (CRV): tsmom+liq_imbalance=1 su governance DeFi token con distribuzione strutturale (ve-overhang, TVL/fees in calo) cattura un ingresso crowded, non momentum organico: tutti i sistemi sistematici ricevono lo stesso trigger simultaneamente, il liq_imbalance=1 riflette gli ordini degli altri modelli tsmom, non domanda spot genuina, e la mean-reversion avviene entro 12-24h prima che la tesi si dispieghi. Regola generale: su DeFi governance token, esigere tsmom positivo su lookback ≥30g (non solo 7g) E conferma che il ratio DeFi-sector/BTC sia in uptrend settimanale prima di considerare liq_imbalance una conferma valida.

## #falsificazione

- [[vwap-reversion-v1]] · **thesis_wrong** (basket): Fade dell'estensione VWAP falsificato 7/7 asset (crypto+commodities+stock): le estensioni oltre 2 sigma IN QUESTO regime sono trend, non esaurimenti. Terza falsificazione consecutiva di tesi mean-reversion (dopo scalp-exit e flow-fade): il regime 2026 H1 premia il trend following, punisce il contrarian.
- [[news-event]] · **thesis_wrong** (basket): Event study su 48 eventi GDELT (12 mesi, 5 topic) falsifica la strategia news-driven DIREZIONALE: tone_hit medio 0.38 (sotto il caso 0.50) - il tono della notizia NON predice la direzione del prezzo. Su 252 combinazioni asset/topic/orizzonte, solo 1 ha |t|>=2 E tono predittivo (ne attenderei ~12 per puro caso). I t-stat alti (LIT/VVV/HYPE +8/12%) sono microcap illiquidi: mean_ret=mean_abs_ret = trend del token, non reazione all'evento. Cosa resta vero: sui liquidi (BTC/ETH) gli eventi geopolitici creano volatilita reale (t~2.8) ma cieca sulla direzione. Riconversione: news_event da segnale direzionale a GATE DI RISCHIO (riduci size/sospendi entrate durante burst news).
- [[commodities-cot-trend-v1]] · **thesis_wrong** (basket): Ipotesi 'TSMOM commodities confermato da posizionamento COT estremo' FALSIFICATA: il filtro COT peggiora lo Sharpe (da 0.43 a -0.10). Il posizionamento estremo dei fondi non e' conferma del trend ma semmai segnale di esaurimento — coerente col fatto che restringe gli ingressi proprio quando il crowd e' gia' dentro. COT resta segnale nel registry ma non come conferma di trend.
- [[commodities-trend-v1]] · **thesis_wrong** (basket): Specializzazione per asset-class: TSMOM sulle SOLE commodities (Sharpe 0.43) NON batte buy-and-hold (-0.70 vs B&H) — nel periodo le commodities sono semplicemente salite, holding vince. Il basket MISTO resta superiore: la diversificazione cross-asset del trend-following e' parte dell'edge, non un dettaglio. crypto-trend-flow batte il B&H crypto ma con Sharpe assoluto debole (0.33).

## #full_target

- [[tsmom-liq-v1]] · **thesis_right** (NEAR): Quando tsmom e liq_imbalance convergono entrambi a +1 (signal_vote pieno), il trade ha sufficiente conviction per giustificare R:R ≥ 3:1 con target fisso: uscire anticipatamente o ridurre il target per 'sicurezza' sarebbe stato un errore atteso-negativo. La confluenza momentum + order-flow su alt-L1 genera move intraday completi — non scalare out prima del target.

## #funding-signal

- [[agents-v1]] · **thesis_right** (ZEC): Su asset illiquidi (ZEC-tier), la combinazione rally >15% senza catalizzatore fondamentale + primo pullback significativo con funding ancora positivo è un segnale di distribuzione ad alta fedeltà: i longs sono intrappolati e non capitolano, il che concentra la pressione sell sul successivo leg down. Il trade ha raggiunto il target (-12.5%) in 36h su 48h disponibili — conferma che il time-stop va calibrato sul tempo di esaurimento del crowding, non sulla volatilità asset. In regime bear o neutro, questo setup (funding positivo + price action negativa) è più affidabile che il fade di momentum puro perché incorpora informazione di positioning.

## #funding_squeeze

- [[agents-v1]] · **execution_issue** (SUI): Vol_compression + funding-squeeze long su L1 altcoin consegna tipicamente 3-7% di reversion intra-giornaliera, non 18%: quando il catalizzatore è 'esaurimento pressione ribassista' (non breakout macro), il target deve essere calibrato sulla magnitudine attesa dello squeeze (R:R compresso ma alta probabilità) e il time_stop deve essere proporzionato — 48h è coerente con la tesi, ma abbinarlo a un target x3 crea un'asimmetria impossibile: il trade chiude a time_stop catturando solo il 30% del premio atteso. Separare il sizing del target in base al tipo di driver: squeeze → target 5-8%, breakout strutturale → target 15%+.
- [[agents-v1]] · **execution_issue** (SOL): Funding negativo mite (−0.25% APR ≈ rumore neutro) non genera squeeze meccanico materiale: la pressione di auto-liquidazione diventa concreta solo sotto −1% APR o quando il gradiente di funding accelera verso neutro (≥0.05% APR/h nelle ultime 4h). Un time-stop da 12h è incongruente con una tesi di compressione funding lenta: o si entra solo quando la compressione è già in corso (momentum del funding, non livello), oppure si estende il time-stop a ≥24h dimezzando la size. Il volume_surge era un segnale direzionale valido, ma non è un proxy del timing dello squeeze.

## #funding_threshold

- [[agents-v1]] · **execution_issue** (SOL): Funding negativo mite (−0.25% APR ≈ rumore neutro) non genera squeeze meccanico materiale: la pressione di auto-liquidazione diventa concreta solo sotto −1% APR o quando il gradiente di funding accelera verso neutro (≥0.05% APR/h nelle ultime 4h). Un time-stop da 12h è incongruente con una tesi di compressione funding lenta: o si entra solo quando la compressione è già in corso (momentum del funding, non livello), oppure si estende il time-stop a ≥24h dimezzando la size. Il volume_surge era un segnale direzionale valido, ma non è un proxy del timing dello squeeze.

## #gdelt

- [[news-event]] · **thesis_wrong** (basket): Event study su 48 eventi GDELT (12 mesi, 5 topic) falsifica la strategia news-driven DIREZIONALE: tone_hit medio 0.38 (sotto il caso 0.50) - il tono della notizia NON predice la direzione del prezzo. Su 252 combinazioni asset/topic/orizzonte, solo 1 ha |t|>=2 E tono predittivo (ne attenderei ~12 per puro caso). I t-stat alti (LIT/VVV/HYPE +8/12%) sono microcap illiquidi: mean_ret=mean_abs_ret = trend del token, non reazione all'evento. Cosa resta vero: sui liquidi (BTC/ETH) gli eventi geopolitici creano volatilita reale (t~2.8) ma cieca sulla direzione. Riconversione: news_event da segnale direzionale a GATE DI RISCHIO (riduci size/sospendi entrate durante burst news).

## #gold

- [[tsmom-conservative-v1]] · **execution_issue** (xyz_GOLD): Se close.logged_at precede open.logged_at sulla stessa barra-timestamp, il motore valuta lo stop prima della conferma dell'ingresso (look-ahead intra-barra): la perdita non riflette un movimento di mercato reale. Fix strutturale: aggiungere guard min_hold_bars>=1 nel loop di stop affinché la logica di uscita venga saltata sulla barra di apertura. In parallelo, il pattern GOLD (4204→4231→4348 in 3 giorni, tsmom=-1 persistente) evidenzia che segnali TSMOM short su safe-haven in regime di bid strutturale generano whipsaw sistematici: filtrare gli short su gold/xau con un proxy di risk-appetite (es. VIX regime o spread TY-bund) prima dell'ingresso.
- [[tsmom-v1]] · **thesis_wrong** (xyz_GOLD): Un segnale tsmom=-1 su un asset con forte tailwind macro (oro in regime risk-off / dollaro debole) ha edge vicino a zero: il momentum di breve periodo è rumore rispetto al flusso dominante. I segnali tsmom short su safe-haven richiedono un filtro regime (es. dollaro in trend rialzista O risk appetite positivo) prima di entrare — senza conferma macro, il fade è contro la corrente più forte.

## #holding_period_calibration

- [[agents-v1]] · **execution_issue** (SOL): Un time-stop di 24h è strutturalmente incoerente con una tesi basata su rotazione di capitale a 7 giorni e catalizzatori macro (Iran/BOJ): il regime bull e il funding negativo non erano stati invalidati, il prezzo è uscito piatto (−0.16%) non perché la tesi fosse sbagliata ma perché la finestra di holding era troppo corta per far emergere l'edge. Regola generale: il time-stop deve essere ≥ metà del lookback usato per costruire la tesi — tesi su momentum 7d → time-stop minimo 72-96h; altrimenti si vende rumore intraday su una tesi strutturale.

## #illiquid-altcoin

- [[tsmom-liq-v1]] · **execution_issue** (WLD): Su token illiquidi ad alta volatilità (WLD-class), uno stop fisso al 2.5% rientra nel rumore di breve periodo: il trade è stato stoppato in 12h su movimento di ~1.7bp dal close. Gli stop devono essere calibrati sull'ATR dell'asset specifico (minimo 1×ATR daily), non su una percentuale flat derivata da asset più liquidi come BTC/ETH — altrimenti il segnale corretto viene annullato da volatilità casuale prima che la tesi possa esprimersi.

## #illiquid-asset

- [[agents-v1]] · **thesis_right** (ZEC): Su asset illiquidi (ZEC-tier), la combinazione rally >15% senza catalizzatore fondamentale + primo pullback significativo con funding ancora positivo è un segnale di distribuzione ad alta fedeltà: i longs sono intrappolati e non capitolano, il che concentra la pressione sell sul successivo leg down. Il trade ha raggiunto il target (-12.5%) in 36h su 48h disponibili — conferma che il time-stop va calibrato sul tempo di esaurimento del crowding, non sulla volatilità asset. In regime bear o neutro, questo setup (funding positivo + price action negativa) è più affidabile che il fade di momentum puro perché incorpora informazione di positioning.

## #intraday_momentum

- [[tsmom-liq-v1]] · **thesis_right** (NEAR): Quando tsmom e liq_imbalance convergono entrambi a +1 (signal_vote pieno), il trade ha sufficiente conviction per giustificare R:R ≥ 3:1 con target fisso: uscire anticipatamente o ridurre il target per 'sicurezza' sarebbe stato un errore atteso-negativo. La confluenza momentum + order-flow su alt-L1 genera move intraday completi — non scalare out prima del target.

## #invalidation

- [[agents-v1]] · **execution_issue** (ZEC): Lo stop deve coincidere con l'invalidazione dichiarata della tesi, mai essere piu stretto: qui stop 418 vs invalidazione 415 - usciti prima che la tesi morisse. Se lo stop coerente rende il rischio troppo grande, ridurre la size, non stringere lo stop.

## #l1_altcoin

- [[agents-v1]] · **execution_issue** (SUI): Vol_compression + funding-squeeze long su L1 altcoin consegna tipicamente 3-7% di reversion intra-giornaliera, non 18%: quando il catalizzatore è 'esaurimento pressione ribassista' (non breakout macro), il target deve essere calibrato sulla magnitudine attesa dello squeeze (R:R compresso ma alta probabilità) e il time_stop deve essere proporzionato — 48h è coerente con la tesi, ma abbinarlo a un target x3 crea un'asimmetria impossibile: il trade chiude a time_stop catturando solo il 30% del premio atteso. Separare il sizing del target in base al tipo di driver: squeeze → target 5-8%, breakout strutturale → target 15%+.

## #liq_imbalance

- [[tsmom-liq-v1]] · **thesis_right** (NEAR): Quando tsmom e liq_imbalance convergono entrambi a +1 (signal_vote pieno), il trade ha sufficiente conviction per giustificare R:R ≥ 3:1 con target fisso: uscire anticipatamente o ridurre il target per 'sicurezza' sarebbe stato un errore atteso-negativo. La confluenza momentum + order-flow su alt-L1 genera move intraday completi — non scalare out prima del target.
- [[tsmom-liq-v1]] · **execution_issue** (NEAR): Quando tsmom + liq_imbalance si allineano su altcoin ad alta beta (NEAR, SOL-tier), uno stop fisso <3% viene consumato dal rumore intraday prima che il momentum si materializzi: il minimo stop deve essere ≥1.5× ATR daily del simbolo; in alternativa ridurre la size proporzionalmente per mantenere il risk assoluto costante con uno stop più largo.
- [[tsmom-liq-v1]] · **execution_issue** (CRV): Segnali tsmom+liq_imbalance su token DeFi small-cap richiedono un filtro di regime esplicito: in mercato bear/laterale, gli squilibri di liquidità su CRV-class asset sono noise e non segnale direzionale — long momentum senza conferma macro (es. BTC sopra EMA breve o realized-vol sotto soglia) producono whipsaw sistematici il cui stop-rate supera l'alpha atteso del setup.
- [[tsmom-liq-v1]] · **execution_issue** (WLD): Su altcoin ad alta volatilità (WLD, float basso), uno stop fisso %-based ignora l'ATR del timeframe: un'oscillazione di 2.5% in 1h è rumore ordinario, non invalidazione della tesi. I segnali tsmom+liq_imbalance erano coerenti ma lo stop è stato piazzato dentro il noise-band — regola: stop su tsmom-liq entries deve essere ≥1× ATR(4h) per sopravvivere al mean-reversion intra-candle senza che la tesi direzionale venga falsificata.
- [[tsmom-liq-v1]] · **thesis_wrong** (CRV): tsmom + liq_imbalance simultanei su token DeFi (bassa cap, alto crowding) possono riflettere momentum già esaurito al momento del segnale — non un'accelerazione in corso. Regola generale: in regime neutro/bear su BTC, esigere N ore di persistenza del segnale (es. 2+ candle di conferma) e coerenza col trend ETH prima di entrare long su DeFi; un segnale intracandle fermato in <1h indica che la liq_imbalance era noise temporaneo, non pressione direzionale sostenuta.

## #logging-bug

- [[tsmom-liq-v1]] · **execution_issue** (NEAR): Exit price (2.2725) è sotto entry (2.3664) su un long, ma PnL registrato è +$178. Inoltre ts_close (02:00) precede opened_at (04:00) di 2 ore. Il record è strutturalmente corrotto: il sistema deve validare sign(exit_px - entry_px) == sign(pnl_usd) per i long e ts_close > ts_open prima di persistere su journal — ogni post-mortem su dati incoerenti produce lezioni spurie e degrada il backtest.

## #logging_bug

- [[tsmom-liq-v1]] · **execution_issue** (WLD): Il PnL (+$174.63 su $2390.57 = 7.3%) è coerente con un fill al target (0.7286, +7.5%) ma exit_px registra 0.6872 (+1.4%) — discrepanza ~5x: il logger sta scrivendo il mark price al momento del log invece del fill price simulato. Aggravante: close.logged_at (20:16) precede open.logged_at (21:15) e open_ts == close_ts (stesso candle), indicando race condition nel pipeline. In paper trading, separare rigorosamente fill_px (prezzo di esecuzione deterministico, fissato all'istante del segnale) da mark_px (prezzo corrente al momento del log); finché il campo è ambiguo ogni post-mortem futuro è invalido indipendentemente dalla direzione del mercato.

## #look-ahead

- [[tsmom-conservative-v1]] · **execution_issue** (xyz_GOLD): Se close.logged_at precede open.logged_at sulla stessa barra-timestamp, il motore valuta lo stop prima della conferma dell'ingresso (look-ahead intra-barra): la perdita non riflette un movimento di mercato reale. Fix strutturale: aggiungere guard min_hold_bars>=1 nel loop di stop affinché la logica di uscita venga saltata sulla barra di apertura. In parallelo, il pattern GOLD (4204→4231→4348 in 3 giorni, tsmom=-1 persistente) evidenzia che segnali TSMOM short su safe-haven in regime di bid strutturale generano whipsaw sistematici: filtrare gli short su gold/xau con un proxy di risk-appetite (es. VIX regime o spread TY-bund) prima dell'ingresso.

## #low_cap

- [[tsmom-liq-v1]] · **thesis_wrong** (WLD): segnali tsmom+liq_imbalance su token narrativi a bassa capitalizzazione catturano spesso momentum di brevissimo termine (spike di liquidità) che si esaurisce entro poche candele: senza un filtro di regime (BTC sopra MA su H4, settore AI/L1 in risk-on) il segnale long su altcoin volatili ha tasso di falsi positivi strutturalmente alto e va ridotto in size o saltato

## #macro_override

- [[tsmom-v1]] · **thesis_wrong** (xyz_GOLD): Un segnale tsmom=-1 su un asset con forte tailwind macro (oro in regime risk-off / dollaro debole) ha edge vicino a zero: il momentum di breve periodo è rumore rispetto al flusso dominante. I segnali tsmom short su safe-haven richiedono un filtro regime (es. dollaro in trend rialzista O risk appetite positivo) prima di entrare — senza conferma macro, il fade è contro la corrente più forte.

## #mean-reversion

- [[vwap-reversion-v1]] · **thesis_wrong** (basket): Fade dell'estensione VWAP falsificato 7/7 asset (crypto+commodities+stock): le estensioni oltre 2 sigma IN QUESTO regime sono trend, non esaurimenti. Terza falsificazione consecutiva di tesi mean-reversion (dopo scalp-exit e flow-fade): il regime 2026 H1 premia il trend following, punisce il contrarian.
- [[agents-v1]] · **thesis_right** (ZEC): Su asset illiquidi (ZEC-tier), la combinazione rally >15% senza catalizzatore fondamentale + primo pullback significativo con funding ancora positivo è un segnale di distribuzione ad alta fedeltà: i longs sono intrappolati e non capitolano, il che concentra la pressione sell sul successivo leg down. Il trade ha raggiunto il target (-12.5%) in 36h su 48h disponibili — conferma che il time-stop va calibrato sul tempo di esaurimento del crowding, non sulla volatilità asset. In regime bear o neutro, questo setup (funding positivo + price action negativa) è più affidabile che il fade di momentum puro perché incorpora informazione di positioning.

## #min-hold-bars

- [[tsmom-conservative-v1]] · **execution_issue** (xyz_GOLD): Se close.logged_at precede open.logged_at sulla stessa barra-timestamp, il motore valuta lo stop prima della conferma dell'ingresso (look-ahead intra-barra): la perdita non riflette un movimento di mercato reale. Fix strutturale: aggiungere guard min_hold_bars>=1 nel loop di stop affinché la logica di uscita venga saltata sulla barra di apertura. In parallelo, il pattern GOLD (4204→4231→4348 in 3 giorni, tsmom=-1 persistente) evidenzia che segnali TSMOM short su safe-haven in regime di bid strutturale generano whipsaw sistematici: filtrare gli short su gold/xau con un proxy di risk-appetite (es. VIX regime o spread TY-bund) prima dell'ingresso.

## #momentum

- [[tsmom-conservative-v1]] · **thesis_right** (xyz_CL): Un segnale tsmom = -1 su futures energetici liquidi in trend ribassista porta il prezzo al target 3:1 entro 3-5 sessioni; non intervenire discrezionalmente sul target meccanico — l'edge della strategia si realizza lasciando girare il winner fino al livello stabilito.
- [[agents-v1]] · **thesis_wrong** (SUI): Un vwap_zscore=1 (1σ) in altcoin ad alta beta è sotto la soglia minima di edge: il rapporto segnale/rumore è insufficiente a sopravvivere alla normale volatilità intraday senza un catalizzatore strutturale aggiuntivo (volume >1.5x media 4h o zscore ≥1.5). La relative strength intraday punto-in-tempo (+2.8%) non è una proxy affidabile di momentum sostenuto se non è confermata da espansione volumetrica nel tick successivo all'ingresso — senza follow-through misurato entro 2h, il segnale va trattato come rumore e il trade chiuso in pareggio.

## #momentum-lag

- [[agents-v1]] · **thesis_wrong** (ZEC): Doppia confluenza tsmom+vwap_zscore su candele già estese segna esaurimento, non continuazione: quando la tesi stessa riconosce il crowding e risponde solo con size ridotta, il segnale qualitativo deve essere invertito. Crowding consapevole + momentum tardivo post-rally = peso contrarian implicito ignorato. La size al 50% mitiga la perdita ma non cambia il segno dell'edge atteso. Regola generale: se la tesi contiene 'il rischio X è reale ma lo gestisco con Y', X è probabilmente la causa principale del fallimento e Y è razionalizzazione.

## #momentum_exhaustion

- [[tsmom-v1]] · **thesis_wrong** (BTC): Un segnale TSMOM short su BTC dopo un drawdown multi-giorno tende a coincidere con l'esaurimento del momentum ribassista, non con la sua accelerazione. Prima di entrare short su TSMOM in contesti di alta volatilità, esigere conferma strutturale (es. incapacità di rimbalzo su daily close o break di supporto volumetrico) per distinguere trend in atto da momentum già consumato.

## #momentum_long

- [[agents-v1]] · **execution_issue** (SOL): Un time-stop di 24h è strutturalmente incoerente con una tesi basata su rotazione di capitale a 7 giorni e catalizzatori macro (Iran/BOJ): il regime bull e il funding negativo non erano stati invalidati, il prezzo è uscito piatto (−0.16%) non perché la tesi fosse sbagliata ma perché la finestra di holding era troppo corta per far emergere l'edge. Regola generale: il time-stop deve essere ≥ metà del lookback usato per costruire la tesi — tesi su momentum 7d → time-stop minimo 72-96h; altrimenti si vende rumore intraday su una tesi strutturale.

## #narrative_token

- [[tsmom-liq-v1]] · **thesis_wrong** (WLD): segnali tsmom+liq_imbalance su token narrativi a bassa capitalizzazione catturano spesso momentum di brevissimo termine (spike di liquidità) che si esaurisce entro poche candele: senza un filtro di regime (BTC sopra MA su H4, settore AI/L1 in risk-on) il segnale long su altcoin volatili ha tasso di falsi positivi strutturalmente alto e va ridotto in size o saltato

## #negative_funding

- [[agents-v1]] · **thesis_right** (SOL): Funding negativo strutturale su asset con regime bull confermato e outperformance spot vs paniere crea uno squeeze lento ma prevedibile: i derivati fungono da carburante direzionale anziché da resistenza. La confluenza funding-negativo + spot-outperformance-vs-basket è un setup ad alto valore con invalidazione netta e misurabile (funding flip), replicabile su qualsiasi perpetual liquido indipendentemente dall'asset specifico.

## #news

- [[news-event]] · **thesis_wrong** (basket): Event study su 48 eventi GDELT (12 mesi, 5 topic) falsifica la strategia news-driven DIREZIONALE: tone_hit medio 0.38 (sotto il caso 0.50) - il tono della notizia NON predice la direzione del prezzo. Su 252 combinazioni asset/topic/orizzonte, solo 1 ha |t|>=2 E tono predittivo (ne attenderei ~12 per puro caso). I t-stat alti (LIT/VVV/HYPE +8/12%) sono microcap illiquidi: mean_ret=mean_abs_ret = trend del token, non reazione all'evento. Cosa resta vero: sui liquidi (BTC/ETH) gli eventi geopolitici creano volatilita reale (t~2.8) ma cieca sulla direzione. Riconversione: news_event da segnale direzionale a GATE DI RISCHIO (riduci size/sospendi entrate durante burst news).

## #noise-stop

- [[tsmom-liq-v1]] · **execution_issue** (WLD): Su token illiquidi ad alta volatilità (WLD-class), uno stop fisso al 2.5% rientra nel rumore di breve periodo: il trade è stato stoppato in 12h su movimento di ~1.7bp dal close. Gli stop devono essere calibrati sull'ATR dell'asset specifico (minimo 1×ATR daily), non su una percentuale flat derivata da asset più liquidi come BTC/ETH — altrimenti il segnale corretto viene annullato da volatilità casuale prima che la tesi possa esprimersi.

## #noise_vs_signal

- [[tsmom-liq-v1]] · **execution_issue** (WLD): Su altcoin ad alta volatilità (WLD, float basso), uno stop fisso %-based ignora l'ATR del timeframe: un'oscillazione di 2.5% in 1h è rumore ordinario, non invalidazione della tesi. I segnali tsmom+liq_imbalance erano coerenti ma lo stop è stato piazzato dentro il noise-band — regola: stop su tsmom-liq entries deve essere ≥1× ATR(4h) per sopravvivere al mean-reversion intra-candle senza che la tesi direzionale venga falsificata.

## #overfitting

- [[news-event]] · **thesis_wrong** (basket): Event study su 48 eventi GDELT (12 mesi, 5 topic) falsifica la strategia news-driven DIREZIONALE: tone_hit medio 0.38 (sotto il caso 0.50) - il tono della notizia NON predice la direzione del prezzo. Su 252 combinazioni asset/topic/orizzonte, solo 1 ha |t|>=2 E tono predittivo (ne attenderei ~12 per puro caso). I t-stat alti (LIT/VVV/HYPE +8/12%) sono microcap illiquidi: mean_ret=mean_abs_ret = trend del token, non reazione all'evento. Cosa resta vero: sui liquidi (BTC/ETH) gli eventi geopolitici creano volatilita reale (t~2.8) ma cieca sulla direzione. Riconversione: news_event da segnale direzionale a GATE DI RISCHIO (riduci size/sospendi entrate durante burst news).

## #paper_trading_accounting

- [[tsmom-liq-v1]] · **execution_issue** (WLD): Il PnL (+$174.63 su $2390.57 = 7.3%) è coerente con un fill al target (0.7286, +7.5%) ma exit_px registra 0.6872 (+1.4%) — discrepanza ~5x: il logger sta scrivendo il mark price al momento del log invece del fill price simulato. Aggravante: close.logged_at (20:16) precede open.logged_at (21:15) e open_ts == close_ts (stesso candle), indicando race condition nel pipeline. In paper trading, separare rigorosamente fill_px (prezzo di esecuzione deterministico, fissato all'istante del segnale) da mark_px (prezzo corrente al momento del log); finché il campo è ambiguo ogni post-mortem futuro è invalido indipendentemente dalla direzione del mercato.

## #pnl-sign-mismatch

- [[tsmom-liq-v1]] · **execution_issue** (NEAR): Exit price (2.2725) è sotto entry (2.3664) su un long, ma PnL registrato è +$178. Inoltre ts_close (02:00) precede opened_at (04:00) di 2 ore. Il record è strutturalmente corrotto: il sistema deve validare sign(exit_px - entry_px) == sign(pnl_usd) per i long e ts_close > ts_open prima di persistere su journal — ogni post-mortem su dati incoerenti produce lezioni spurie e degrada il backtest.

## #post-extended-candle

- [[agents-v1]] · **thesis_wrong** (ZEC): Doppia confluenza tsmom+vwap_zscore su candele già estese segna esaurimento, non continuazione: quando la tesi stessa riconosce il crowding e risponde solo con size ridotta, il segnale qualitativo deve essere invertito. Crowding consapevole + momentum tardivo post-rally = peso contrarian implicito ignorato. La size al 50% mitiga la perdita ma non cambia il segno dell'edge atteso. Regola generale: se la tesi contiene 'il rischio X è reale ma lo gestisco con Y', X è probabilmente la causa principale del fallimento e Y è razionalizzazione.

## #pre_expansion

- [[agents-v1]] · **thesis_right** (ZEC): Vol compression su un asset già in bull regime primario è un setup asimmetrico: il regime trasforma un pattern neutro in un entry direzionale ad alta probabilità. La selezione per regime nel basket (1/5 in bull vs 4/5 in chop) è il filtro che converte il segnale tecnico in edge — senza quel filtro lo stesso setup su un asset in chop non avrebbe la stessa aspettativa. Generalizzazione: quando si fa basket selection, cercare il regime outlier positivo e concentrare la posizione lì, non diversificare su tutti i segnali.

## #premature_stopout

- [[tsmom-liq-v1]] · **execution_issue** (XRP): Quando tsmom e liq_imbalance convergono (-1/-1) il segnale è solido, ma su asset ad alta volatilità intraday (XRP, ATR giornaliero > 3%) uno stop a ~2.5% cade dentro la banda di rumore e non fuori dalla tesi. Gli stop di momentum-liq vanno calibrati su 1.5-2x ATR del timeframe del segnale, non su una percentuale fissa: altrimenti ogni rimbalzo tecnico di 5h elimina il trade prima che la direzionalità si esprima.

## #regime

- [[vwap-reversion-v1]] · **thesis_wrong** (basket): Fade dell'estensione VWAP falsificato 7/7 asset (crypto+commodities+stock): le estensioni oltre 2 sigma IN QUESTO regime sono trend, non esaurimenti. Terza falsificazione consecutiva di tesi mean-reversion (dopo scalp-exit e flow-fade): il regime 2026 H1 premia il trend following, punisce il contrarian.

## #regime-filter

- [[tsmom-conservative-v1]] · **execution_issue** (xyz_GOLD): Se close.logged_at precede open.logged_at sulla stessa barra-timestamp, il motore valuta lo stop prima della conferma dell'ingresso (look-ahead intra-barra): la perdita non riflette un movimento di mercato reale. Fix strutturale: aggiungere guard min_hold_bars>=1 nel loop di stop affinché la logica di uscita venga saltata sulla barra di apertura. In parallelo, il pattern GOLD (4204→4231→4348 in 3 giorni, tsmom=-1 persistente) evidenzia che segnali TSMOM short su safe-haven in regime di bid strutturale generano whipsaw sistematici: filtrare gli short su gold/xau con un proxy di risk-appetite (es. VIX regime o spread TY-bund) prima dell'ingresso.
- [[tsmom-liq-v1]] · **thesis_wrong** (ZEC): In fasi di downtrend strutturale su altcoin ad alta beta (ZEC), segnali tsmom+liq_imbalance rialzisti catturano spesso picchi di crowding long piuttosto che momentum genuino: il segnale si accende quando tutti sono già entrati, non quando inizia la spinta. Richiedere un regime-filter esplicito (es. BTC price > MA20 o rolling-Sharpe basket > 0) prima di approvare long su tsmom in altcoin.

## #regime_filter

- [[tsmom-v1]] · **thesis_wrong** (ETH): Il segnale tsmom -1 era tecnicamente valido sul passato ma il momentum aveva già esaurito la direzionalità: ETH a 1660 era vicino all'estremo del drawdown recente e il prezzo ha immediatamente invertito. Un filtro di 'freshness' (il segnale -1 deve essere presente da ≤2 barre, non cronico) e la conferma cross-sectional (ETH sotto-performante rispetto al basket nella stessa finestra) separano i momentum genuini dai falsi segnali in regime di possibile mean-reversion.
- [[tsmom-v1]] · **thesis_wrong** (xyz_GOLD): Un segnale tsmom=-1 su un asset con forte tailwind macro (oro in regime risk-off / dollaro debole) ha edge vicino a zero: il momentum di breve periodo è rumore rispetto al flusso dominante. I segnali tsmom short su safe-haven richiedono un filtro regime (es. dollaro in trend rialzista O risk appetite positivo) prima di entrare — senza conferma macro, il fade è contro la corrente più forte.
- [[tsmom-liq-v1]] · **thesis_wrong** (WLD): segnali tsmom+liq_imbalance su token narrativi a bassa capitalizzazione catturano spesso momentum di brevissimo termine (spike di liquidità) che si esaurisce entro poche candele: senza un filtro di regime (BTC sopra MA su H4, settore AI/L1 in risk-on) il segnale long su altcoin volatili ha tasso di falsi positivi strutturalmente alto e va ridotto in size o saltato
- [[tsmom-liq-v1]] · **execution_issue** (CRV): Segnali tsmom+liq_imbalance su token DeFi small-cap richiedono un filtro di regime esplicito: in mercato bear/laterale, gli squilibri di liquidità su CRV-class asset sono noise e non segnale direzionale — long momentum senza conferma macro (es. BTC sopra EMA breve o realized-vol sotto soglia) producono whipsaw sistematici il cui stop-rate supera l'alpha atteso del setup.
- [[tsmom-liq-v1]] · **thesis_wrong** (CRV): tsmom + liq_imbalance simultanei su token DeFi (bassa cap, alto crowding) possono riflettere momentum già esaurito al momento del segnale — non un'accelerazione in corso. Regola generale: in regime neutro/bear su BTC, esigere N ore di persistenza del segnale (es. 2+ candle di conferma) e coerenza col trend ETH prima di entrare long su DeFi; un segnale intracandle fermato in <1h indica che la liq_imbalance era noise temporaneo, non pressione direzionale sostenuta.
- [[tsmom-liq-v1]] · **thesis_wrong** (CRV): tsmom+liq_imbalance=1 su governance DeFi token con distribuzione strutturale (ve-overhang, TVL/fees in calo) cattura un ingresso crowded, non momentum organico: tutti i sistemi sistematici ricevono lo stesso trigger simultaneamente, il liq_imbalance=1 riflette gli ordini degli altri modelli tsmom, non domanda spot genuina, e la mean-reversion avviene entro 12-24h prima che la tesi si dispieghi. Regola generale: su DeFi governance token, esigere tsmom positivo su lookback ≥30g (non solo 7g) E conferma che il ratio DeFi-sector/BTC sia in uptrend settimanale prima di considerare liq_imbalance una conferma valida.

## #regime_outlier

- [[agents-v1]] · **thesis_right** (ZEC): Vol compression su un asset già in bull regime primario è un setup asimmetrico: il regime trasforma un pattern neutro in un entry direzionale ad alta probabilità. La selezione per regime nel basket (1/5 in bull vs 4/5 in chop) è il filtro che converte il segnale tecnico in edge — senza quel filtro lo stesso setup su un asset in chop non avrebbe la stessa aspettativa. Generalizzazione: quando si fa basket selection, cercare il regime outlier positivo e concentrare la posizione lì, non diversificare su tutti i segnali.

## #relative_strength_decay

- [[agents-v1]] · **thesis_wrong** (SUI): Un vwap_zscore=1 (1σ) in altcoin ad alta beta è sotto la soglia minima di edge: il rapporto segnale/rumore è insufficiente a sopravvivere alla normale volatilità intraday senza un catalizzatore strutturale aggiuntivo (volume >1.5x media 4h o zscore ≥1.5). La relative strength intraday punto-in-tempo (+2.8%) non è una proxy affidabile di momentum sostenuto se non è confermata da espansione volumetrica nel tick successivo all'ingresso — senza follow-through misurato entro 2h, il segnale va trattato come rumore e il trade chiuso in pareggio.

## #research

- [[tsmom-conservative-v1]] · **thesis_right** (basket): Ricerca profili di rischio su TSMOM: il profilo CONSERVATIVO (leva 1x, stop 2.5%, 2 posizioni) domina il base e l'aggressivo: stesso Sharpe (1.70) ma drawdown dimezzato (-9.8% vs -15%+). L'aggressivo (leva 2x, stop 6%) FALSIFICATO: Sharpe 1.56 sotto buy-and-hold, piu' rischio senza reward. Lezione: su trend-following il controllo del rischio batte la ricerca di rendimento. tsmom-conservative -> challenger in paper.
- [[commodities-cot-trend-v1]] · **thesis_wrong** (basket): Ipotesi 'TSMOM commodities confermato da posizionamento COT estremo' FALSIFICATA: il filtro COT peggiora lo Sharpe (da 0.43 a -0.10). Il posizionamento estremo dei fondi non e' conferma del trend ma semmai segnale di esaurimento — coerente col fatto che restringe gli ingressi proprio quando il crowd e' gia' dentro. COT resta segnale nel registry ma non come conferma di trend.
- [[commodities-trend-v1]] · **thesis_wrong** (basket): Specializzazione per asset-class: TSMOM sulle SOLE commodities (Sharpe 0.43) NON batte buy-and-hold (-0.70 vs B&H) — nel periodo le commodities sono semplicemente salite, holding vince. Il basket MISTO resta superiore: la diversificazione cross-asset del trend-following e' parte dell'edge, non un dettaglio. crypto-trend-flow batte il B&H crypto ma con Sharpe assoluto debole (0.33).

## #reversion_vs_breakout

- [[agents-v1]] · **execution_issue** (SUI): Vol_compression + funding-squeeze long su L1 altcoin consegna tipicamente 3-7% di reversion intra-giornaliera, non 18%: quando il catalizzatore è 'esaurimento pressione ribassista' (non breakout macro), il target deve essere calibrato sulla magnitudine attesa dello squeeze (R:R compresso ma alta probabilità) e il time_stop deve essere proporzionato — 48h è coerente con la tesi, ma abbinarlo a un target x3 crea un'asimmetria impossibile: il trade chiude a time_stop catturando solo il 30% del premio atteso. Separare il sizing del target in base al tipo di driver: squeeze → target 5-8%, breakout strutturale → target 15%+.

## #risk-gate

- [[news-event]] · **thesis_wrong** (basket): Event study su 48 eventi GDELT (12 mesi, 5 topic) falsifica la strategia news-driven DIREZIONALE: tone_hit medio 0.38 (sotto il caso 0.50) - il tono della notizia NON predice la direzione del prezzo. Su 252 combinazioni asset/topic/orizzonte, solo 1 ha |t|>=2 E tono predittivo (ne attenderei ~12 per puro caso). I t-stat alti (LIT/VVV/HYPE +8/12%) sono microcap illiquidi: mean_ret=mean_abs_ret = trend del token, non reazione all'evento. Cosa resta vero: sui liquidi (BTC/ETH) gli eventi geopolitici creano volatilita reale (t~2.8) ma cieca sulla direzione. Riconversione: news_event da segnale direzionale a GATE DI RISCHIO (riduci size/sospendi entrate durante burst news).

## #risk-profile

- [[tsmom-conservative-v1]] · **thesis_right** (basket): Ricerca profili di rischio su TSMOM: il profilo CONSERVATIVO (leva 1x, stop 2.5%, 2 posizioni) domina il base e l'aggressivo: stesso Sharpe (1.70) ma drawdown dimezzato (-9.8% vs -15%+). L'aggressivo (leva 2x, stop 6%) FALSIFICATO: Sharpe 1.56 sotto buy-and-hold, piu' rischio senza reward. Lezione: su trend-following il controllo del rischio batte la ricerca di rendimento. tsmom-conservative -> challenger in paper.

## #safe-haven

- [[tsmom-conservative-v1]] · **execution_issue** (xyz_GOLD): Se close.logged_at precede open.logged_at sulla stessa barra-timestamp, il motore valuta lo stop prima della conferma dell'ingresso (look-ahead intra-barra): la perdita non riflette un movimento di mercato reale. Fix strutturale: aggiungere guard min_hold_bars>=1 nel loop di stop affinché la logica di uscita venga saltata sulla barra di apertura. In parallelo, il pattern GOLD (4204→4231→4348 in 3 giorni, tsmom=-1 persistente) evidenzia che segnali TSMOM short su safe-haven in regime di bid strutturale generano whipsaw sistematici: filtrare gli short su gold/xau con un proxy di risk-appetite (es. VIX regime o spread TY-bund) prima dell'ingresso.

## #same-bar-exit

- [[tsmom-conservative-v1]] · **execution_issue** (xyz_GOLD): Se close.logged_at precede open.logged_at sulla stessa barra-timestamp, il motore valuta lo stop prima della conferma dell'ingresso (look-ahead intra-barra): la perdita non riflette un movimento di mercato reale. Fix strutturale: aggiungere guard min_hold_bars>=1 nel loop di stop affinché la logica di uscita venga saltata sulla barra di apertura. In parallelo, il pattern GOLD (4204→4231→4348 in 3 giorni, tsmom=-1 persistente) evidenzia che segnali TSMOM short su safe-haven in regime di bid strutturale generano whipsaw sistematici: filtrare gli short su gold/xau con un proxy di risk-appetite (es. VIX regime o spread TY-bund) prima dell'ingresso.

## #short

- [[tsmom-v1]] · **thesis_wrong** (BTC): Un segnale TSMOM short su BTC dopo un drawdown multi-giorno tende a coincidere con l'esaurimento del momentum ribassista, non con la sua accelerazione. Prima di entrare short su TSMOM in contesti di alta volatilità, esigere conferma strutturale (es. incapacità di rimbalzo su daily close o break di supporto volumetrico) per distinguere trend in atto da momentum già consumato.
- [[tsmom-v1]] · **thesis_wrong** (xyz_GOLD): Un segnale tsmom=-1 su un asset con forte tailwind macro (oro in regime risk-off / dollaro debole) ha edge vicino a zero: il momentum di breve periodo è rumore rispetto al flusso dominante. I segnali tsmom short su safe-haven richiedono un filtro regime (es. dollaro in trend rialzista O risk appetite positivo) prima di entrare — senza conferma macro, il fade è contro la corrente più forte.
- [[tsmom-conservative-v1]] · **thesis_right** (xyz_CL): Un segnale tsmom = -1 su futures energetici liquidi in trend ribassista porta il prezzo al target 3:1 entro 3-5 sessioni; non intervenire discrezionalmente sul target meccanico — l'edge della strategia si realizza lasciando girare il winner fino al livello stabilito.

## #short-setup

- [[agents-v1]] · **thesis_right** (ZEC): Su asset illiquidi (ZEC-tier), la combinazione rally >15% senza catalizzatore fondamentale + primo pullback significativo con funding ancora positivo è un segnale di distribuzione ad alta fedeltà: i longs sono intrappolati e non capitolano, il che concentra la pressione sell sul successivo leg down. Il trade ha raggiunto il target (-12.5%) in 36h su 48h disponibili — conferma che il time-stop va calibrato sul tempo di esaurimento del crowding, non sulla volatilità asset. In regime bear o neutro, questo setup (funding positivo + price action negativa) è più affidabile che il fade di momentum puro perché incorpora informazione di positioning.

## #short_squeeze

- [[agents-v1]] · **thesis_right** (SOL): Funding negativo strutturale su asset con regime bull confermato e outperformance spot vs paniere crea uno squeeze lento ma prevedibile: i derivati fungono da carburante direzionale anziché da resistenza. La confluenza funding-negativo + spot-outperformance-vs-basket è un setup ad alto valore con invalidazione netta e misurabile (funding flip), replicabile su qualsiasi perpetual liquido indipendentemente dall'asset specifico.

## #signal-timeframe

- [[tsmom-liq-v1]] · **execution_issue** (WLD): Un segnale tsmom è per definizione costruito su finestre giornaliere (o multi-ora): lo stop deve essere ≥ 1× ATR-giornaliero del sottostante, altrimenti il rumore intraday esaurisce il margine prima che la tesi si materializzi. WLD ha ATR-daily ~5-8%; uno stop al 2.5% sotto l'entry entra direttamente nella fascia di rumore e viene colpito statisticamente anche quando la direzione è corretta. Regola generale: su strategie momentum a bassa frequenza, calibra lo stop sul timeframe del segnale (daily ATR), non sulla tolleranza di rischio in USD — aggiusta il size per tenere il rischio fisso, non restringere lo stop.

## #signal_confluence

- [[tsmom-liq-v1]] · **thesis_right** (NEAR): Quando tsmom e liq_imbalance convergono entrambi a +1 (signal_vote pieno), il trade ha sufficiente conviction per giustificare R:R ≥ 3:1 con target fisso: uscire anticipatamente o ridurre il target per 'sicurezza' sarebbe stato un errore atteso-negativo. La confluenza momentum + order-flow su alt-L1 genera move intraday completi — non scalare out prima del target.
- [[tsmom-liq-v1]] · **execution_issue** (ZEC): Doppio segnale confluente (tsmom+liq entrambi=1) su un alt ad alta volatilità segnala potenziale entry affollato: molti sistemi sistematici ricevono lo stesso trigger simultaneamente, e uno stop fisso al 2.5% viene colpito dal noise di mean-reversion prima che la tesi si dispieghi. Regola generale: su alt con ATR/day ≥ 3%, calibrare lo stop a 1× ATR(14) e ridurre la size proporzionalmente; in alternativa, attendere un micro-pullback dal primo tick di segnale per entry meno denso.

## #signal_staleness

- [[tsmom-v1]] · **thesis_wrong** (ETH): Il segnale tsmom -1 era tecnicamente valido sul passato ma il momentum aveva già esaurito la direzionalità: ETH a 1660 era vicino all'estremo del drawdown recente e il prezzo ha immediatamente invertito. Un filtro di 'freshness' (il segnale -1 deve essere presente da ≤2 barre, non cronico) e la conferma cross-sectional (ETH sotto-performante rispetto al basket nella stessa finestra) separano i momentum genuini dai falsi segnali in regime di possibile mean-reversion.
- [[tsmom-liq-v1]] · **thesis_wrong** (CRV): tsmom + liq_imbalance simultanei su token DeFi (bassa cap, alto crowding) possono riflettere momentum già esaurito al momento del segnale — non un'accelerazione in corso. Regola generale: in regime neutro/bear su BTC, esigere N ore di persistenza del segnale (es. 2+ candle di conferma) e coerenza col trend ETH prima di entrare long su DeFi; un segnale intracandle fermato in <1h indica che la liq_imbalance era noise temporaneo, non pressione direzionale sostenuta.

## #signal_threshold

- [[agents-v1]] · **thesis_wrong** (SUI): Un vwap_zscore=1 (1σ) in altcoin ad alta beta è sotto la soglia minima di edge: il rapporto segnale/rumore è insufficiente a sopravvivere alla normale volatilità intraday senza un catalizzatore strutturale aggiuntivo (volume >1.5x media 4h o zscore ≥1.5). La relative strength intraday punto-in-tempo (+2.8%) non è una proxy affidabile di momentum sostenuto se non è confermata da espansione volumetrica nel tick successivo all'ingresso — senza follow-through misurato entro 2h, il segnale va trattato come rumore e il trade chiuso in pareggio.

## #size-vs-stop-tradeoff

- [[tsmom-liq-v1]] · **execution_issue** (WLD): Un segnale tsmom è per definizione costruito su finestre giornaliere (o multi-ora): lo stop deve essere ≥ 1× ATR-giornaliero del sottostante, altrimenti il rumore intraday esaurisce il margine prima che la tesi si materializzi. WLD ha ATR-daily ~5-8%; uno stop al 2.5% sotto l'entry entra direttamente nella fascia di rumore e viene colpito statisticamente anche quando la direzione è corretta. Regola generale: su strategie momentum a bassa frequenza, calibra lo stop sul timeframe del segnale (daily ATR), non sulla tolleranza di rischio in USD — aggiusta il size per tenere il rischio fisso, non restringere lo stop.

## #sol

- [[agents-v1]] · **execution_issue** (SOL): Funding negativo mite (−0.25% APR ≈ rumore neutro) non genera squeeze meccanico materiale: la pressione di auto-liquidazione diventa concreta solo sotto −1% APR o quando il gradiente di funding accelera verso neutro (≥0.05% APR/h nelle ultime 4h). Un time-stop da 12h è incongruente con una tesi di compressione funding lenta: o si entra solo quando la compressione è già in corso (momentum del funding, non livello), oppure si estende il time-stop a ≥24h dimezzando la size. Il volume_surge era un segnale direzionale valido, ma non è un proxy del timing dello squeeze.

## #squeeze

- [[agents-v1]] · **thesis_wrong** (ZEC): Fade contro trend (squeeze su crowding) dopo un +5% giornaliero = comprare il rimbalzo gia esteso. In bear regime l'entry squeeze richiede conferma (retest del breakout o capitolazione OI), non anticipazione. Conferma la lezione gen1-3 del loop evolutivo: il crowding da solo non basta contro il trend.

## #stop-calibration

- [[tsmom-liq-v1]] · **execution_issue** (WLD): Un segnale tsmom è per definizione costruito su finestre giornaliere (o multi-ora): lo stop deve essere ≥ 1× ATR-giornaliero del sottostante, altrimenti il rumore intraday esaurisce il margine prima che la tesi si materializzi. WLD ha ATR-daily ~5-8%; uno stop al 2.5% sotto l'entry entra direttamente nella fascia di rumore e viene colpito statisticamente anche quando la direzione è corretta. Regola generale: su strategie momentum a bassa frequenza, calibra lo stop sul timeframe del segnale (daily ATR), non sulla tolleranza di rischio in USD — aggiusta il size per tenere il rischio fisso, non restringere lo stop.

## #stop-placement

- [[agents-v1]] · **execution_issue** (ZEC): Lo stop deve coincidere con l'invalidazione dichiarata della tesi, mai essere piu stretto: qui stop 418 vs invalidazione 415 - usciti prima che la tesi morisse. Se lo stop coerente rende il rischio troppo grande, ridurre la size, non stringere lo stop.

## #stop-sizing

- [[tsmom-liq-v1]] · **execution_issue** (WLD): Su token illiquidi ad alta volatilità (WLD-class), uno stop fisso al 2.5% rientra nel rumore di breve periodo: il trade è stato stoppato in 12h su movimento di ~1.7bp dal close. Gli stop devono essere calibrati sull'ATR dell'asset specifico (minimo 1×ATR daily), non su una percentuale flat derivata da asset più liquidi come BTC/ETH — altrimenti il segnale corretto viene annullato da volatilità casuale prima che la tesi possa esprimersi.

## #stop_calibration

- [[tsmom-liq-v1]] · **execution_issue** (NEAR): Quando tsmom + liq_imbalance si allineano su altcoin ad alta beta (NEAR, SOL-tier), uno stop fisso <3% viene consumato dal rumore intraday prima che il momentum si materializzi: il minimo stop deve essere ≥1.5× ATR daily del simbolo; in alternativa ridurre la size proporzionalmente per mantenere il risk assoluto costante con uno stop più largo.

## #stop_sizing

- [[tsmom-liq-v1]] · **execution_issue** (XRP): Quando tsmom e liq_imbalance convergono (-1/-1) il segnale è solido, ma su asset ad alta volatilità intraday (XRP, ATR giornaliero > 3%) uno stop a ~2.5% cade dentro la banda di rumore e non fuori dalla tesi. Gli stop di momentum-liq vanno calibrati su 1.5-2x ATR del timeframe del segnale, non su una percentuale fissa: altrimenti ogni rimbalzo tecnico di 5h elimina il trade prima che la direzionalità si esprima.
- [[tsmom-liq-v1]] · **execution_issue** (ZEC): Doppio segnale confluente (tsmom+liq entrambi=1) su un alt ad alta volatilità segnala potenziale entry affollato: molti sistemi sistematici ricevono lo stesso trigger simultaneamente, e uno stop fisso al 2.5% viene colpito dal noise di mean-reversion prima che la tesi si dispieghi. Regola generale: su alt con ATR/day ≥ 3%, calibrare lo stop a 1× ATR(14) e ridurre la size proporzionalmente; in alternativa, attendere un micro-pullback dal primo tick di segnale per entry meno denso.
- [[tsmom-liq-v1]] · **execution_issue** (WLD): Su altcoin ad alta volatilità (WLD, float basso), uno stop fisso %-based ignora l'ATR del timeframe: un'oscillazione di 2.5% in 1h è rumore ordinario, non invalidazione della tesi. I segnali tsmom+liq_imbalance erano coerenti ma lo stop è stato piazzato dentro il noise-band — regola: stop su tsmom-liq entries deve essere ≥1× ATR(4h) per sopravvivere al mean-reversion intra-candle senza che la tesi direzionale venga falsificata.

## #structural_decline

- [[tsmom-liq-v1]] · **thesis_wrong** (CRV): tsmom+liq_imbalance=1 su governance DeFi token con distribuzione strutturale (ve-overhang, TVL/fees in calo) cattura un ingresso crowded, non momentum organico: tutti i sistemi sistematici ricevono lo stesso trigger simultaneamente, il liq_imbalance=1 riflette gli ordini degli altri modelli tsmom, non domanda spot genuina, e la mean-reversion avviene entro 12-24h prima che la tesi si dispieghi. Regola generale: su DeFi governance token, esigere tsmom positivo su lookback ≥30g (non solo 7g) E conferma che il ratio DeFi-sector/BTC sia in uptrend settimanale prima di considerare liq_imbalance una conferma valida.

## #structural_thesis

- [[agents-v1]] · **execution_issue** (SOL): Un time-stop di 24h è strutturalmente incoerente con una tesi basata su rotazione di capitale a 7 giorni e catalizzatori macro (Iran/BOJ): il regime bull e il funding negativo non erano stati invalidati, il prezzo è uscito piatto (−0.16%) non perché la tesi fosse sbagliata ma perché la finestra di holding era troppo corta per far emergere l'edge. Regola generale: il time-stop deve essere ≥ metà del lookback usato per costruire la tesi — tesi su momentum 7d → time-stop minimo 72-96h; altrimenti si vende rumore intraday su una tesi strutturale.

## #target_hit

- [[tsmom-conservative-v1]] · **thesis_right** (xyz_CL): Un segnale tsmom = -1 su futures energetici liquidi in trend ribassista porta il prezzo al target 3:1 entro 3-5 sessioni; non intervenire discrezionalmente sul target meccanico — l'edge della strategia si realizza lasciando girare il winner fino al livello stabilito.

## #target_miscalibration

- [[agents-v1]] · **execution_issue** (SUI): Vol_compression + funding-squeeze long su L1 altcoin consegna tipicamente 3-7% di reversion intra-giornaliera, non 18%: quando il catalizzatore è 'esaurimento pressione ribassista' (non breakout macro), il target deve essere calibrato sulla magnitudine attesa dello squeeze (R:R compresso ma alta probabilità) e il time_stop deve essere proporzionato — 48h è coerente con la tesi, ma abbinarlo a un target x3 crea un'asimmetria impossibile: il trade chiude a time_stop catturando solo il 30% del premio atteso. Separare il sizing del target in base al tipo di driver: squeeze → target 5-8%, breakout strutturale → target 15%+.

## #thesis-confirmed

- [[agents-v1]] · **thesis_right** (ZEC): Su asset illiquidi (ZEC-tier), la combinazione rally >15% senza catalizzatore fondamentale + primo pullback significativo con funding ancora positivo è un segnale di distribuzione ad alta fedeltà: i longs sono intrappolati e non capitolano, il che concentra la pressione sell sul successivo leg down. Il trade ha raggiunto il target (-12.5%) in 36h su 48h disponibili — conferma che il time-stop va calibrato sul tempo di esaurimento del crowding, non sulla volatilità asset. In regime bear o neutro, questo setup (funding positivo + price action negativa) è più affidabile che il fade di momentum puro perché incorpora informazione di positioning.

## #thesis-self-contradiction

- [[agents-v1]] · **thesis_wrong** (ZEC): Doppia confluenza tsmom+vwap_zscore su candele già estese segna esaurimento, non continuazione: quando la tesi stessa riconosce il crowding e risponde solo con size ridotta, il segnale qualitativo deve essere invertito. Crowding consapevole + momentum tardivo post-rally = peso contrarian implicito ignorato. La size al 50% mitiga la perdita ma non cambia il segno dell'edge atteso. Regola generale: se la tesi contiene 'il rischio X è reale ma lo gestisco con Y', X è probabilmente la causa principale del fallimento e Y è razionalizzazione.

## #time_stop

- [[agents-v1]] · **execution_issue** (SUI): Vol_compression + funding-squeeze long su L1 altcoin consegna tipicamente 3-7% di reversion intra-giornaliera, non 18%: quando il catalizzatore è 'esaurimento pressione ribassista' (non breakout macro), il target deve essere calibrato sulla magnitudine attesa dello squeeze (R:R compresso ma alta probabilità) e il time_stop deve essere proporzionato — 48h è coerente con la tesi, ma abbinarlo a un target x3 crea un'asimmetria impossibile: il trade chiude a time_stop catturando solo il 30% del premio atteso. Separare il sizing del target in base al tipo di driver: squeeze → target 5-8%, breakout strutturale → target 15%+.

## #time_stop_mismatch

- [[agents-v1]] · **execution_issue** (SOL): Funding negativo mite (−0.25% APR ≈ rumore neutro) non genera squeeze meccanico materiale: la pressione di auto-liquidazione diventa concreta solo sotto −1% APR o quando il gradiente di funding accelera verso neutro (≥0.05% APR/h nelle ultime 4h). Un time-stop da 12h è incongruente con una tesi di compressione funding lenta: o si entra solo quando la compressione è già in corso (momentum del funding, non livello), oppure si estende il time-stop a ≥24h dimezzando la size. Il volume_surge era un segnale direzionale valido, ma non è un proxy del timing dello squeeze.
- [[agents-v1]] · **execution_issue** (SOL): Un time-stop di 24h è strutturalmente incoerente con una tesi basata su rotazione di capitale a 7 giorni e catalizzatori macro (Iran/BOJ): il regime bull e il funding negativo non erano stati invalidati, il prezzo è uscito piatto (−0.16%) non perché la tesi fosse sbagliata ma perché la finestra di holding era troppo corta per far emergere l'edge. Regola generale: il time-stop deve essere ≥ metà del lookback usato per costruire la tesi — tesi su momentum 7d → time-stop minimo 72-96h; altrimenti si vende rumore intraday su una tesi strutturale.

## #timestamp-inversion

- [[tsmom-liq-v1]] · **execution_issue** (NEAR): Exit price (2.2725) è sotto entry (2.3664) su un long, ma PnL registrato è +$178. Inoltre ts_close (02:00) precede opened_at (04:00) di 2 ore. Il record è strutturalmente corrotto: il sistema deve validare sign(exit_px - entry_px) == sign(pnl_usd) per i long e ts_close > ts_open prima di persistere su journal — ogni post-mortem su dati incoerenti produce lezioni spurie e degrada il backtest.

## #timestamp_race_condition

- [[tsmom-liq-v1]] · **execution_issue** (WLD): Il PnL (+$174.63 su $2390.57 = 7.3%) è coerente con un fill al target (0.7286, +7.5%) ma exit_px registra 0.6872 (+1.4%) — discrepanza ~5x: il logger sta scrivendo il mark price al momento del log invece del fill price simulato. Aggravante: close.logged_at (20:16) precede open.logged_at (21:15) e open_ts == close_ts (stesso candle), indicando race condition nel pipeline. In paper trading, separare rigorosamente fill_px (prezzo di esecuzione deterministico, fissato all'istante del segnale) da mark_px (prezzo corrente al momento del log); finché il campo è ambiguo ogni post-mortem futuro è invalido indipendentemente dalla direzione del mercato.

## #timing

- [[agents-v1]] · **thesis_wrong** (ZEC): Fade contro trend (squeeze su crowding) dopo un +5% giornaliero = comprare il rimbalzo gia esteso. In bear regime l'entry squeeze richiede conferma (retest del breakout o capitolazione OI), non anticipazione. Conferma la lezione gen1-3 del loop evolutivo: il crowding da solo non basta contro il trend.

## #trend-following

- [[tsmom-v1]] · **thesis_right** (basket): TSMOM (7g+30g concordi, exit posizionali) conferma la letteratura: Sharpe medio 1.69, 8/9 asset positivi su basket misto. I segnali universali OHLCV viaggiano cross-asset; funding/flow restano additivi solo su crypto. Nota: consistenza per fold bassa (25/54) - tipico del trend following, guadagna a strappi nei trend e resta piatto nel chop.

## #trend_exhaustion

- [[tsmom-v1]] · **thesis_wrong** (ETH): Il segnale tsmom -1 era tecnicamente valido sul passato ma il momentum aveva già esaurito la direzionalità: ETH a 1660 era vicino all'estremo del drawdown recente e il prezzo ha immediatamente invertito. Un filtro di 'freshness' (il segnale -1 deve essere presente da ≤2 barre, non cronico) e la conferma cross-sectional (ETH sotto-performante rispetto al basket nella stessa finestra) separano i momentum genuini dai falsi segnali in regime di possibile mean-reversion.

## #trend_following

- [[tsmom-v1]] · **thesis_wrong** (xyz_GOLD): Un segnale tsmom=-1 su un asset con forte tailwind macro (oro in regime risk-off / dollaro debole) ha edge vicino a zero: il momentum di breve periodo è rumore rispetto al flusso dominante. I segnali tsmom short su safe-haven richiedono un filtro regime (es. dollaro in trend rialzista O risk appetite positivo) prima di entrare — senza conferma macro, il fade è contro la corrente più forte.
- [[agents-v1]] · **thesis_right** (SOL): Funding negativo strutturale su asset con regime bull confermato e outperformance spot vs paniere crea uno squeeze lento ma prevedibile: i derivati fungono da carburante direzionale anziché da resistenza. La confluenza funding-negativo + spot-outperformance-vs-basket è un setup ad alto valore con invalidazione netta e misurabile (funding flip), replicabile su qualsiasi perpetual liquido indipendentemente dall'asset specifico.

## #tsmom

- [[tsmom-v1]] · **thesis_right** (basket): TSMOM (7g+30g concordi, exit posizionali) conferma la letteratura: Sharpe medio 1.69, 8/9 asset positivi su basket misto. I segnali universali OHLCV viaggiano cross-asset; funding/flow restano additivi solo su crypto. Nota: consistenza per fold bassa (25/54) - tipico del trend following, guadagna a strappi nei trend e resta piatto nel chop.
- [[tsmom-conservative-v1]] · **thesis_right** (basket): Ricerca profili di rischio su TSMOM: il profilo CONSERVATIVO (leva 1x, stop 2.5%, 2 posizioni) domina il base e l'aggressivo: stesso Sharpe (1.70) ma drawdown dimezzato (-9.8% vs -15%+). L'aggressivo (leva 2x, stop 6%) FALSIFICATO: Sharpe 1.56 sotto buy-and-hold, piu' rischio senza reward. Lezione: su trend-following il controllo del rischio batte la ricerca di rendimento. tsmom-conservative -> challenger in paper.
- [[tsmom-v1]] · **thesis_wrong** (BTC): Un segnale TSMOM short su BTC dopo un drawdown multi-giorno tende a coincidere con l'esaurimento del momentum ribassista, non con la sua accelerazione. Prima di entrare short su TSMOM in contesti di alta volatilità, esigere conferma strutturale (es. incapacità di rimbalzo su daily close o break di supporto volumetrico) per distinguere trend in atto da momentum già consumato.
- [[tsmom-v1]] · **thesis_wrong** (ETH): Il segnale tsmom -1 era tecnicamente valido sul passato ma il momentum aveva già esaurito la direzionalità: ETH a 1660 era vicino all'estremo del drawdown recente e il prezzo ha immediatamente invertito. Un filtro di 'freshness' (il segnale -1 deve essere presente da ≤2 barre, non cronico) e la conferma cross-sectional (ETH sotto-performante rispetto al basket nella stessa finestra) separano i momentum genuini dai falsi segnali in regime di possibile mean-reversion.
- [[tsmom-liq-v1]] · **execution_issue** (XRP): Quando tsmom e liq_imbalance convergono (-1/-1) il segnale è solido, ma su asset ad alta volatilità intraday (XRP, ATR giornaliero > 3%) uno stop a ~2.5% cade dentro la banda di rumore e non fuori dalla tesi. Gli stop di momentum-liq vanno calibrati su 1.5-2x ATR del timeframe del segnale, non su una percentuale fissa: altrimenti ogni rimbalzo tecnico di 5h elimina il trade prima che la direzionalità si esprima.
- [[tsmom-conservative-v1]] · **execution_issue** (xyz_GOLD): Se close.logged_at precede open.logged_at sulla stessa barra-timestamp, il motore valuta lo stop prima della conferma dell'ingresso (look-ahead intra-barra): la perdita non riflette un movimento di mercato reale. Fix strutturale: aggiungere guard min_hold_bars>=1 nel loop di stop affinché la logica di uscita venga saltata sulla barra di apertura. In parallelo, il pattern GOLD (4204→4231→4348 in 3 giorni, tsmom=-1 persistente) evidenzia che segnali TSMOM short su safe-haven in regime di bid strutturale generano whipsaw sistematici: filtrare gli short su gold/xau con un proxy di risk-appetite (es. VIX regime o spread TY-bund) prima dell'ingresso.
- [[tsmom-v1]] · **thesis_wrong** (xyz_GOLD): Un segnale tsmom=-1 su un asset con forte tailwind macro (oro in regime risk-off / dollaro debole) ha edge vicino a zero: il momentum di breve periodo è rumore rispetto al flusso dominante. I segnali tsmom short su safe-haven richiedono un filtro regime (es. dollaro in trend rialzista O risk appetite positivo) prima di entrare — senza conferma macro, il fade è contro la corrente più forte.
- [[tsmom-liq-v1]] · **thesis_right** (NEAR): Quando tsmom e liq_imbalance convergono entrambi a +1 (signal_vote pieno), il trade ha sufficiente conviction per giustificare R:R ≥ 3:1 con target fisso: uscire anticipatamente o ridurre il target per 'sicurezza' sarebbe stato un errore atteso-negativo. La confluenza momentum + order-flow su alt-L1 genera move intraday completi — non scalare out prima del target.
- [[tsmom-liq-v1]] · **thesis_wrong** (WLD): segnali tsmom+liq_imbalance su token narrativi a bassa capitalizzazione catturano spesso momentum di brevissimo termine (spike di liquidità) che si esaurisce entro poche candele: senza un filtro di regime (BTC sopra MA su H4, settore AI/L1 in risk-on) il segnale long su altcoin volatili ha tasso di falsi positivi strutturalmente alto e va ridotto in size o saltato
- [[tsmom-liq-v1]] · **execution_issue** (NEAR): Quando tsmom + liq_imbalance si allineano su altcoin ad alta beta (NEAR, SOL-tier), uno stop fisso <3% viene consumato dal rumore intraday prima che il momentum si materializzi: il minimo stop deve essere ≥1.5× ATR daily del simbolo; in alternativa ridurre la size proporzionalmente per mantenere il risk assoluto costante con uno stop più largo.
- [[tsmom-liq-v1]] · **execution_issue** (WLD): Un segnale tsmom è per definizione costruito su finestre giornaliere (o multi-ora): lo stop deve essere ≥ 1× ATR-giornaliero del sottostante, altrimenti il rumore intraday esaurisce il margine prima che la tesi si materializzi. WLD ha ATR-daily ~5-8%; uno stop al 2.5% sotto l'entry entra direttamente nella fascia di rumore e viene colpito statisticamente anche quando la direzione è corretta. Regola generale: su strategie momentum a bassa frequenza, calibra lo stop sul timeframe del segnale (daily ATR), non sulla tolleranza di rischio in USD — aggiusta il size per tenere il rischio fisso, non restringere lo stop.
- [[tsmom-conservative-v1]] · **thesis_right** (xyz_CL): Un segnale tsmom = -1 su futures energetici liquidi in trend ribassista porta il prezzo al target 3:1 entro 3-5 sessioni; non intervenire discrezionalmente sul target meccanico — l'edge della strategia si realizza lasciando girare il winner fino al livello stabilito.
- [[tsmom-liq-v1]] · **thesis_wrong** (ZEC): In fasi di downtrend strutturale su altcoin ad alta beta (ZEC), segnali tsmom+liq_imbalance rialzisti catturano spesso picchi di crowding long piuttosto che momentum genuino: il segnale si accende quando tutti sono già entrati, non quando inizia la spinta. Richiedere un regime-filter esplicito (es. BTC price > MA20 o rolling-Sharpe basket > 0) prima di approvare long su tsmom in altcoin.
- [[tsmom-liq-v1]] · **execution_issue** (CRV): Segnali tsmom+liq_imbalance su token DeFi small-cap richiedono un filtro di regime esplicito: in mercato bear/laterale, gli squilibri di liquidità su CRV-class asset sono noise e non segnale direzionale — long momentum senza conferma macro (es. BTC sopra EMA breve o realized-vol sotto soglia) producono whipsaw sistematici il cui stop-rate supera l'alpha atteso del setup.
- [[tsmom-liq-v1]] · **execution_issue** (WLD): Su altcoin ad alta volatilità (WLD, float basso), uno stop fisso %-based ignora l'ATR del timeframe: un'oscillazione di 2.5% in 1h è rumore ordinario, non invalidazione della tesi. I segnali tsmom+liq_imbalance erano coerenti ma lo stop è stato piazzato dentro il noise-band — regola: stop su tsmom-liq entries deve essere ≥1× ATR(4h) per sopravvivere al mean-reversion intra-candle senza che la tesi direzionale venga falsificata.
- [[tsmom-liq-v1]] · **thesis_wrong** (CRV): tsmom + liq_imbalance simultanei su token DeFi (bassa cap, alto crowding) possono riflettere momentum già esaurito al momento del segnale — non un'accelerazione in corso. Regola generale: in regime neutro/bear su BTC, esigere N ore di persistenza del segnale (es. 2+ candle di conferma) e coerenza col trend ETH prima di entrare long su DeFi; un segnale intracandle fermato in <1h indica che la liq_imbalance era noise temporaneo, non pressione direzionale sostenuta.
- [[agents-v1]] · **thesis_wrong** (ZEC): Doppia confluenza tsmom+vwap_zscore su candele già estese segna esaurimento, non continuazione: quando la tesi stessa riconosce il crowding e risponde solo con size ridotta, il segnale qualitativo deve essere invertito. Crowding consapevole + momentum tardivo post-rally = peso contrarian implicito ignorato. La size al 50% mitiga la perdita ma non cambia il segno dell'edge atteso. Regola generale: se la tesi contiene 'il rischio X è reale ma lo gestisco con Y', X è probabilmente la causa principale del fallimento e Y è razionalizzazione.
- [[tsmom-liq-v1]] · **execution_issue** (WLD): Su token illiquidi ad alta volatilità (WLD-class), uno stop fisso al 2.5% rientra nel rumore di breve periodo: il trade è stato stoppato in 12h su movimento di ~1.7bp dal close. Gli stop devono essere calibrati sull'ATR dell'asset specifico (minimo 1×ATR daily), non su una percentuale flat derivata da asset più liquidi come BTC/ETH — altrimenti il segnale corretto viene annullato da volatilità casuale prima che la tesi possa esprimersi.
- [[tsmom-liq-v1]] · **thesis_wrong** (CRV): tsmom+liq_imbalance=1 su governance DeFi token con distribuzione strutturale (ve-overhang, TVL/fees in calo) cattura un ingresso crowded, non momentum organico: tutti i sistemi sistematici ricevono lo stesso trigger simultaneamente, il liq_imbalance=1 riflette gli ordini degli altri modelli tsmom, non domanda spot genuina, e la mean-reversion avviene entro 12-24h prima che la tesi si dispieghi. Regola generale: su DeFi governance token, esigere tsmom positivo su lookback ≥30g (non solo 7g) E conferma che il ratio DeFi-sector/BTC sia in uptrend settimanale prima di considerare liq_imbalance una conferma valida.

## #tsmom-liq-v1

- [[tsmom-liq-v1]] · **execution_issue** (NEAR): Exit price (2.2725) è sotto entry (2.3664) su un long, ma PnL registrato è +$178. Inoltre ts_close (02:00) precede opened_at (04:00) di 2 ore. Il record è strutturalmente corrotto: il sistema deve validare sign(exit_px - entry_px) == sign(pnl_usd) per i long e ts_close > ts_open prima di persistere su journal — ogni post-mortem su dati incoerenti produce lezioni spurie e degrada il backtest.

## #tsmom_liq

- [[tsmom-liq-v1]] · **execution_issue** (WLD): Il PnL (+$174.63 su $2390.57 = 7.3%) è coerente con un fill al target (0.7286, +7.5%) ma exit_px registra 0.6872 (+1.4%) — discrepanza ~5x: il logger sta scrivendo il mark price al momento del log invece del fill price simulato. Aggravante: close.logged_at (20:16) precede open.logged_at (21:15) e open_ts == close_ts (stesso candle), indicando race condition nel pipeline. In paper trading, separare rigorosamente fill_px (prezzo di esecuzione deterministico, fissato all'istante del segnale) da mark_px (prezzo corrente al momento del log); finché il campo è ambiguo ogni post-mortem futuro è invalido indipendentemente dalla direzione del mercato.

## #ve_overhang

- [[tsmom-liq-v1]] · **thesis_wrong** (CRV): tsmom+liq_imbalance=1 su governance DeFi token con distribuzione strutturale (ve-overhang, TVL/fees in calo) cattura un ingresso crowded, non momentum organico: tutti i sistemi sistematici ricevono lo stesso trigger simultaneamente, il liq_imbalance=1 riflette gli ordini degli altri modelli tsmom, non domanda spot genuina, e la mean-reversion avviene entro 12-24h prima che la tesi si dispieghi. Regola generale: su DeFi governance token, esigere tsmom positivo su lookback ≥30g (non solo 7g) E conferma che il ratio DeFi-sector/BTC sia in uptrend settimanale prima di considerare liq_imbalance una conferma valida.

## #vol_compression

- [[agents-v1]] · **execution_issue** (SUI): Vol_compression + funding-squeeze long su L1 altcoin consegna tipicamente 3-7% di reversion intra-giornaliera, non 18%: quando il catalizzatore è 'esaurimento pressione ribassista' (non breakout macro), il target deve essere calibrato sulla magnitudine attesa dello squeeze (R:R compresso ma alta probabilità) e il time_stop deve essere proporzionato — 48h è coerente con la tesi, ma abbinarlo a un target x3 crea un'asimmetria impossibile: il trade chiude a time_stop catturando solo il 30% del premio atteso. Separare il sizing del target in base al tipo di driver: squeeze → target 5-8%, breakout strutturale → target 15%+.
- [[agents-v1]] · **thesis_right** (ZEC): Vol compression su un asset già in bull regime primario è un setup asimmetrico: il regime trasforma un pattern neutro in un entry direzionale ad alta probabilità. La selezione per regime nel basket (1/5 in bull vs 4/5 in chop) è il filtro che converte il segnale tecnico in edge — senza quel filtro lo stesso setup su un asset in chop non avrebbe la stessa aspettativa. Generalizzazione: quando si fa basket selection, cercare il regime outlier positivo e concentrare la posizione lì, non diversificare su tutti i segnali.

## #vwap

- [[vwap-reversion-v1]] · **thesis_wrong** (basket): Fade dell'estensione VWAP falsificato 7/7 asset (crypto+commodities+stock): le estensioni oltre 2 sigma IN QUESTO regime sono trend, non esaurimenti. Terza falsificazione consecutiva di tesi mean-reversion (dopo scalp-exit e flow-fade): il regime 2026 H1 premia il trend following, punisce il contrarian.

## #vwap_zscore

- [[agents-v1]] · **thesis_wrong** (SUI): Un vwap_zscore=1 (1σ) in altcoin ad alta beta è sotto la soglia minima di edge: il rapporto segnale/rumore è insufficiente a sopravvivere alla normale volatilità intraday senza un catalizzatore strutturale aggiuntivo (volume >1.5x media 4h o zscore ≥1.5). La relative strength intraday punto-in-tempo (+2.8%) non è una proxy affidabile di momentum sostenuto se non è confermata da espansione volumetrica nel tick successivo all'ingresso — senza follow-through misurato entro 2h, il segnale va trattato come rumore e il trade chiuso in pareggio.

## #whipsaw

- [[tsmom-v1]] · **thesis_wrong** (BTC): Un segnale TSMOM short su BTC dopo un drawdown multi-giorno tende a coincidere con l'esaurimento del momentum ribassista, non con la sua accelerazione. Prima di entrare short su TSMOM in contesti di alta volatilità, esigere conferma strutturale (es. incapacità di rimbalzo su daily close o break di supporto volumetrico) per distinguere trend in atto da momentum già consumato.
- [[tsmom-v1]] · **thesis_wrong** (ETH): Il segnale tsmom -1 era tecnicamente valido sul passato ma il momentum aveva già esaurito la direzionalità: ETH a 1660 era vicino all'estremo del drawdown recente e il prezzo ha immediatamente invertito. Un filtro di 'freshness' (il segnale -1 deve essere presente da ≤2 barre, non cronico) e la conferma cross-sectional (ETH sotto-performante rispetto al basket nella stessa finestra) separano i momentum genuini dai falsi segnali in regime di possibile mean-reversion.
- [[tsmom-liq-v1]] · **execution_issue** (CRV): Segnali tsmom+liq_imbalance su token DeFi small-cap richiedono un filtro di regime esplicito: in mercato bear/laterale, gli squilibri di liquidità su CRV-class asset sono noise e non segnale direzionale — long momentum senza conferma macro (es. BTC sopra EMA breve o realized-vol sotto soglia) producono whipsaw sistematici il cui stop-rate supera l'alpha atteso del setup.

## #xrp_volatility

- [[tsmom-liq-v1]] · **execution_issue** (XRP): Quando tsmom e liq_imbalance convergono (-1/-1) il segnale è solido, ma su asset ad alta volatilità intraday (XRP, ATR giornaliero > 3%) uno stop a ~2.5% cade dentro la banda di rumore e non fuori dalla tesi. Gli stop di momentum-liq vanno calibrati su 1.5-2x ATR del timeframe del segnale, non su una percentuale fissa: altrimenti ogni rimbalzo tecnico di 5h elimina il trade prima che la direzionalità si esprima.
