#!/bin/sh
# Run periodico della piattaforma (cron ogni 4h).
# Ordine: challenger segnale-based → executor decisioni agenti → reviewer
# (solo se CLI claude installata) → dashboard.
set -u
ROOT="/Users/lorenzogiordani/Desktop/PROGETTI/defi-ai-vault"
UV="/opt/homebrew/bin/uv"
cd "$ROOT" || exit 1

"$UV" run scripts/paper_trade.py strategies/generated/funding-squeeze-breakout-g2-g1-g2.yaml BTC,ETH,SOL,XRP,SUI,NEAR,WLD,ZEC,CRV
"$UV" run scripts/agents_paper.py

if command -v claude >/dev/null 2>&1; then
    "$UV" run scripts/review.py || true          # post-mortem trade chiusi
    # decisione pipeline ogni run (4h) — solo con CLI: usa il piano Pro
    "$UV" run scripts/decide.py BTC,ETH,SOL,SUI,ZEC || true
    "$UV" run scripts/agents_paper.py || true    # esegui subito l'eventuale decisione
fi

"$UV" run scripts/dashboard.py
