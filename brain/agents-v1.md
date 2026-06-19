# agents-v1

[[README|← Brain index]]

## Anagrafica

- **status**: live
- _nessuno spec YAML: pagina da dati runtime_

## Performance (paper)

- equity: $10,322.30
- trade chiusi: 9 · win rate: 44%
- PnL totale: $327.60
- posizioni aperte ora: 2

### Posizioni aperte

| symbol | dir | entry | stop | target | size |
|---|---|---|---|---|---|
| SOL | long | 72.3214614 | 67.258959102 | 87.508968294 | $1,101.36 |
| ZEC | long | 454.300842 | 438.40031252999995 | 494.05216567499997 | $884.80 |

### Trade chiusi

| symbol | reason | exit | PnL |
|---|---|---|---|
| ZEC | stopped | 417.94148328234 | $-50.92 |
| SUI | time_stop | 0.795260916 | $55.66 |
| ZEC | target | 498.45848006166 | $148.62 |
| SOL | target | 75.4788869808444 | $185.38 |
| SOL | time_stop | 73.5332904 | $-27.11 |
| ZEC | stopped | 496.40898014363995 | $-26.21 |
| SOL | time_stop | 73.5682834 | $-1.66 |
| SUI | stopped | 0.7728724690851 | $-52.07 |
| ZEC | target | 447.62373209505 | $95.91 |

## Lezioni

- **execution_issue** (ZEC, $-50.92): Lo stop deve coincidere con l'invalidazione dichiarata della tesi, mai essere piu stretto: qui stop 418 vs invalidazione 415 - usciti prima che la tesi morisse. Se lo stop coerente rende il rischio troppo grande, ridurre la size, non stringere lo stop. #execution #stop-placement #invalidation
- **thesis_wrong** (ZEC, $-50.92): Fade contro trend (squeeze su crowding) dopo un +5% giornaliero = comprare il rimbalzo gia esteso. In bear regime l'entry squeeze richiede conferma (retest del breakout o capitolazione OI), non anticipazione. Conferma la lezione gen1-3 del loop evolutivo: il crowding da solo non basta contro il trend. #counter-trend #squeeze #timing #bear-regime
- **execution_issue** (SUI, $55.66): Vol_compression + funding-squeeze long su L1 altcoin consegna tipicamente 3-7% di reversion intra-giornaliera, non 18%: quando il catalizzatore è 'esaurimento pressione ribassista' (non breakout macro), il target deve essere calibrato sulla magnitudine attesa dello squeeze (R:R compresso ma alta probabilità) e il time_stop deve essere proporzionato — 48h è coerente con la tesi, ma abbinarlo a un target x3 crea un'asimmetria impossibile: il trade chiude a time_stop catturando solo il 30% del premio atteso. Separare il sizing del target in base al tipo di driver: squeeze → target 5-8%, breakout strutturale → target 15%+. #vol_compression #funding_squeeze #target_miscalibration #time_stop #l1_altcoin #reversion_vs_breakout
- **thesis_right** (ZEC, $148.62): Vol compression su un asset già in bull regime primario è un setup asimmetrico: il regime trasforma un pattern neutro in un entry direzionale ad alta probabilità. La selezione per regime nel basket (1/5 in bull vs 4/5 in chop) è il filtro che converte il segnale tecnico in edge — senza quel filtro lo stesso setup su un asset in chop non avrebbe la stessa aspettativa. Generalizzazione: quando si fa basket selection, cercare il regime outlier positivo e concentrare la posizione lì, non diversificare su tutti i segnali. #vol_compression #bull_regime #basket_selection #regime_outlier #pre_expansion
- **thesis_right** (SOL, $185.38): Funding negativo strutturale su asset con regime bull confermato e outperformance spot vs paniere crea uno squeeze lento ma prevedibile: i derivati fungono da carburante direzionale anziché da resistenza. La confluenza funding-negativo + spot-outperformance-vs-basket è un setup ad alto valore con invalidazione netta e misurabile (funding flip), replicabile su qualsiasi perpetual liquido indipendentemente dall'asset specifico. #negative_funding #short_squeeze #bull_regime #derivatives_confluence #basket_relative_strength #trend_following
- **execution_issue** (SOL, $-27.11): Funding negativo mite (−0.25% APR ≈ rumore neutro) non genera squeeze meccanico materiale: la pressione di auto-liquidazione diventa concreta solo sotto −1% APR o quando il gradiente di funding accelera verso neutro (≥0.05% APR/h nelle ultime 4h). Un time-stop da 12h è incongruente con una tesi di compressione funding lenta: o si entra solo quando la compressione è già in corso (momentum del funding, non livello), oppure si estende il time-stop a ≥24h dimezzando la size. Il volume_surge era un segnale direzionale valido, ma non è un proxy del timing dello squeeze. #funding_squeeze #funding_threshold #time_stop_mismatch #execution_mismatch #sol
- **thesis_wrong** (ZEC, $-26.21): Doppia confluenza tsmom+vwap_zscore su candele già estese segna esaurimento, non continuazione: quando la tesi stessa riconosce il crowding e risponde solo con size ridotta, il segnale qualitativo deve essere invertito. Crowding consapevole + momentum tardivo post-rally = peso contrarian implicito ignorato. La size al 50% mitiga la perdita ma non cambia il segno dell'edge atteso. Regola generale: se la tesi contiene 'il rischio X è reale ma lo gestisco con Y', X è probabilmente la causa principale del fallimento e Y è razionalizzazione. #momentum-lag #crowding #altcoin-exhaustion #tsmom #post-extended-candle #thesis-self-contradiction
- **execution_issue** (SOL, $-1.66): Un time-stop di 24h è strutturalmente incoerente con una tesi basata su rotazione di capitale a 7 giorni e catalizzatori macro (Iran/BOJ): il regime bull e il funding negativo non erano stati invalidati, il prezzo è uscito piatto (−0.16%) non perché la tesi fosse sbagliata ma perché la finestra di holding era troppo corta per far emergere l'edge. Regola generale: il time-stop deve essere ≥ metà del lookback usato per costruire la tesi — tesi su momentum 7d → time-stop minimo 72-96h; altrimenti si vende rumore intraday su una tesi strutturale. #time_stop_mismatch #structural_thesis #holding_period_calibration #momentum_long #SOL
- **thesis_wrong** (SUI, $-52.07): Un vwap_zscore=1 (1σ) in altcoin ad alta beta è sotto la soglia minima di edge: il rapporto segnale/rumore è insufficiente a sopravvivere alla normale volatilità intraday senza un catalizzatore strutturale aggiuntivo (volume >1.5x media 4h o zscore ≥1.5). La relative strength intraday punto-in-tempo (+2.8%) non è una proxy affidabile di momentum sostenuto se non è confermata da espansione volumetrica nel tick successivo all'ingresso — senza follow-through misurato entro 2h, il segnale va trattato come rumore e il trade chiuso in pareggio. #signal_threshold #vwap_zscore #momentum #altcoin_high_beta #entry_filter #relative_strength_decay
- **thesis_right** (ZEC, $95.91): Su asset illiquidi (ZEC-tier), la combinazione rally >15% senza catalizzatore fondamentale + primo pullback significativo con funding ancora positivo è un segnale di distribuzione ad alta fedeltà: i longs sono intrappolati e non capitolano, il che concentra la pressione sell sul successivo leg down. Il trade ha raggiunto il target (-12.5%) in 36h su 48h disponibili — conferma che il time-stop va calibrato sul tempo di esaurimento del crowding, non sulla volatilità asset. In regime bear o neutro, questo setup (funding positivo + price action negativa) è più affidabile che il fade di momentum puro perché incorpora informazione di positioning. #mean-reversion #funding-signal #crowding-exhaustion #illiquid-asset #distribution #short-setup #thesis-confirmed

[[lessons|Tutte le lezioni]] · [[timeline|Timeline]]
