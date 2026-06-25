# glm-regime-confluence-v1

[[README|← Brain index]]

## Anagrafica

- **status**: live (paper)
- **creatore**: glm-5.2 (Z.ai Coding Plan)
- _nessuno spec YAML: strategia script (`scripts/glm_strategy.py`), pagina da dati runtime_

## Tesi

Edge = confluenza di due lenti momentum **ortogonali** che concordano:
`tsmom` (trend assoluto, Moskowitz-Ooi-Pedersen) + `xsection_momentum`
(forza relativa nel basket, market-neutral → netta il beta comune).
Accordo assoluto+relativo = il move non è drift di mercato, è alpha
relativo confermato. Diverso da `lux-confluence` (tsmom+liq+kronos) e
da `claude-strategy` (tsmom+liq): qui due momentum indipendenti, non
trend+flow.

Veto hard: `news_event` attivo (event-risk, il tono è falsificato ma la
volatilità no) · `kronos_vol` alta (regime imprevedibile) ·
`funding_percentile` estremo **contro** direzione (crowding headwind,
lezione `altcoin-exhaustion`).

Conviction vote (0-4): `hmm_regime`·`taker_flow`·`smart_money_ratio`·
`oi_trend` allineati al core. `hmm` solo su BTC/ETH → score degrada
0-3 sugli altri, gate resta valido.

LLM (glm-5.2) = **auditor di portafoglio**, non oracolo: giudica solo
rischio di correlazione col book aperto. Una chiamata, solo se il gate
ha candidati.

Exit: stop 2×ATR (floor 1×ATR, lezione `altcoin_volatility`), target_r
2.0 (crypto, RR2 batte RR3), time_stop 96h (tesi momentum 7d, lezione
`SOL execution_issue`).

**Falsificata se**: su basket crypto liquido (BTC,ETH,SOL,SUI,NEAR,XRP,
WLD,ZEC,CRV) non batte buy-and-hold risk-adjusted su 6 mesi paper, o se
il filtro xsection non riduce il drawdown vs tsmom puro.
