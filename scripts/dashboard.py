"""Dashboard statica — la piattaforma "ricerca in pubblico" v0.

Genera dashboard/index.html dai journal: equity curve, posizioni aperte,
decisioni con tesi, lezioni, lineage strategie. Zero processi residenti
(Mac 8GB), pubblicabile su Cloudflare Pages quando si vuole andare live.
"""

import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dashboard/index.html"


def jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def sparkline(points: list[float], w: int = 600, h: int = 120) -> str:
    if len(points) < 2:
        return "<p class='muted'>equity curve: servono più heartbeat</p>"
    lo, hi = min(points), max(points)
    rng = (hi - lo) or 1
    xs = [i * w / (len(points) - 1) for i in range(len(points))]
    ys = [h - 8 - (p - lo) / rng * (h - 16) for p in points]
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    color = "#2e9e5b" if points[-1] >= points[0] else "#c0392b"
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}">'
            f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{pts}"/></svg>')


def table(rows: list[dict], cols: list[str]) -> str:
    if not rows:
        return "<p class='muted'>—</p>"
    head = "".join(f"<th>{c}</th>" for c in cols)
    body = "".join("<tr>" + "".join(f"<td>{html.escape(str(r.get(c, '')))[:240]}</td>" for c in cols) + "</tr>"
                   for r in rows)
    return f"<table><tr>{head}</tr>{body}</table>"


def main() -> None:
    state = json.loads((ROOT / "paper/state.json").read_text()) if (ROOT / "paper/state.json").exists() else {}
    journal = jsonl(ROOT / "paper/journal.jsonl")
    decisions = jsonl(ROOT / "paper/decisions.jsonl")
    lessons = jsonl(ROOT / "paper/lessons.jsonl")

    sections = [f"<h1>DeFi AI Vault — paper trading live</h1>"
                f"<p class='muted'>aggiornato {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC · "
                f"balance fittizio, dati e prezzi reali · nessun fondo</p>"]

    for sid, st in state.items():
        beats = [e["equity"] for e in journal if e.get("type") == "heartbeat" and e.get("strategy") == sid]
        pos_rows = [{"symbol": s, **{k: p.get(k) for k in ("direction", "entry_px", "size_usd", "stop_px", "target_px", "opened_at")}}
                    for s, p in st.get("positions", {}).items()]
        closes = [e for e in journal if e.get("type") == "close" and e.get("strategy") == sid]
        pnl = sum(e.get("pnl_usd", 0) for e in closes)
        sections.append(
            f"<h2>{html.escape(sid)}</h2>"
            f"<p><b>equity {st['equity']:.2f}$</b> · trade chiusi {len(closes)} · pnl realizzato {pnl:+.2f}$</p>"
            + sparkline(beats)
            + "<h3>posizioni aperte</h3>" + table(pos_rows, ["symbol", "direction", "entry_px", "size_usd", "stop_px", "target_px", "opened_at"])
            + "<h3>ultimi trade chiusi</h3>" + table(closes[-10:][::-1], ["ts", "symbol", "reason", "exit_px", "pnl_usd"]))

    dec_rows = [{"ts": d.get("logged_at", "")[:16], "symbol": d.get("proposal", {}).get("symbol"),
                 "direction": d.get("proposal", {}).get("direction"),
                 "risk": d.get("risk", {}).get("verdict"),
                 "thesis": d.get("proposal", {}).get("thesis", "")}
                for d in decisions if d.get("stage") == "final"]
    sections.append("<h2>Decisioni della pipeline (tesi pubbliche)</h2>"
                    + table(dec_rows[-15:][::-1], ["ts", "symbol", "direction", "risk", "thesis"]))

    sections.append("<h2>Lezioni apprese</h2>"
                    + table([{"ts": l.get("logged_at", "")[:16], "symbol": l.get("symbol"),
                              "verdict": l.get("verdict"), "lesson": l.get("lesson")}
                             for l in lessons[-15:][::-1]], ["ts", "symbol", "verdict", "lesson"]))

    lineage = []
    for f in sorted((ROOT / "strategies/generated").glob("*.yaml")):
        if "candidates" in f.name:
            continue
        s = yaml.safe_load(f.read_text())
        agg = next(iter(s.get("backtest", {}).values()), {}).get("aggregate") or \
              next(iter(s.get("backtest", {}).values()), {}).get("metrics", {})
        lineage.append({"id": s["id"], "parent": s.get("parent"), "status": s.get("status"),
                        "sharpe": round(agg.get("mean_sharpe", agg.get("sharpe", 0)), 2),
                        "note": s.get("evolution", {}).get("notes", "")})
    sections.append("<h2>Evoluzione strategie (lineage)</h2>"
                    + table(lineage, ["id", "parent", "status", "sharpe", "note"]))

    css = ("body{font-family:-apple-system,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;"
           "background:#0f1115;color:#e6e6e6}h1,h2{border-bottom:1px solid #333;padding-bottom:.3rem}"
           "table{border-collapse:collapse;width:100%;font-size:.85rem}td,th{border:1px solid #2a2d35;"
           "padding:.35rem .5rem;text-align:left;vertical-align:top}th{background:#1a1d24}"
           ".muted{color:#888}")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(f"<!doctype html><meta charset='utf-8'><title>DeFi AI Vault</title>"
                   f"<style>{css}</style>" + "\n".join(sections))
    print(f"dashboard → {OUT}")


if __name__ == "__main__":
    main()
