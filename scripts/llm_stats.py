"""Osservabilità del layer LLM — riassume il tracing (paper/llm_calls.jsonl).

Uso:
  uv run scripts/llm_stats.py              # tutto
  uv run scripts/llm_stats.py --since 24h  # ultime 24h

Mostra: chiamate totali, token, latenza media, cache hit, e un breakdown per
ruolo (chi costa cosa, chi veto di più) e per effort. È il "cosa mi dice il
tracing" quando vuoi capire dove tagliare effort o ottimizzare un prompt.
"""
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "paper/llm_calls.jsonl"


def _parse_since(arg: str):
    if not arg:
        return None
    try:
        h = float(arg.rstrip("h"))
        return datetime.now(timezone.utc) - timedelta(hours=h)
    except ValueError:
        return None


def main() -> None:
    since = _parse_since(sys.argv[sys.argv.index("--since") + 1]) if "--since" in sys.argv else None
    if not LOG.exists():
        print("(nessun tracing ancora — paper/llm_calls.jsonl vuoto o assente)")
        return
    rows = [json.loads(l) for l in LOG.read_text().splitlines() if l.strip()]
    if since:
        rows = [r for r in rows if datetime.fromisoformat(r["ts"]) >= since]
    if not rows:
        print("(nessuna chiamata nel range)")
        return

    by_role = defaultdict(lambda: {"n": 0, "lat": 0.0, "tok_in": 0, "tok_out": 0, "fail": 0})
    by_effort = defaultdict(int)
    cached = 0
    for r in rows:
        u = r.get("usage", {}) or {}
        d = by_role[r.get("role") or "?"]
        d["n"] += 1
        d["lat"] += float(r.get("latency_s", 0) or 0)
        d["tok_in"] += int(u.get("in") or 0)
        d["tok_out"] += int(u.get("out") or 0)
        if not r.get("ok"):
            d["fail"] += 1
        if r.get("cached"):
            cached += 1
        by_effort[r.get("effort") or "?"] += 1

    tot_tok = sum(d["tok_in"] + d["tok_out"] for d in by_role.values())
    tot_lat = sum(d["lat"] for d in by_role.values())
    print(f"=== Layer LLM ({len(rows)} chiamate" + (f" da {since:%Y-%m-%d %H:%M} UTC" if since else "") + ") ===")
    print(f"token totali: {tot_tok:,} (in {sum(d['tok_in'] for d in by_role.values()):,} / "
          f"out {sum(d['tok_out'] for d in by_role.values()):,}) · cache hit: {cached}")
    print(f"latenza totale: {tot_lat:.0f}s · effort mix: "
          + ", ".join(f"{k}={v}" for k, v in sorted(by_effort.items(), key=lambda kv: -kv[1])))
    print(f"\n{'ruolo':<16}{'n':>5}{'lat/s':>8}{'tok_in':>10}{'tok_out':>10}{'fail':>5}")
    print("-" * 54)
    for role, d in sorted(by_role.items(), key=lambda kv: -(kv[1]["tok_in"] + kv[1]["tok_out"])):
        print(f"{role:<16}{d['n']:>5}{d['lat']/d['n']:>8.1f}{d['tok_in']:>10,}"
              f"{d['tok_out']:>10,}{d['fail']:>5}")
    # insight: il ruolo più costoso e quello più lento
    cost = max(by_role.items(), key=lambda kv: kv[1]["tok_in"] + kv[1]["tok_out"])
    slow = max(by_role.items(), key=lambda kv: kv[1]["lat"] / kv[1]["n"])
    print(f"\npiù costoso: {cost[0]} ({cost[1]['tok_in']+cost[1]['tok_out']:,} tok) · "
          f"più lento: {slow[0]} ({slow[1]['lat']/slow[1]['n']:.0f}s/call media)")


if __name__ == "__main__":
    main()
