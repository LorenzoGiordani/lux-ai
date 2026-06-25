"""Reviewer — post-mortem dei trade chiusi → lezioni (il learning loop).

Ogni trade chiuso senza review produce una lezione in paper/lessons.jsonl.
Le lezioni rientrano nei prompt di Strategist/Risk (recall in decide.py):
errore → lezione → comportamento corretto = criterio di successo Fase 1.

Modi:
  uv run scripts/review.py            # auto via GLM-5.2 (Z.ai Coding Plan)
  uv run scripts/review.py --pack     # stampa i post-mortem pendenti (LLM in sessione)
  uv run scripts/review.py --add f.jsonl  # appende lezioni scritte dalla sessione
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

JOURNAL = ROOT / "paper/journal.jsonl"
LESSONS = ROOT / "paper/lessons.jsonl"

REVIEWER = (
    "Sei il Reviewer di un trading desk. Post-mortem onesto del trade chiuso: "
    "1) la tesi era giusta o sbagliata? (distingui tesi sbagliata da sfortuna/timing) "
    "2) l'esecuzione (stop/target/time-stop) era adeguata alla tesi? "
    "3) UNA lezione actionable e generale (non 'ZEC è sceso' ma 'i fade di crowding in regime bear "
    "richiedono X'). Rispondi SOLO con JSON: "
    '{"verdict": "thesis_right"|"thesis_wrong"|"execution_issue"|"luck", "lesson": str, "tags": [str]}'
)


def events() -> list[dict]:
    if not JOURNAL.exists():
        return []
    return [json.loads(l) for l in JOURNAL.read_text().splitlines()]


def reviewed_keys() -> set:
    if not LESSONS.exists():
        return set()
    return {json.loads(l).get("trade_key") for l in LESSONS.read_text().splitlines()}


def pending() -> list[dict]:
    evs = events()
    opens = {}
    for e in evs:
        if e.get("type") == "open":
            opens[(e.get("strategy"), e.get("symbol"))] = e
    done = reviewed_keys()
    out = []
    for e in evs:
        if e.get("type") != "close":
            continue
        key = f"{e.get('strategy')}|{e.get('symbol')}|{e.get('ts')}"
        if key in done:
            continue
        o = opens.get((e.get("strategy"), e.get("symbol")), {})
        out.append({"trade_key": key, "open": o, "close": e})
    return out


def add_lessons(path: str) -> None:
    LESSONS.parent.mkdir(exist_ok=True)
    n = 0
    with LESSONS.open("a") as f:
        for line in Path(path).read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                rec["logged_at"] = datetime.now(timezone.utc).isoformat()
                f.write(json.dumps(rec) + "\n")
                n += 1
    print(f"{n} lezioni aggiunte")


def append_lesson(rec: dict) -> None:
    """Canale unificato per scrivere una lezione singola (usato da promote.py).
    Mantiene lo schema compatibile con --add: trade_key, symbol, verdict,
    lesson, tags, logged_at. Aggiunge logged_at se mancante."""
    LESSONS.parent.mkdir(exist_ok=True)
    rec.setdefault("logged_at", datetime.now(timezone.utc).isoformat())
    with LESSONS.open("a") as f:
        f.write(json.dumps(rec) + "\n")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "auto"
    if mode == "--add":
        add_lessons(sys.argv[2])
        return

    todo = pending()
    if not todo:
        print("nessun trade da rivedere")
        return

    if mode == "--pack":
        print(f"=== {len(todo)} post-mortem pendenti ===\n{REVIEWER}\n")
        for t in todo:
            print(f"--- trade_key: {t['trade_key']}")
            print(json.dumps({"open": t["open"], "close": t["close"]}, indent=1, default=str))
        print('\nOutput atteso (una riga JSONL per trade): {"trade_key": ..., "verdict": ..., "lesson": ..., "tags": [...], "pnl_usd": ...}')
        return

    from scripts.decide import _ask_role
    LESSONS.parent.mkdir(exist_ok=True)
    with LESSONS.open("a") as f:
        for t in todo:
            res = _ask_role("reviewer", f"TRADE:\n{json.dumps({'open': t['open'], 'close': t['close']}, default=str)}")
            rec = {"trade_key": t["trade_key"], "symbol": t["close"].get("symbol"),
                   "strategy": t["close"].get("strategy"), "pnl_usd": t["close"].get("pnl_usd"),
                   **res, "logged_at": datetime.now(timezone.utc).isoformat()}
            f.write(json.dumps(rec) + "\n")
            print(f"  lezione [{rec['verdict']}] {rec['symbol']}: {rec['lesson'][:80]}")


if __name__ == "__main__":
    main()
