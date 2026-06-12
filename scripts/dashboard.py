"""Dashboard VETRO — inietta i dati reali nel template di design.

Il markup vive in dashboard/template.html (handoff da Claude Design, non
toccarlo per cambiare i dati): qui si costruisce SOLO il blocco JSON
(<script id="data">) dallo stato reale e si scrive dashboard/index.html.
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "dashboard/template.html"
OUT = ROOT / "dashboard/index.html"

ACCOUNT_META = {
    "agents-v1": {"label": "Agenti LLM", "tag": "pipeline decide"},
    "tsmom-v1": {"label": "TSMOM challenger", "tag": "sistematico multi-asset"},
    "funding-squeeze-breakout-g2-g1-g2": {"label": "Funding-squeeze", "tag": "segnali crypto"},
}


def jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def ts_short(s: str) -> str:
    """Qualsiasi timestamp → 'YYYY-MM-DD HH:MM' (il JS del template lo richiede)."""
    s = str(s).replace("T", " ")
    return s[:16]


def clean_symbol(s: str) -> str:
    return str(s).removeprefix("xyz_")


def build_data() -> dict:
    state = json.loads((ROOT / "paper/state.json").read_text()) if (ROOT / "paper/state.json").exists() else {}
    journal = jsonl(ROOT / "paper/journal.jsonl")
    decisions = jsonl(ROOT / "paper/decisions.jsonl")
    lessons = jsonl(ROOT / "paper/lessons.jsonl")

    accounts = []
    for sid, st in state.items():
        meta = ACCOUNT_META.get(sid, {"label": sid, "tag": ""})
        closes = [e for e in journal if e.get("type") == "close" and e.get("strategy") == sid]
        curve = [[ts_short(e["logged_at"]), round(e["equity"], 2)] for e in journal
                 if e.get("type") == "heartbeat" and e.get("strategy") == sid]
        accounts.append({
            "id": sid, "label": meta["label"], "tag": meta["tag"],
            "equity": round(st["equity"], 2),
            "pnl_realized": round(sum(e.get("pnl_usd", 0) for e in closes), 2),
            "trades_closed": len(closes),
            "wins": sum(1 for e in closes if e.get("pnl_usd", 0) > 0),
            "equity_curve": curve,
            "positions": [{
                "symbol": clean_symbol(s), "direction": p["direction"],
                "entry_px": round(p["entry_px"], 6), "size_usd": round(p["size_usd"], 2),
                "stop_px": round(p["stop_px"], 6), "target_px": round(p["target_px"], 6),
                "opened_at": ts_short(p["opened_at"]),
            } for s, p in st.get("positions", {}).items()],
        })

    dec_out = []
    for d in decisions:
        if d.get("stage") != "final":
            continue
        p = d.get("proposal", {})
        if p.get("action") != "trade":
            continue
        risk = d.get("risk", {})
        sym = clean_symbol(p.get("symbol", ""))
        # esito: primo close di agents-v1 sullo stesso simbolo dopo la decisione
        outcome = {"closed": False}
        for e in journal:
            if (e.get("type") == "close" and e.get("strategy") == "agents-v1"
                    and clean_symbol(e.get("symbol", "")) == sym
                    and e.get("logged_at", "") > d.get("logged_at", "")):
                outcome = {"closed": True, "reason": e.get("reason"),
                           "pnl_usd": round(e.get("pnl_usd", 0), 2)}
                break
        rec = {
            "ts": ts_short(d.get("logged_at", "")), "symbol": sym,
            "direction": p.get("direction"), "account": "agents-v1",
            "risk_verdict": risk.get("verdict", "approve"),
            "thesis": p.get("thesis", ""), "invalidation": p.get("invalidation", ""),
            "outcome": outcome,
        }
        if risk.get("size_multiplier") not in (None, 1, 1.0):
            rec["size_multiplier"] = risk["size_multiplier"]
        dec_out.append(rec)
    dec_out.reverse()  # cronologico inverso

    les_out = [{
        "ts": ts_short(l.get("logged_at", "")), "scope": clean_symbol(l.get("symbol", "")),
        "verdict": l.get("verdict", ""), "lesson": l.get("lesson", ""), "tags": l.get("tags", []),
    } for l in lessons][::-1]

    lineage = []
    files = sorted(ROOT.glob("strategies/*.yaml")) + sorted(ROOT.glob("strategies/generated/*.yaml"))
    for f in files:
        if "candidates" in f.name:
            continue
        s = yaml.safe_load(f.read_text())
        bt = next(iter(s.get("backtest", {}).values()), {})
        agg = bt.get("aggregate") or bt.get("metrics") or {}
        sharpe = agg.get("mean_sharpe", agg.get("sharpe", 0)) or 0
        lineage.append({"id": s["id"], "parent": s.get("parent"),
                        "status": s.get("status", "candidate"), "sharpe": round(float(sharpe), 2),
                        "note": s.get("evolution", {}).get("notes", "")[:160]})

    return {
        "updated_utc": f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M}",
        "accounts": accounts, "decisions": dec_out, "lessons": les_out, "lineage": lineage,
    }


def main() -> None:
    data = build_data()
    html = TEMPLATE.read_text()
    block = f'<script id="data" type="application/json">\n{json.dumps(data, ensure_ascii=False, indent=1)}\n</script>'
    out, n = re.subn(r'<script id="data" type="application/json">.*?</script>', block, html, flags=re.DOTALL)
    if n != 1:
        sys.exit("ERRORE: blocco #data non trovato nel template")
    OUT.write_text(out)
    print(f"dashboard VETRO → {OUT}")


if __name__ == "__main__":
    main()
