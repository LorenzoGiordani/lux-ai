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
"$UV" run scripts/agents_paper.py
"$UV" run scripts/agents_paper.py --account agents-rr2-v1 --source agents-v1 --target-r 2.0 || true   # A/B RR2, stesse decisioni
stage "portfolio book"
"$UV" run scripts/portfolio_paper.py strategies/generated/xsmom-port-v1.yaml || true   # cross-sectional momentum

if command -v claude >/dev/null 2>&1; then
    stage "reviewer"
    "$UV" run scripts/review.py || true          # post-mortem trade chiusi
    # decisione pipeline ogni run (4h) — solo con CLI: usa il piano Pro
    stage "pipeline decide"
    "$UV" run scripts/decide.py BTC,ETH,SOL,SUI,ZEC || true
    "$UV" run scripts/agents_paper.py || true    # esegui subito l'eventuale decisione
    "$UV" run scripts/agents_paper.py --account agents-rr2-v1 --source agents-v1 --target-r 2.0 || true   # variante RR2
    # Claude Strategy: gate sistematico (confluenza) + layer LLM; chiama l'LLM solo a gate aperto
    stage "claude strategy"
    "$UV" run scripts/claude_strategy.py BTC,ETH,SOL,XRP,SUI,NEAR,WLD,ZEC,CRV || true
    "$UV" run scripts/agents_paper.py --account claude-strategy-v1 || true
    # desk geopolitico: gated su burst GDELT, chiama l'LLM solo se il gate è aperto
    stage "geopolitics desk"
    "$UV" run scripts/geopolitics_paper.py || true
fi

stage "brain"
"$UV" run scripts/brain_gen.py || true        # rigenera wiki markdown dai dati paper/

stage "dashboard"
"$UV" run scripts/dashboard.py

# auto-pubblica journal, brain e dashboard su GitHub (repo privata)
git add paper/ brain/ dashboard/index.html 2>/dev/null
if ! git diff --cached --quiet; then
    git commit -q -m "chore: paper run $(date -u '+%Y-%m-%d %H:%M') UTC [auto]"
    git push -q origin main || true
fi
