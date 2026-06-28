#!/bin/sh
# Run periodico della piattaforma (cron ogni 4h).
# Ordine: challenger segnale-based → executor decisioni agenti → reviewer
# (solo se CLI claude installata) → dashboard.
set -u
ROOT="/Users/lorenzogiordani/PROGETTI/defi-ai-vault"
UV="/opt/homebrew/bin/uv"
cd "$ROOT" || exit 1

# log persistente nel progetto, auto-trim a 10k righe (Mac con poco disco)
LOG="$ROOT/logs/cron.log"
mkdir -p "$ROOT/logs"
[ -f "$LOG" ] && [ "$(wc -l < "$LOG")" -gt 10000 ] && tail -n 5000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
exec >> "$LOG" 2>&1
echo "=== cron run $(date -u '+%Y-%m-%d %H:%M') UTC ==="

stage() { echo "--- $1 [$(date -u '+%H:%M:%S')]"; }

stage "paper trading strategie attive"
"$UV" run scripts/paper_all.py
stage "executor agenti"
"$UV" run scripts/agents_paper.py || true
"$UV" run scripts/agents_paper.py --account agents-rr2-v1 --source agents-v1 --target-r 2.0 || true   # A/B RR2, stesse decisioni
# strategie engine:portfolio (xsmom-port, xsmom-multihorizon, highvol-port, combo, voltarget):
# runner dedicato via active_specs — niente più glob pattern (zombie multihorizon fixato).
"$UV" run scripts/portfolio_all.py

if command -v claude >/dev/null 2>&1; then
    stage "reviewer"
    "$UV" run scripts/review.py || true          # post-mortem trade chiusi
    # decisione pipeline ogni run (4h) — solo con CLI: usa il piano Pro
    stage "pipeline decide"
    "$UV" run scripts/decide.py BTC,ETH,SOL,SUI,ZEC || true
    "$UV" run scripts/agents_paper.py || true    # esegui subito l'eventuale decisione
    "$UV" run scripts/agents_paper.py --account agents-rr2-v1 --source agents-v1 --target-r 2.0 || true   # variante RR2
    # Claude Strategy RETIRATA 25/06 (layer LLM non aggiungeva valore): rimosso dal cron.
    # desk geopolitico: gated su burst GDELT, chiama l'LLM solo se il gate è aperto
    stage "geopolitics desk"
    "$UV" run scripts/geopolitics_paper.py || true
fi

stage "brain"
"$UV" run scripts/brain_gen.py || true        # rigenera wiki markdown dai dati paper/

stage "backtest"
"$UV" run scripts/backtest_report.py    # basket multi-asset (sezione dashboard)

stage "dashboard"
"$UV" run scripts/dashboard.py

# auto-pubblica journal, brain e dashboard su GitHub (repo privata)
git add paper/ brain/ dashboard/index.html 2>/dev/null
if ! git diff --cached --quiet; then
    git commit -q -m "chore: paper run $(date -u '+%Y-%m-%d %H:%M') UTC [auto]"
    git push -q origin main || true
fi
