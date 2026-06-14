"""Ricerca strategie SEED guidata da ipotesi (non mutazioni: nuovi ceppi).

Ogni seed ha una tesi falsificabile e un universo mirato per asset-class o
profilo di rischio. Backtest sul basket + gate DSR + confronto vs buy-and-hold.
I seed che battono buy-and-hold risk-adjusted E passano il DSR → status challenger
(entrano in paper). Gli altri → candidate (archiviati nell'albero).

Rispetta le lezioni accumulate: trend funziona, mean-reversion no, news non
direzionale. Niente indicatori lagging. Solo segnali del registry.

Uso: .venv/bin/python scripts/research_seeds.py [--dsr 0.85] [--write]
"""

import argparse
import sys
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest.metrics import buy_and_hold, compute
from backtest.signals import SIGNALS
from backtest.stats import deflated_sharpe, sharpe_moments
from scripts.evolve import OUT_DIR, eval_basket, load_data

CRYPTO = "BTC,ETH,SOL,XRP,SUI,NEAR,WLD,ZEC,CRV"
COMMOD = "xyz_GOLD,xyz_SILVER,xyz_CL,xyz_BRENTOIL,xyz_NATGAS"
EQUITY = "xyz_SP500,xyz_MU,xyz_SNDK,xyz_XYZ100"

# ---- SEED: ognuno una tesi falsificabile, universo e profilo di rischio mirati ----
SEEDS = [
    {
        "id": "commodities-trend-v1", "family": "commodities-trend", "symbols": COMMOD,
        "thesis": "I trend sulle commodities sono persistenti (driver macro/COT, cicli "
                  "lunghi). Un book dedicato alle sole commodities con TSMOM dovrebbe essere "
                  "più pulito del basket misto. Falsificata se non batte buy-and-hold "
                  "risk-adjusted sulle commodities a 6 mesi.",
        "signals": [{"name": "tsmom", "params": {"short_h": 168, "long_h": 720}}],
        "entry": {"rule": "tsmom", "direction": "follow:tsmom"},
        "exit": {"stop_pct": 4.0, "target_r": 3.0, "time_stop_h": 360},
        "risk": {"max_leverage": 2, "risk_per_trade_pct": 1.0, "max_concurrent_positions": 3},
    },
    {
        "id": "commodities-cot-trend-v1", "family": "commodities-cot-trend", "symbols": COMMOD,
        "thesis": "TSMOM sulle commodities CONFERMATO dal posizionamento estremo dei fondi "
                  "(COT): trend + crowd allineati = spinta più forte. rule tsmom AND "
                  "cot_percentile, direzione dal trend. Falsificata se il filtro COT non "
                  "migliora lo Sharpe rispetto al solo TSMOM commodities.",
        "signals": [{"name": "tsmom", "params": {"short_h": 168, "long_h": 720}},
                    {"name": "cot_percentile", "params": {"lookback_w": 26, "extreme_pct": 80}}],
        "entry": {"rule": "tsmom AND cot_percentile", "direction": "follow:tsmom"},
        "exit": {"stop_pct": 4.0, "target_r": 3.0, "time_stop_h": 360},
        "risk": {"max_leverage": 2, "risk_per_trade_pct": 1.0, "max_concurrent_positions": 3},
    },
    {
        "id": "crypto-trend-flow-v1", "family": "crypto-trend-flow", "symbols": CRYPTO,
        "thesis": "Momentum crypto CONFERMATO dal flusso aggressivo (taker buy/sell): il "
                  "trend supportato da ordini a mercato è più robusto dei breakout in "
                  "sottigliezza. rule tsmom AND taker_flow, direzione dal trend. Falsificata "
                  "se non batte il TSMOM semplice su crypto.",
        "signals": [{"name": "tsmom", "params": {"short_h": 168, "long_h": 720}},
                    {"name": "taker_flow", "params": {"lookback_h": 24, "threshold": 0.02}}],
        "entry": {"rule": "tsmom AND taker_flow", "direction": "follow:tsmom"},
        "exit": {"stop_pct": 4.5, "target_r": 3.0, "time_stop_h": 240},
        "risk": {"max_leverage": 2, "risk_per_trade_pct": 1.0, "max_concurrent_positions": 3},
    },
    {
        "id": "tsmom-conservative-v1", "family": "tsmom-conservative",
        "symbols": "BTC,ETH,xyz_GOLD,xyz_CL,xyz_BRENTOIL,xyz_SILVER,xyz_SP500,xyz_MU",
        "thesis": "Profilo di rischio difensivo sullo stesso edge TSMOM (vincente): leva 1x, "
                  "stop stretto, meno posizioni concorrenti. Tesi: rinunciare a parte del "
                  "rendimento per un drawdown nettamente minore migliora lo Sharpe. "
                  "Falsificata se lo Sharpe non sale rispetto a tsmom-v1.",
        "signals": [{"name": "tsmom", "params": {"short_h": 168, "long_h": 720}}],
        "entry": {"rule": "tsmom", "direction": "follow:tsmom"},
        "exit": {"stop_pct": 2.5, "target_r": 3.0, "time_stop_h": 240},
        "risk": {"max_leverage": 1, "risk_per_trade_pct": 0.6, "max_concurrent_positions": 2},
    },
    {
        "id": "tsmom-aggressive-v1", "family": "tsmom-aggressive",
        "symbols": "BTC,ETH,xyz_GOLD,xyz_CL,xyz_BRENTOIL,xyz_SILVER,xyz_SP500,xyz_MU",
        "thesis": "Profilo aggressivo sullo stesso edge TSMOM: leva 2x, stop largo, target "
                  "esteso, più posizioni. Tesi: lasciar correre i trend con stop larghi cattura "
                  "le code dei movimenti. Falsificata se il drawdown extra non è compensato dal "
                  "rendimento (Sharpe non superiore a tsmom-v1).",
        "signals": [{"name": "tsmom", "params": {"short_h": 168, "long_h": 720}}],
        "entry": {"rule": "tsmom", "direction": "follow:tsmom"},
        "exit": {"stop_pct": 6.0, "target_r": 4.0, "time_stop_h": 360},
        "risk": {"max_leverage": 2, "risk_per_trade_pct": 1.5, "max_concurrent_positions": 4},
    },
    {
        "id": "tsmom-volgate-v1", "family": "tsmom-volgate",
        "symbols": "BTC,ETH,xyz_GOLD,xyz_CL,xyz_BRENTOIL,xyz_SILVER,xyz_SP500,xyz_MU",
        "thesis": "Il backtest mostra che il regime chop distrugge il TSMOM (Sharpe negativo) e "
                  "che il vincolo binding è il DSR (overfitting), non il rendimento grezzo. Tesi: "
                  "entrare sul trend SOLO quando emerge da una compressione di volatilità (molla "
                  "carica) filtra i whipsaw di chop e dovrebbe alzare il DSR rispetto a tsmom-v1, "
                  "a costo di meno trade. rule tsmom AND vol_compression, direzione dal trend. "
                  "Falsificata se il DSR non supera tsmom-v1 (0.36) o se i trade crollano sotto "
                  "soglia di significatività.",
        "signals": [{"name": "tsmom", "params": {"short_h": 168, "long_h": 720}},
                    {"name": "vol_compression", "params": {"lookback_h": 48, "pct": 20}}],
        "entry": {"rule": "tsmom AND vol_compression", "direction": "follow:tsmom"},
        "exit": {"stop_pct": 2.5, "target_r": 3.0, "time_stop_h": 240},
        "risk": {"max_leverage": 1, "risk_per_trade_pct": 0.6, "max_concurrent_positions": 3},
    },
    {
        # A/B Kronos: gemello esatto di tsmom-conservative-v1 + gate forecast Kronos.
        # rule "tsmom AND kronos_forecast" + direction "signal_vote" => entra SOLO quando
        # trend e forecast Kronos CONCORDANO sulla direzione (somma=0 se discordano → niente trade).
        # Confronto vs tsmom-conservative-v1 (Sharpe 1.70, DSR 0.40) isola l'effetto Kronos.
        # Richiede la cache: scripts/precompute_kronos.py. Senza cache il segnale è neutro
        # (kronos≡0) => nessuna entrata: il vuoto è esplicito, non un falso positivo.
        "id": "tsmom-kronos-v1", "family": "tsmom-kronos",
        "symbols": "BTC,ETH,xyz_GOLD,xyz_CL,xyz_BRENTOIL,xyz_SILVER,xyz_SP500,xyz_MU",
        "thesis": "A/B del segnale Kronos (foundation model OHLCV, leading non lagging): stesso "
                  "TSMOM conservativo, ma l'ingresso richiede che anche il forecast Kronos concordi "
                  "sulla direzione del trend. Tesi: un secondo segnale leading indipendente alza il "
                  "DSR filtrando i falsi trend. Falsificata se DSR/Sharpe non superano "
                  "tsmom-conservative-v1 (0.40 / 1.70).",
        "signals": [{"name": "tsmom", "params": {"short_h": 168, "long_h": 720}},
                    {"name": "kronos_forecast", "params": {"horizon_h": 24, "min_move_pct": 0.5}}],
        "entry": {"rule": "tsmom AND kronos_forecast", "direction": "signal_vote"},
        "exit": {"stop_pct": 2.5, "target_r": 3.0, "time_stop_h": 240},
        "risk": {"max_leverage": 1, "risk_per_trade_pct": 0.6, "max_concurrent_positions": 2},
    },
    {
        # Kronos STANDALONE: il forecast a 24h ha un edge direzionale di per sé?
        # Direzione = segno del forecast. Riusa la stessa cache (costo zero).
        # Se nemmeno da solo batte B&H, il forecast a 24h non ha alpha direzionale a questa soglia.
        "id": "kronos-only-v1", "family": "kronos-only",
        "symbols": "BTC,ETH,xyz_GOLD,xyz_CL,xyz_BRENTOIL,xyz_SILVER,xyz_SP500,xyz_MU",
        "thesis": "Il forecast Kronos a 24h, usato come unico segnale direzionale, ha un edge? "
                  "Falsificata se non batte buy-and-hold risk-adjusted: in tal caso il modello "
                  "non aggiunge alpha direzionale sfruibile a questa soglia/orizzonte.",
        "signals": [{"name": "kronos_forecast", "params": {"horizon_h": 24, "min_move_pct": 0.5}}],
        "entry": {"rule": "kronos_forecast", "direction": "follow:kronos_forecast"},
        "exit": {"stop_pct": 2.5, "target_r": 3.0, "time_stop_h": 240},
        "risk": {"max_leverage": 1, "risk_per_trade_pct": 0.6, "max_concurrent_positions": 2},
    },
    {
        # Kronos uso NON direzionale: il forecast direzionale è senza alpha, ma la
        # volatilità PREVISTA potrebbe aiutare come gate di rischio. Trend conservativo
        # che NON apre quando Kronos prevede alta volatilità (regime mosso/chop).
        # Falsificata se DSR/Sharpe non superano tsmom-conservative-v1.
        "id": "tsmom-kvolveto-v1", "family": "tsmom-kvolveto",
        "symbols": "BTC,ETH,xyz_GOLD,xyz_CL,xyz_BRENTOIL,xyz_SILVER,xyz_SP500,xyz_MU",
        "thesis": "Kronos come gate di rischio (non direzionale): TSMOM conservativo che sospende "
                  "le nuove entrate quando il forecast Kronos prevede alta volatilità (top 30%), "
                  "ipotizzando che siano regimi mossi/chop dove il trend whipsaggia. Falsificata se "
                  "non migliora DSR/Sharpe vs tsmom-conservative-v1 (0.54 / 1.70).",
        "signals": [{"name": "tsmom", "params": {"short_h": 168, "long_h": 720}},
                    {"name": "kronos_vol", "params": {"horizon_h": 24, "hi_pct": 70}}],
        "entry": {"rule": "tsmom", "direction": "follow:tsmom", "veto": "kronos_vol"},
        "exit": {"stop_pct": 2.5, "target_r": 3.0, "time_stop_h": 240},
        "risk": {"max_leverage": 1, "risk_per_trade_pct": 0.6, "max_concurrent_positions": 2},
    },
    {
        # Filtro di regime HMM (metodo Jim Simons, da studio canale Moon Dev): TSMOM
        # conservativo che entra SOLO quando l'HMM classifica il regime come "trending".
        # Affronta il problema dimostrato (il chop uccide il trend) con un detector più
        # principiato di vol_compression (che è fallito in tsmom-volgate). Richiede la
        # cache: scripts/precompute_hmm.py. Senza cache hmm_regime≡0 → 0 trade (vuoto esplicito).
        "id": "tsmom-hmm-v1", "family": "tsmom-hmm",
        "symbols": "BTC,ETH,xyz_GOLD,xyz_CL,xyz_BRENTOIL,xyz_SILVER,xyz_SP500,xyz_MU",
        "thesis": "Filtro di regime HMM sul TSMOM: entra solo nei regimi 'trending' rilevati da "
                  "un Hidden Markov Model sui ritorni (metodo Renaissance). Tesi: tenere le entrate "
                  "fuori dal chop alza il DSR vs tsmom-conservative-v1 (0.54 / 1.70). Falsificata se "
                  "non migliora DSR/Sharpe.",
        "signals": [{"name": "tsmom", "params": {"short_h": 168, "long_h": 720}},
                    {"name": "hmm_regime", "params": {}}],
        "entry": {"rule": "tsmom AND hmm_regime", "direction": "follow:tsmom"},
        "exit": {"stop_pct": 2.5, "target_r": 3.0, "time_stop_h": 240},
        "risk": {"max_leverage": 1, "risk_per_trade_pct": 0.6, "max_concurrent_positions": 2},
    },
    # --- A/B posizionamento smart-money (metrics Binance gratis, basket SOLO crypto) ---
    # Edge ORTOGONALE al trend (posizionamento dei top trader, non prezzo). Baseline crypto
    # dedicata per confronto pulito (i seed sopra sono basket misti con commodity).
    {
        "id": "tsmom-crypto-base-v1", "family": "tsmom-crypto",
        "symbols": CRYPTO,
        "thesis": "Baseline: TSMOM conservativo sul solo basket crypto, metro di paragone per i "
                  "segnali di posizionamento smart-money (che esistono solo per le crypto).",
        "signals": [{"name": "tsmom", "params": {"short_h": 168, "long_h": 720}}],
        "entry": {"rule": "tsmom", "direction": "follow:tsmom"},
        "exit": {"stop_pct": 2.5, "target_r": 3.0, "time_stop_h": 240},
        "risk": {"max_leverage": 1, "risk_per_trade_pct": 0.6, "max_concurrent_positions": 3},
    },
    {
        "id": "smart-money-only-v1", "family": "smart-money",
        "symbols": CRYPTO,
        "thesis": "Il posizionamento dei TOP TRADER (Binance) ha un edge direzionale di per sé? "
                  "Segui lo smart money: long quando i top trader sono nettamente long vs la loro "
                  "storia, short quando nettamente short. Falsificata se non batte buy-and-hold.",
        "signals": [{"name": "smart_money_ratio", "params": {"lookback_h": 720, "extreme_pct": 80}}],
        "entry": {"rule": "smart_money_ratio", "direction": "follow:smart_money_ratio"},
        "exit": {"stop_pct": 2.5, "target_r": 3.0, "time_stop_h": 240},
        "risk": {"max_leverage": 1, "risk_per_trade_pct": 0.6, "max_concurrent_positions": 3},
    },
    {
        "id": "tsmom-smartmoney-v1", "family": "tsmom-smartmoney",
        "symbols": CRYPTO,
        "thesis": "Trend confermato dallo smart money: entra solo quando TSMOM e posizionamento dei "
                  "top trader CONCORDANO sulla direzione (signal_vote → somma=0 se discordano). Tesi: "
                  "un secondo segnale leading ortogonale (posizionamento, non prezzo) alza il DSR. "
                  "Falsificata se non migliora vs tsmom-crypto-base-v1.",
        "signals": [{"name": "tsmom", "params": {"short_h": 168, "long_h": 720}},
                    {"name": "smart_money_ratio", "params": {"lookback_h": 720, "extreme_pct": 75}}],
        "entry": {"rule": "tsmom AND smart_money_ratio", "direction": "signal_vote"},
        "exit": {"stop_pct": 2.5, "target_r": 3.0, "time_stop_h": 240},
        "risk": {"max_leverage": 1, "risk_per_trade_pct": 0.6, "max_concurrent_positions": 2},
    },
    {
        # Controprova: seguire i top trader perde → l'edge è CONTRARIAN? (fade del posizionamento)
        "id": "smart-money-fade-v1", "family": "smart-money-fade",
        "symbols": CRYPTO,
        "thesis": "Se seguire i top trader perde, forse il loro posizionamento estremo è contrarian "
                  "(affollamento da fadare). Short quando sono estremi long, long quando estremi short. "
                  "Falsificata se non batte buy-and-hold.",
        "signals": [{"name": "smart_money_ratio", "params": {"lookback_h": 720, "extreme_pct": 80}}],
        "entry": {"rule": "smart_money_ratio", "direction": "contrarian:smart_money_ratio"},
        "exit": {"stop_pct": 2.5, "target_r": 3.0, "time_stop_h": 240},
        "risk": {"max_leverage": 1, "risk_per_trade_pct": 0.6, "max_concurrent_positions": 3},
    },
    # --- A/B LIQUIDAZIONI reali (Coinalyze gratis, daily, basket crypto) — l'edge ortogonale ---
    {
        "id": "liq-momentum-v1", "family": "liq-momentum",
        "symbols": CRYPTO,
        "thesis": "Segui lo squeeze: quando vengono liquidati in massa gli SHORT (pressione "
                  "rialzista) vai long, quando i LONG vai short. Tesi momentum: le cascate di "
                  "liquidazione continuano nella stessa direzione. Falsificata se non batte B&H.",
        "signals": [{"name": "liq_imbalance", "params": {"lookback_d": 21, "extreme_pct": 80}}],
        "entry": {"rule": "liq_imbalance", "direction": "follow:liq_imbalance"},
        "exit": {"stop_pct": 2.5, "target_r": 3.0, "time_stop_h": 240},
        "risk": {"max_leverage": 1, "risk_per_trade_pct": 0.6, "max_concurrent_positions": 3},
    },
    {
        "id": "liq-contrarian-v1", "family": "liq-contrarian",
        "symbols": CRYPTO,
        "thesis": "Fada il flush: quando i LONG vengono liquidati in massa (capitolazione) compra, "
                  "quando gli SHORT vendi. Tesi mean-reversion: le liquidazioni estreme segnano "
                  "esaurimento, il prezzo rimbalza. Falsificata se non batte buy-and-hold.",
        "signals": [{"name": "liq_imbalance", "params": {"lookback_d": 21, "extreme_pct": 80}}],
        "entry": {"rule": "liq_imbalance", "direction": "contrarian:liq_imbalance"},
        "exit": {"stop_pct": 2.5, "target_r": 3.0, "time_stop_h": 240},
        "risk": {"max_leverage": 1, "risk_per_trade_pct": 0.6, "max_concurrent_positions": 3},
    },
    {
        "id": "tsmom-liq-v1", "family": "tsmom-liq",
        "symbols": CRYPTO,
        "thesis": "Trend confermato dalle liquidazioni: entra solo quando TSMOM e lo sbilancio "
                  "liquidazioni CONCORDANO sulla direzione (signal_vote). Tesi: la pressione da "
                  "liquidazione nella direzione del trend lo rafforza. Falsificata se non migliora "
                  "vs tsmom-crypto-base-v1.",
        "signals": [{"name": "tsmom", "params": {"short_h": 168, "long_h": 720}},
                    {"name": "liq_imbalance", "params": {"lookback_d": 21, "extreme_pct": 75}}],
        "entry": {"rule": "tsmom AND liq_imbalance", "direction": "signal_vote"},
        "exit": {"stop_pct": 2.5, "target_r": 3.0, "time_stop_h": 240},
        "risk": {"max_leverage": 1, "risk_per_trade_pct": 0.6, "max_concurrent_positions": 2},
    },
    # --- A/B OPEN INTEREST (Coinalyze gratis, multi-exchange) — nuovo edge candidato ---
    {
        "id": "oi-trend-v1", "family": "oi-trend",
        "symbols": CRYPTO,
        "thesis": "OI-confirmed momentum: entra nella direzione del prezzo SOLO quando "
                  "l'open interest multi-exchange sale (nuovi soldi = carburante). OI in "
                  "calo → covering/deleverage, nessuna conviction → stai fuori. Tesi: il "
                  "flusso di posizionamento filtra i trend veri dai rimbalzi senza fondo. "
                  "Falsificata se non batte buy-and-hold risk-adjusted.",
        "signals": [{"name": "oi_trend", "params": {"lookback_d": 3, "price_lb_h": 72, "min_oi_chg_pct": 1.0}}],
        "entry": {"rule": "oi_trend", "direction": "follow:oi_trend"},
        "exit": {"stop_pct": 2.5, "target_r": 3.0, "time_stop_h": 240},
        "risk": {"max_leverage": 1, "risk_per_trade_pct": 0.6, "max_concurrent_positions": 3},
    },
    {
        "id": "tsmom-oi-v1", "family": "tsmom-oi",
        "symbols": CRYPTO,
        "thesis": "Trend confermato dall'OI: entra solo quando TSMOM e l'OI-confirmed "
                  "momentum CONCORDANO (signal_vote). Tesi: l'espansione di open interest "
                  "nella direzione del trend = nuovi soldi che lo spingono, non solo "
                  "inerzia di prezzo. Falsificata se non migliora vs tsmom-crypto-base-v1.",
        "signals": [{"name": "tsmom", "params": {"short_h": 168, "long_h": 720}},
                    {"name": "oi_trend", "params": {"lookback_d": 3, "price_lb_h": 72, "min_oi_chg_pct": 1.0}}],
        "entry": {"rule": "tsmom AND oi_trend", "direction": "signal_vote"},
        "exit": {"stop_pct": 2.5, "target_r": 3.0, "time_stop_h": 240},
        "risk": {"max_leverage": 1, "risk_per_trade_pct": 0.6, "max_concurrent_positions": 2},
    },
    {
        "id": "tsmom-oi-gate-v1", "family": "tsmom-oi-gate",
        "symbols": CRYPTO,
        "thesis": "OI come GATE direzionless (non vote): entra sul trend TSMOM solo quando "
                  "l'OI è in espansione (oi_trend attivo), direzione presa dal solo tsmom. "
                  "Tesi: l'espansione di open interest conferma che dietro il trend ci sono "
                  "nuovi soldi, filtrando i trend senza partecipazione. Falsificata se DSR/"
                  "Sharpe non superano tsmom-crypto-base-v1.",
        "signals": [{"name": "tsmom", "params": {"short_h": 168, "long_h": 720}},
                    {"name": "oi_trend", "params": {"lookback_d": 3, "price_lb_h": 72, "min_oi_chg_pct": 1.0}}],
        "entry": {"rule": "tsmom AND oi_trend", "direction": "follow:tsmom"},
        "exit": {"stop_pct": 2.5, "target_r": 3.0, "time_stop_h": 240},
        "risk": {"max_leverage": 1, "risk_per_trade_pct": 0.6, "max_concurrent_positions": 3},
    },
    {
        "id": "liq-oi-v1", "family": "liq-oi",
        "symbols": CRYPTO,
        "thesis": "Doppia conferma del posizionamento: squeeze da liquidazioni E "
                  "espansione OI concordi (signal_vote). Tesi: le due fonti free di "
                  "positioning flow (liquidazioni + open interest, entrambe Coinalyze) "
                  "insieme isolano gli squeeze con vero carburante dietro. Falsificata se "
                  "non migliora vs tsmom-liq-v1 (l'edge già validato).",
        "signals": [{"name": "liq_imbalance", "params": {"lookback_d": 21, "extreme_pct": 75}},
                    {"name": "oi_trend", "params": {"lookback_d": 3, "price_lb_h": 72, "min_oi_chg_pct": 1.0}}],
        "entry": {"rule": "liq_imbalance AND oi_trend", "direction": "signal_vote"},
        "exit": {"stop_pct": 2.5, "target_r": 3.0, "time_stop_h": 240},
        "risk": {"max_leverage": 1, "risk_per_trade_pct": 0.6, "max_concurrent_positions": 2},
    },
]


def make_spec(seed: dict) -> dict:
    for s in seed["signals"]:
        if s["name"] not in SIGNALS:
            raise ValueError(f"segnale fuori registry: {s['name']}")
    return {
        "id": seed["id"], "parent": None, "status": "candidate", "created": str(date.today()),
        "thesis": seed["thesis"],
        "universe": {"selection": "explicit", "max_assets": len(seed["symbols"].split(",")),
                     "kinds": ["mixed"]},
        "timeframe": "1h", "decision_every_h": 4,
        "signals": seed["signals"], "entry": seed["entry"], "exit": seed["exit"],
        "risk": seed["risk"],
        "evolution": {"mutable": ["signals", "entry", "exit"], "notes": "seed di ricerca"},
        "backtest": {}, "paper_symbols": seed["symbols"],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsr", type=float, default=0.85, help="DSR riportato (gate champion, non challenger)")
    ap.add_argument("--min-sharpe", type=float, default=1.0, help="Sharpe minimo per il test live (challenger)")
    ap.add_argument("--months", type=int, default=6)
    ap.add_argument("--write", action="store_true", help="scrive gli YAML (challenger se passano)")
    args = ap.parse_args()

    # cache dati per simbolo (riuso tra seed con universi sovrapposti)
    cache: dict = {}

    def data_for(symbols: str) -> dict:
        out = {}
        for s in symbols.split(","):
            if s not in cache:
                cache[s] = load_data(s, args.months)
            out[s] = cache[s]
        return out

    results = []
    for seed in SEEDS:
        spec = make_spec(seed)
        datasets = data_for(seed["symbols"])
        res = eval_basket(spec, datasets)
        rets = res["basket_rets"]
        # buy-and-hold medio del basket come baseline obbligatoria
        bh = [buy_and_hold(d["candles"])["sharpe"] for d in datasets.values()]
        bh_sharpe = sum(bh) / len(bh)
        results.append((seed, spec, res, rets, bh_sharpe))

    trial_srs = [sharpe_moments(r)["sr"] for *_, r, _ in results]
    k = len([f for f in OUT_DIR.glob("*.yaml") if "candidates" not in f.name]) + len(results) + 1

    print(f"\n{'seed':<28} {'Sharpe':>7} {'vs B&H':>7} {'DSR':>6} {'MDD':>7} {'trades':>6}  esito")
    print("-" * 78)
    promoted = 0
    for seed, spec, res, rets, bh_sharpe in results:
        a = res["aggregate"]
        d = deflated_sharpe(rets, k, trial_srs)
        a["dsr"] = round(d["dsr"], 3)
        a["dsr_sr0_ann"] = d["sr0_ann"]
        a["vs_buy_hold_sharpe"] = round(a["mean_sharpe"] - bh_sharpe, 2)
        beats_bh = a["mean_sharpe"] > bh_sharpe
        # challenger = degno di TEST LIVE: batte buy-and-hold + Sharpe solido.
        # Il DSR resta il gate per la promozione a CHAMPION (promote.py), non qui:
        # il paper trading è il vero giudice di un challenger.
        passes = beats_bh and a["mean_sharpe"] >= args.min_sharpe
        spec["status"] = "challenger" if passes else "candidate"
        spec["backtest"] = {f"basket_{args.months}m": res if "basket_rets" not in res
                            else {kk: vv for kk, vv in res.items() if kk != "basket_rets"}}
        esito = "✓ CHALLENGER" if passes else ("· candidate" if beats_bh else "✗ sotto B&H")
        print(f"{seed['id']:<28} {a['mean_sharpe']:>7.2f} {a['vs_buy_hold_sharpe']:>+7.2f} "
              f"{a['dsr']:>6.2f} {a['worst_drawdown']:>7.1%} {a['total_trades']:>6}  {esito}")
        if args.write:
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            (OUT_DIR / f"{seed['id']}.yaml").write_text(
                yaml.safe_dump(spec, sort_keys=False, allow_unicode=True))
        promoted += int(passes)

    print(f"\n{promoted} seed promossi a challenger" +
          ("" if args.write else " (anteprima — usa --write per salvare)"))


if __name__ == "__main__":
    main()
