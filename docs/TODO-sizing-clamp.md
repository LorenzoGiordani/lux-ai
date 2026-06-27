# TODO: sizing clamp invece di hard_veto (design approvato, da implementare)

Stato: **approvato**, bloccato temporaneamente da bypass di test (vedi sotto).
Implementare quando il bypass verrà rimosso.

## Contesto
69 trade su 69 bloccati (storico) lo erano SOLO per sizing: leva 31, risk_pct 22,
stop_alto 16. Le tesi erano spesso buone. Buttare un trade per "leva 3 > 2" è
sprecato, soprattutto perché la leva dichiarata spesso non è nemmeno il vincolo
attivo (exposure = min(leverage, risk_pct/stop_pct)).

## Design
`hard_check` in `scripts/decide.py` distingue due categorie:

### CLAMP (corregge e lascia passare)
- `leverage > max` → clamp a max_leverage (2.0). Spesso inattivo nel sizing reale.
- `risk_pct > max` → clamp a max_risk_per_trade_pct (1.0).
- `stop_pct > hi` → clamp a hi (8.0). Stop più stretto = più conservativo.

Restituisce `(errs, clamps)` dove clamps è la lista delle correzioni applicate.
Il chiamante registra `sizing_clamped: clamps` nella decisione (trasparenza).

### RESTA VETO (strutturale, non riducibile)
- `stop_pct < lo` (0.5) o `stop < 1×ATR` → noise-stop, #1 causa execution_issue
- `max_concurrent_positions` → non puoi "ridurre" una nuova posizione
- `direction`/`thesis`/`invalidation` mancanti → difetto di qualità del trade

## Perché non viola "insindacabile"
Il limite resta un muro, non un suggerimento: non è l'LLM che decide il sizing
finale, è il sistema che lo impone deterministicamente. Più rigoroso del veto
(corregge invece di buttare).

## Mitigazione moral hazard
- Log trasparente: il trade eseguito porta `sizing_clamped`
- Clamp solo su parametri riducibili, mai su quelli strutturali
- Tesi cattive muoiono comunque al risk gate LLM (strato 2) e sul campo

## Chiamanti da aggiornare
- scripts/decide.py (main)
- scripts/glm_strategy.py:131
- scripts/geopolitics_paper.py:111
- scripts/claude_strategy.py:85
Tutti chiamano `hard_check(proposal, atr_by_symbol=...)`. Cambiare la signature
in `(errs, clamps)` e gestire entrambi.
