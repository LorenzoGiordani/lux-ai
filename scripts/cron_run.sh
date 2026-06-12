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

stage "challenger funding-squeeze"
"$UV" run scripts/paper_trade.py strategies/generated/funding-squeeze-breakout-g2-g1-g2.yaml BTC,ETH,SOL,XRP,SUI,NEAR,WLD,ZEC,CRV
stage "challenger tsmom"
"$UV" run scripts/paper_trade.py strategies/tsmom-v1.yaml BTC,ETH,xyz_GOLD,xyz_CL,xyz_BRENTOIL,xyz_SILVER,xyz_SP500,xyz_MU
stage "executor agenti"
"$UV" run scripts/agents_paper.py

if command -v claude >/dev/null 2>&1; then
    stage "reviewer"
    "$UV" run scripts/review.py || true          # post-mortem trade chiusi
    # decisione pipeline ogni run (4h) — solo con CLI: usa il piano Pro
    stage "pipeline decide"
    "$UV" run scripts/decide.py BTC,ETH,SOL,SUI,ZEC || true
    "$UV" run scripts/agents_paper.py || true    # esegui subito l'eventuale decisione
fi

stage "dashboard"
"$UV" run scripts/dashboard.py

# auto-pubblica journal e dashboard su GitHub (repo privata)
git add paper/ dashboard/index.html 2>/dev/null
if ! git diff --cached --quiet; then
    git commit -q -m "chore: paper run $(date -u '+%Y-%m-%d %H:%M') UTC [auto]"
    git push -q origin main || true
fi
