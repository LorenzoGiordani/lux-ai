"""Robustness validation dei 2 edge portfolio forti (xsmom, highvol).

Tre test ONESIT prima di dichiarare gli edge "reali" (e prima di M5 / soldi veri).
Rispondono al dubbio: i parametri (lookback/rebalance) sono stati scelti sul periodo
intero -> selection bias. Il DSR sconta il multiple-testing ma e' calcolato in-sample.

  [1] PARAMETER STABILITY  — sweep lookback/rebalance attorno al valore scelto.
       Un picco ISOLATO (cliff perturbando) = overfit. Un ALTOPIANO largo
       (Sharpe > 1.5 sulla maggior parte dei vicini) = edge robusto.
  [2] BLOCK BOOTSTRAP CI    — resampling a blocchi del Sharpe (preserva
       l'autocorrelazione del ribilanciamento). Risponde: Sharpe 2.1 e'
       statisticamente > 1.0? Qual e' il bound inferiore al 95%?
  [3] TRUE OOS SPLIT        — calibra i parametri sui primi 8m, FREEZE, test sui
       4m finali mai visti. Risponde al selection bias in modo diretto.

Dati: 8640h (12m) × 9 crypto. Uso: uv run scripts/robustness_portfolio.py
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backtest.portfolio import PortfolioBacktest
from backtest.stats import deflated_sharpe

CRYPTO = "BTC,ETH,SOL,XRP,SUI,NEAR,WLD,ZEC,CRV"
PPY = 24 * 365
HL_TAKER_FEE = 0.00045
DEFAULT_SLIPPAGE = 0.0005
COST = HL_TAKER_FEE + DEFAULT_SLIPPAGE


def grid_panel(symbols, months, col="close", kind="candles"):
    """Panel orario allineato alla griglia BTC (24/7), ffill per gap session."""
    btc = pd.read_parquet(ROOT / "data/candles/BTC.parquet").tail(months * 30 * 24)
    grid = pd.to_datetime(btc.ts, utc=True)
    cols = {}
    for s in symbols:
        p = ROOT / f"data/{kind}/{s}.parquet"
        if p.exists():
            c = pd.read_parquet(p).copy()
            c["ts"] = pd.to_datetime(c.ts, utc=True)
            if col in c.columns:
                cols[s] = (c.drop_duplicates("ts").set_index("ts")[col]
                           .reindex(grid, method="ffill"))
    return pd.DataFrame(cols).sort_index()


def terzile_weights(signal_row, gross=1.0):
    """Long top-terzile, short bottom-terzile, dollar-neutral equal-weight per gamba."""
    s = signal_row.dropna()
    w = pd.Series(0.0, index=signal_row.index)
    if len(s) < 6:
        return w
    n = max(2, len(s) // 3)
    w[s.nlargest(n).index] = 0.5 / n
    w[s.nsmallest(n).index] = -0.5 / n
    g = w.abs().sum()
    return w / g * gross if g > 0 else w


def run_book(signal_panel, bt, weight_fn, rebalance_h):
    """Applica weight_fn al signal_panel, ribilancia ogni rebalance_h, anti-lookahead
    (pesi decisi a t, applicati dal bar t+1). Ritorna (equity, port_ret, n_rebalances)."""
    idx = bt.close.index
    n = len(idx)
    sig = signal_panel.reindex(columns=bt.close.columns)
    W = pd.DataFrame(0.0, index=idx, columns=bt.close.columns)
    turnover = pd.Series(0.0, index=idx)
    last_w = pd.Series(0.0, index=bt.close.columns)
    first = sig.dropna(how="all").index
    start = sig.index.get_loc(first[0]) + 1 if len(first) else n
    for i in range(start, n, rebalance_h):
        w = weight_fn(sig.iloc[i - 1]).reindex(bt.close.columns).fillna(0.0)
        turnover.iloc[i] = (w - last_w).abs().sum()
        last_w = w
        W.iloc[i:min(i + rebalance_h, n)] = w.to_numpy()
    port_ret = (W.shift(1) * bt.ret).sum(axis=1) - turnover * bt.cost
    eq = (1.0 + port_ret).cumprod()
    return eq, port_ret, int((turnover > 0).sum())


def stats(eq, ret):
    sh = ret.mean() / ret.std() * np.sqrt(PPY) if ret.std() else 0.0
    dd = float((eq / eq.cummax() - 1).min())
    return float(eq.iloc[-1] - 1), float(sh), dd


# ── costruttori segnale (factory per parametrizzare lookback) ──────────────
def xsmom_signal(px, lookback_h):
    return px.pct_change(lookback_h)


def highvol_signal(px, vol_lookback_h):
    return px.pct_change().rolling(vol_lookback_h, min_periods=vol_lookback_h // 2).std()


SIGNALS = {
    "xsmom":   dict(builder=xsmom_signal,   chosen_lb=168, chosen_reb=168,
                    lb_grid=[48, 72, 96, 120, 168, 240, 336],
                    reb_grid=[48, 72, 168, 336]),
    "highvol": dict(builder=highvol_signal, chosen_lb=72,  chosen_reb=168,
                    lb_grid=[24, 48, 72, 96, 168],
                    reb_grid=[48, 72, 168, 336]),
}


def _dsr(ret, n_trials):
    return deflated_sharpe(ret, n_trials, periods_per_year=PPY)["dsr"]


# ════════════════════════════════════════════════════════════════════════════
# TEST 1 — PARAMETER STABILITY
# ════════════════════════════════════════════════════════════════════════════
def test_stability(name, px, bt_full, cfg):
    b = cfg["builder"]
    print(f"\n[1] PARAMETER STABILITY — {name}  (scelto: lb={cfg['chosen_lb']} reb={cfg['chosen_reb']})")
    # (a) sweep lookback a rebalance fissato
    print(f"  {'lookback':>9} {'ret':>8} {'sharpe':>7} {'maxDD':>8}  curva")
    sharpe_by_lb = {}
    for lb in cfg["lb_grid"]:
        sig = b(px, lb)
        eq, ret, _ = run_book(sig, bt_full, terzile_weights, cfg["chosen_reb"])
        r, sh, dd = stats(eq, ret)
        sharpe_by_lb[lb] = sh
        mark = "  ← scelto" if lb == cfg["chosen_lb"] else ""
        bar = "█" * int(max(0, sh))
        print(f"  {lb:>9} {r:>+8.1%} {sh:>7.2f} {dd:>+8.1%}  {bar}{mark}")
    # (b) sweep rebalance a lookback fissato
    print(f"  {'rebal_h':>9} {'ret':>8} {'sharpe':>7} {'maxDD':>8}")
    for rb in cfg["reb_grid"]:
        sig = b(px, cfg["chosen_lb"])
        eq, ret, _ = run_book(sig, bt_full, terzile_weights, rb)
        r, sh, dd = stats(eq, ret)
        mark = "  ← scelto" if rb == cfg["chosen_reb"] else ""
        print(f"  {rb:>9} {r:>+8.1%} {sh:>7.2f} {dd:>+8.1%}{mark}")
    # score: frazione di vicini (lb_grid escl. scelto) con Sharpe > 1.5
    neigh = [sh for lb, sh in sharpe_by_lb.items() if lb != cfg["chosen_lb"]]
    robust_frac = np.mean([s > 1.5 for s in neigh])
    best_lb = max(sharpe_by_lb, key=sharpe_by_lb.get)
    verdict = ("ROBUSTO (altopiano)" if robust_frac >= 0.5
               else "FRAGILE (picco isolato)")
    print(f"  → {robust_frac:.0%} dei lookback vicini tengono Sharpe>1.5 | "
          f"picco a lb={best_lb} ({sharpe_by_lb[best_lb]:.2f}) | {verdict}")
    return robust_frac


# ════════════════════════════════════════════════════════════════════════════
# TEST 2 — BLOCK BOOTSTRAP CI sul Sharpe
# ════════════════════════════════════════════════════════════════════════════
def block_bootstrap_sharpe(ret, block_h=168, B=2000, seed=42):
    """Circular block bootstrap del Sharpe annualizzato. Blocchi di `block_h` ore
    preservano l'autocorrelazione del ribilanciamento (non possiamo resamplare
    i singoli return come IID: il book ha memoria settimanale)."""
    rng = np.random.default_rng(seed)
    r = ret.to_numpy()
    n = len(r)
    n_blocks = int(np.ceil(n / block_h))
    # indici di partenza dei blocchi (circular)
    starts = rng.integers(0, n, size=(B, n_blocks))
    sharpes = np.empty(B)
    ann = np.sqrt(PPY)
    for b in range(B):
        idx = (starts[b][:, None] + np.arange(block_h)[None, :]).ravel() % n
        samp = r[idx[:n]]
        sd = samp.std()
        sharpes[b] = samp.mean() / sd * ann if sd > 0 else 0.0
    return sharpes


def test_bootstrap(name, px, bt_full, cfg):
    sig = cfg["builder"](px, cfg["chosen_lb"])
    _, ret, _ = run_book(sig, bt_full, terzile_weights, cfg["chosen_reb"])
    sharpes = block_bootstrap_sharpe(ret, block_h=cfg["chosen_reb"], B=2000)
    pt_ret, pt_sh, pt_dd = stats((1 + ret).cumprod(), ret)
    lo, hi = np.percentile(sharpes, [2.5, 97.5])
    p_pos = np.mean(sharpes > 0)
    p_gt1 = np.mean(sharpes > 1.0)
    p_gt15 = np.mean(sharpes > 1.5)
    print(f"\n[2] BLOCK BOOTSTRAP CI — {name}  (B=2000, block={cfg['chosen_reb']}h)")
    print(f"  Sharpe puntuale: {pt_sh:.2f} | maxDD {pt_dd:+.1%} | ret {pt_ret:+.1%}")
    print(f"  Sharpe 95% CI:   [{lo:.2f}, {hi:.2f}]")
    print(f"  P(Sharpe > 0):   {p_pos:.1%}   P(> 1.0): {p_gt1:.1%}   P(> 1.5): {p_gt15:.1%}")
    verdict = ("EDGE SOLIDO" if lo > 1.0 else
               "EDGE DEBOLE" if lo > 0 else "NON DISTINGUIBILE DA 0")
    print(f"  → bound inferiore 95% = {lo:.2f} | {verdict}")
    return lo


# ════════════════════════════════════════════════════════════════════════════
# TEST 3 — TRUE OUT-OF-SAMPLE (calibra su 8m, testa sui 4m finali)
# ════════════════════════════════════════════════════════════════════════════
def test_oos(name, px, train_end, cfg):
    b = cfg["builder"]
    px_tr, px_te = px.loc[:train_end], px.loc[train_end:]
    bt_tr, bt_te = PortfolioBacktest(px_tr), PortfolioBacktest(px_te)
    print(f"\n[3] TRUE OOS SPLIT — {name}  (train fino al {train_end:%Y-%m-%d}, "
          f"test {len(px_te)}h)")
    # calibra su train: meglio Sharpe (ma penalizza config DD enorme? Sharpe e' risk-adj)
    grid = [(lb, rb) for lb in cfg["lb_grid"] for rb in cfg["reb_grid"]]
    rows = []
    for lb, rb in grid:
        eq, ret, _ = run_book(b(px_tr, lb), bt_tr, terzile_weights, rb)
        r, sh, dd = stats(eq, ret)
        rows.append((lb, rb, sh, dd, r))
    rows.sort(key=lambda x: x[2], reverse=True)
    best = rows[0]
    lb_b, rb_b = best[0], best[1]
    print(f"  best su TRAIN: lb={lb_b} reb={rb_b} → Sharpe {best[2]:.2f} "
          f"maxDD {best[3]:+.1%} ret {best[4]:+.1%}")
    print(f"  {'lb':>5} {'reb':>5} {'sharpe_tr':>9} | {'sharpe_te':>9} {'maxDD_te':>9} {'ret_te':>8}")
    # top-5 config su train, vedi come generalizzano su test
    for lb, rb, sh_tr, dd_tr, r_tr in rows[:5]:
        eq, ret, _ = run_book(b(px_te, lb), bt_te, terzile_weights, rb)
        r_te, sh_te, dd_te = stats(eq, ret)
        mark = "  ← FREEZE" if (lb, rb) == (lb_b, rb_b) else ""
        chosen = "  ← scelto-origine" if (lb, rb) == (cfg["chosen_lb"], cfg["chosen_reb"]) else ""
        print(f"  {lb:>5} {rb:>5} {sh_tr:>9.2f} | {sh_te:>9.2f} {dd_te:>+9.1%} {r_te:>+8.1%}{mark}{chosen}")
    # OOS del config FREEZE (scelto solo su train)
    eq, ret, _ = run_book(b(px_te, lb_b), bt_te, terzile_weights, rb_b)
    r_te, sh_te, dd_te = stats(eq, ret)
    # confronto: config "scelto-origine" (lb scelto sul full) sul test
    eq2, ret2, _ = run_book(b(px_te, cfg["chosen_lb"]), bt_te, terzile_weights, cfg["chosen_reb"])
    _, sh_orig, dd_orig = stats(eq2, ret2)
    print(f"  OOS Sharpe (FREEZE train-best): {sh_te:.2f} | "
          f"OOS Sharpe (config origine): {sh_orig:.2f}")
    return sh_te, sh_orig


# ════════════════════════════════════════════════════════════════════════════
# TEST 4 — COMBO xsmom+highvol (la candidata champion: Sharpe 2.38 maxDD -16%)
# ════════════════════════════════════════════════════════════════════════════
def test_combo(px, bt_full, train_end, xcfg, hcfg):
    """Il valore di prodotto e' il DD basso della combo. Test: (a) sweep blend ratio,
    (b) bootstrap Sharpe E maxDD del 70/30, (c) OOS del blend coi config origine."""
    # full-period returns delle due gambe coi config scelti
    ret_xs = run_book(xcfg["builder"](px, xcfg["chosen_lb"]), bt_full,
                      terzile_weights, xcfg["chosen_reb"])[1]
    ret_hv = run_book(hcfg["builder"](px, hcfg["chosen_lb"]), bt_full,
                      terzile_weights, hcfg["chosen_reb"])[1]
    print("\n" + "─" * 78)
    print("  COMBO xsmom+highvol  (candidata champion)")
    print("─" * 78)

    # (a) sweep blend ratio (w = peso xsmom; highvol = 1-w)
    print("[4a] BLEND RATIO SWEEP  (w = peso xsmom)")
    print(f"  {'w_xs':>6} {'ret':>8} {'sharpe':>7} {'maxDD':>8}  commento")
    best_dd, best_dd_w = -2.0, None
    for w in [0.0, 0.25, 0.5, 0.7, 0.75, 1.0]:
        blend = w * ret_xs + (1 - w) * ret_hv
        eq = (1 + blend).cumprod()
        r, sh, dd = stats(eq, blend)
        note = "← 70/30 scelto" if abs(w - 0.7) < 1e-6 else ""
        if dd > best_dd:
            best_dd, best_dd_w = dd, w
        print(f"  {w:>6.2f} {r:>+8.1%} {sh:>7.2f} {dd:>+8.1%}  {note}")
    print(f"  → minor DD a w_xs={best_dd_w:.2f} (maxDD {best_dd:+.1%}) | "
          f"70/30 e' {'ottimo' if abs(best_dd_w-0.7)<0.05 else 'vicino ma non il min-DD'}")

    # (b) bootstrap Sharpe E maxDD del 70/30
    blend = 0.7 * ret_xs + 0.3 * ret_hv
    sharpes = block_bootstrap_sharpe(blend, block_h=168, B=2000)
    # bootstrap sul maxDD: serve ricostruire l'equity di ogni campione
    rng = np.random.default_rng(123)
    r = blend.to_numpy()
    n = len(r)
    bh = 168
    nb = int(np.ceil(n / bh))
    starts = rng.integers(0, n, size=(2000, nb))
    maxdds = np.empty(2000)
    for b in range(2000):
        idx = (starts[b][:, None] + np.arange(bh)[None, :]).ravel()[:n] % n
        eq = np.cumprod(1 + r[idx])
        maxdds[b] = (eq / np.maximum.accumulate(eq) - 1).min()
    lo_s, hi_s = np.percentile(sharpes, [2.5, 97.5])
    lo_dd = np.percentile(maxdds, 5)   # 5° percentile = coda avversa del DD
    r, sh, dd = stats((1 + blend).cumprod(), blend)
    print(f"\n[4b] BOOTSTRAP combo 70/30  (B=2000)")
    print(f"  Sharpe {sh:.2f}  95% CI [{lo_s:.2f}, {hi_s:.2f}]  P(>1.0)={np.mean(sharpes>1.0):.0%}")
    print(f"  maxDD  {dd:+.1%}  coda 5% (avversa) {lo_dd:+.1%}  P(DD peggiore di -25%)={np.mean(maxdds<-0.25):.0%}")

    # (c) OOS del blend (config origine di entrambe le gambe, mai ricalibrati)
    px_te = px.loc[train_end:]
    bt_te = PortfolioBacktest(px_te)
    ret_xs_te = run_book(xcfg["builder"](px_te, xcfg["chosen_lb"]), bt_te,
                         terzile_weights, xcfg["chosen_reb"])[1]
    ret_hv_te = run_book(hcfg["builder"](px_te, hcfg["chosen_lb"]), bt_te,
                         terzile_weights, hcfg["chosen_reb"])[1]
    blend_te = 0.7 * ret_xs_te + 0.3 * ret_hv_te
    r_te, sh_te, dd_te = stats((1 + blend_te).cumprod(), blend_te)
    print(f"\n[4c] OOS combo 70/30  (config origine, 4m mai visti)")
    print(f"  ret {r_te:+.1%}  Sharpe {sh_te:.2f}  maxDD {dd_te:+.1%}")
    return {"full_sh": sh, "ci_lo": lo_s, "oos_sh": sh_te, "oos_dd": dd_te,
            "dd_tail5": lo_dd}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=CRYPTO)
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--train_frac", type=float, default=0.67,
                    help="frazione iniziale dedicata al train (resto = test OOS)")
    a = ap.parse_args()
    syms = a.symbols.split(",")

    px = grid_panel(syms, a.months)
    bt_full = PortfolioBacktest(px)
    split_idx = int(len(px) * a.train_frac)
    train_end = px.index[split_idx]
    print(f"basket {list(px.columns)} | {len(px)}h "
          f"({px.index.min():%Y-%m-%d} → {px.index.max():%Y-%m-%d})")
    print(f"split OOS: train {split_idx}h → test {len(px)-split_idx}h "
          f"(cutoff {train_end:%Y-%m-%d})")
    print("=" * 78)

    summary = {}
    for name, cfg in SIGNALS.items():
        print("\n" + "─" * 78)
        print(f"  {name.upper()}   (scelto lb={cfg['chosen_lb']} reb={cfg['chosen_reb']})")
        print("─" * 78)
        # baseline full-period (riferimento)
        eq, ret, nreb = run_book(cfg["builder"](px, cfg["chosen_lb"]), bt_full,
                                 terzile_weights, cfg["chosen_reb"])
        r, sh, dd = stats(eq, ret)
        dsr = _dsr(ret, n_trials=8)
        print(f"  full-period (riferimento): ret {r:+.1%} Sharpe {sh:.2f} "
              f"maxDD {dd:+.1%} DSR {dsr:.2f} ({nreb} rebal)")
        rf = test_stability(name, px, bt_full, cfg)
        lo = test_bootstrap(name, px, bt_full, cfg)
        sh_te, sh_orig = test_oos(name, px, train_end, cfg)
        summary[name] = dict(full_sh=sh, ci_lo=lo, oos_freeze=sh_te, oos_origin=sh_orig,
                             robust_frac=rf)

    # combo (candidata champion)
    summary["combo70/30"] = test_combo(px, bt_full, train_end,
                                      SIGNALS["xsmom"], SIGNALS["highvol"])

    # ── verdetto finale ───────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("VERDETTO ROBUSTEZZA")
    print("=" * 78)
    print(f"{'strategia':<12} {'full':>6} {'CI95lo':>7} {'OOS':>7} {'OOS_DD':>8} {'stab%':>6}  giustizio")
    for n, s in summary.items():
        if n == "combo70/30":
            ok = (s["ci_lo"] > 1.0 and s["oos_sh"] > 1.0 and s["oos_dd"] > -0.25)
            verdict = "✓ EDGE ROBUSTO" if ok else "△ NON ANCORA ROBUSTO"
            print(f"{n:<12} {s['full_sh']:>6.2f} {s['ci_lo']:>7.2f} {s['oos_sh']:>7.2f} "
                  f"{s['oos_dd']:>+8.1%} {'':>6}  {verdict}")
        else:
            ok = (s["ci_lo"] > 1.0 and s["oos_freeze"] > 1.0 and s["robust_frac"] >= 0.5)
            verdict = "✓ EDGE ROBUSTO" if ok else "△ NON ANCORA ROBUSTO"
            print(f"{n:<12} {s['full_sh']:>6.2f} {s['ci_lo']:>7.2f} {s['oos_freeze']:>7.2f} "
                  f"{'':>8} {s['robust_frac']:>5.0%}  {verdict}")
    print("\nSingola gamba: CI95 inf > 1.0 AND OOS-freeze Sharpe > 1.0 AND "
          "≥50% lookback vicini tengono Sharpe>1.5.")
    print("Combo: CI95 inf > 1.0 AND OOS Sharpe > 1.0 AND OOS maxDD > -25%.")
    print("⚠ Onesta: 12m (~50 ribilanci) e' troppo poco per inchiodare uno Sharpe. "
          "I CI sono larghi (±2). Il gate verso M5 resta il TRACK RECORD nel tempo.")


if __name__ == "__main__":
    main()
