"""Statistiche anti-overfitting: PSR e Deflated Sharpe (Bailey & López de Prado).

Il loop evolutivo testa K candidati: il migliore ha uno Sharpe gonfiato per
selezione (è il massimo di K estrazioni, in parte rumore). Il DSR risponde a:
"probabilità che lo Sharpe osservato sia skill vero e non il massimo del
rumore su K prove?". Gate di promozione: DSR ≥ 0.95.

Riferimenti: Bailey & López de Prado, "The Deflated Sharpe Ratio" (2014).
Solo stdlib (statistics.NormalDist): niente scipy.
"""

import math
from statistics import NormalDist

import pandas as pd

_N = NormalDist()
_EULER = 0.5772156649015329


def sharpe_moments(rets: pd.Series) -> dict:
    """Momenti per-periodo dei ritorni (NON annualizzati: il PSR li vuole così)."""
    r = rets.dropna()
    n = len(r)
    if n < 30 or r.std(ddof=1) == 0:
        return {"sr": 0.0, "skew": 0.0, "kurt": 3.0, "n": n}
    return {"sr": float(r.mean() / r.std(ddof=1)),
            "skew": float(r.skew()),
            "kurt": float(r.kurt()) + 3.0,  # pandas dà l'eccesso → raw
            "n": n}


def psr(rets: pd.Series, sr0: float = 0.0) -> float:
    """Probabilistic Sharpe Ratio: P(SR vero > sr0), con sr0 per-periodo.
    Corregge per campione corto, skew e code grasse."""
    m = sharpe_moments(rets)
    if m["n"] < 30:
        return 0.0
    denom = 1 - m["skew"] * m["sr"] + (m["kurt"] - 1) / 4 * m["sr"] ** 2
    if denom <= 0:
        return 0.0
    z = (m["sr"] - sr0) * math.sqrt(m["n"] - 1) / math.sqrt(denom)
    return float(_N.cdf(z))


def expected_max_sr(n_trials: int, var_trials: float) -> float:
    """Sharpe massimo atteso (per-periodo) di n_trials strategie SENZA skill."""
    if n_trials <= 1 or var_trials <= 0:
        return 0.0
    k = max(n_trials, 2)
    return math.sqrt(var_trials) * ((1 - _EULER) * _N.inv_cdf(1 - 1 / k)
                                    + _EULER * _N.inv_cdf(1 - 1 / (k * math.e)))


def deflated_sharpe(rets: pd.Series, n_trials: int,
                    trial_srs: list[float] | None = None,
                    periods_per_year: int = 24 * 365) -> dict:
    """DSR = PSR contro lo Sharpe massimo atteso dal solo rumore su n_trials.

    rets: ritorni per-periodo della strategia candidata (es. orari, sul basket)
    trial_srs: Sharpe PER-PERIODO di tutti i candidati provati (stima la
               varianza cross-trial); se assente, usa la varianza dello
               stimatore dello SR del candidato stesso (conservativo)."""
    m = sharpe_moments(rets)
    if trial_srs and len(trial_srs) > 1:
        s = pd.Series(trial_srs)
        var_trials = float(s.var(ddof=1))
    else:
        var_trials = (1 - m["skew"] * m["sr"] + (m["kurt"] - 1) / 4 * m["sr"] ** 2) \
            / max(m["n"] - 1, 1)
    sr0 = expected_max_sr(n_trials, var_trials)
    ann = math.sqrt(periods_per_year)
    return {"dsr": psr(rets, sr0),
            "sr_ann": round(m["sr"] * ann, 3),
            "sr0_ann": round(sr0 * ann, 3),  # asticella: max atteso dal rumore
            "n_trials": n_trials}
