"""Test: layer LLM (GLM-5.2 via OpenRouter) — robustezza + nuove capacità.

Tutto OFFLINE (no rete, no chiamate al modello). Verifica:
  1. NON_TRANSIENT_ERRORS cattura errori reali quota/auth/credit di OpenRouter
     (fail-fast), senza falsi positivi su prosa di trading.
  2. extract_text() legge choices[0].message.content (formato OpenAI);
     extract_tool_input() parsa arguments dal primo tool_call (structured output).
  3. parse_json() robusto a prosa + markdown fence.
  4. reasoning_effort() mappa effort→enum (max→high, none→omesso).
  5. aggregate_proposals(): majority vote dello Strategist (self-consistency).
  6. prompts loader: ruoli/schemi dal yaml, effort + schema_name corretti.
  7. cache applicativo: put poi get ritorna lo stesso risultato.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.llm import (NON_TRANSIENT_ERRORS, extract_text, extract_tool_input,
                         parse_json, reasoning_effort, max_tokens_for)
from scripts.decide import aggregate_proposals
from scripts.prompts import get_role, SCHEMA, role_names


# ─── 1. errori non transienti ────────────────────────────────────────────────
def _hits(text: str) -> str | None:
    low = text.lower()
    for p in NON_TRANSIENT_ERRORS:
        if p in low:
            return p
    return None


def test_insufficient_credits_caught():
    # OpenRouter 402: "insufficient credits"
    assert _hits('{"error":{"code":402,"message":"Insufficient credits"}}')


def test_invalid_api_key_caught():
    assert _hits("401 Unauthorized: invalid api key")


def test_no_credit_caught():
    assert _hits("error: no credit on account")


def test_rate_limit_not_non_transient():
    # 429 rate limit è TRANSIENTE (retry) — NON deve essere catturato qui
    assert not _hits("429 Too Many Requests: rate limit exceeded")


def test_legit_output_not_false_positive():
    legit = ("La tesi e' un breakout di trend su BTC con funding neutro. "
             "Direzione long, stop 3%. Il limite di rischio e' rispettato.")
    assert not _hits(legit)


# ─── 2. estrazione contenuto (formato OpenAI) ────────────────────────────────
def test_extract_text_returns_content_string():
    # OpenAI: message.content è una stringa (non lista di blocchi)
    message = {"role": "assistant", "content": "A B"}
    assert extract_text(message) == "A B"


def test_extract_text_empty_when_no_content():
    assert extract_text({"role": "assistant", "content": None}) == ""


def test_extract_tool_input_parses_arguments():
    # arguments è una stringa JSON su OpenAI format (non dict già pronto)
    message = {"role": "assistant", "content": None,
               "tool_calls": [{"id": "c1", "type": "function",
                               "function": {"name": "propose",
                                            "arguments": '{"action": "trade", "symbol": "BTC"}'}}]}
    assert extract_tool_input(message) == {"action": "trade", "symbol": "BTC"}


def test_extract_tool_input_none_when_absent():
    assert extract_tool_input({"role": "assistant", "content": "x"}) is None


# ─── 3. parse_json ───────────────────────────────────────────────────────────
def test_parse_json_from_fence_and_prose():
    raw = 'Ecco:\n```json\n{"action": "trade", "symbol": "BTC"}\n```\nok.'
    assert parse_json(raw) == {"action": "trade", "symbol": "BTC"}


def test_parse_json_plain():
    assert parse_json('{"a": 1}') == {"a": 1}


# ─── 4. effort → reasoning_effort enum ───────────────────────────────────────
def test_reasoning_effort_levels():
    assert reasoning_effort("max") == "high"
    assert reasoning_effort("medium") == "medium"
    assert reasoning_effort("low") == "low"
    assert reasoning_effort("none") is None


def test_reasoning_effort_unknown_defaults_none():
    assert reasoning_effort("inesistente") is None


def test_max_tokens_scales_with_effort():
    # effort alto → più spazio (reasoning + content); none → solo output
    assert max_tokens_for("max") > max_tokens_for("medium")
    assert max_tokens_for("medium") > max_tokens_for("low")
    assert max_tokens_for("none") > 0
    assert max_tokens_for("inesistente") > 0  # fallback sicuro


# ─── 5. self-consistency (aggregate_proposals) ───────────────────────────────
def test_aggregate_majority_no_trade():
    votes = [{"action": "no_trade"}, {"action": "no_trade"},
             {"action": "trade", "symbol": "BTC", "direction": "long"}]
    agg = aggregate_proposals(votes)
    assert agg["action"] == "no_trade"


def test_aggregate_trade_plurality_and_averaging():
    votes = [
        {"action": "trade", "symbol": "BTC", "direction": "long", "leverage": 2,
         "risk_pct": 1, "stop_pct": 3, "target_r": 2, "time_stop_h": 72},
        {"action": "trade", "symbol": "BTC", "direction": "long", "leverage": 2,
         "risk_pct": 1, "stop_pct": 4, "target_r": 2, "time_stop_h": 96},
        {"action": "trade", "symbol": "ETH", "direction": "long", "leverage": 2,
         "risk_pct": 1, "stop_pct": 5, "target_r": 2, "time_stop_h": 72},
    ]
    agg = aggregate_proposals(votes)
    assert agg["action"] == "trade"
    assert (agg["symbol"], agg["direction"]) == ("BTC", "long")
    assert agg["stop_pct"] == 3.5          # media di 3 e 4 (i due allineati)
    assert agg["sc_consensus"] == 2 and agg["sc_votes"] == 3


def test_aggregate_tie_picks_one():
    # 1 no_trade + 2 trade su asset diversi → n_no*2(2) >= len(3)? 2>=3? no → trade,
    # plurality su (symbol,direction): 1-1 → most_common breaka il pareggio
    votes = [{"action": "no_trade"},
             {"action": "trade", "symbol": "BTC", "direction": "long",
              "risk_pct": 1, "stop_pct": 3, "target_r": 2, "time_stop_h": 72, "leverage": 2},
             {"action": "trade", "symbol": "ETH", "direction": "long",
              "risk_pct": 1, "stop_pct": 3, "target_r": 2, "time_stop_h": 72, "leverage": 2}]
    agg = aggregate_proposals(votes)
    assert agg["action"] == "trade" and agg["symbol"] in ("BTC", "ETH")


def test_aggregate_empty_raises():
    try:
        aggregate_proposals([])
        assert False, "doveva raise"
    except RuntimeError:
        pass


# ─── 6. prompts loader ───────────────────────────────────────────────────────
def test_roles_and_schemas_loaded():
    names = role_names()
    for r in ("analyst", "strategist", "risk", "auditor", "pm", "reviewer", "evolve"):
        assert r in names
    assert set(SCHEMA().keys()) >= {"propose", "risk_verdict", "lesson", "candidates"}


def test_role_effort_and_schema():
    assert get_role("strategist").effort == "max"
    assert get_role("strategist").schema_name == "propose"
    assert get_role("bull").effort == "low"
    assert get_role("risk").effort == "medium"
    assert get_role("risk").schema_name == "risk_verdict"


def test_unknown_role_raises():
    try:
        get_role("inesistente")
        assert False
    except KeyError:
        pass


# ─── 7. cache applicativo ────────────────────────────────────────────────────
def test_cache_put_get(monkeypatch=None):
    from scripts import llm as L
    os.environ["GLM_CACHE_DIR"] = "paper/llm_cache_test"
    os.environ["GLM_CACHE_TTL"] = "0"  # senza scadenza
    try:
        k = "testkey123"
        L._cache_put(k, {"x": 1}, {"in": 10})
        assert L._cache_get(k) == {"x": 1}
        assert L._cache_get("inesistente") is None
    finally:
        d = L._cache_dir()
        if d and d.exists():
            for f in d.glob("*.json"):
                f.unlink()
            d.rmdir()
        del os.environ["GLM_CACHE_DIR"]
        del os.environ["GLM_CACHE_TTL"]


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fails = 0
    for fn in fns:
        try:
            fn(); print(f"PASS {fn.__name__}")
        except Exception:
            fails += 1; print(f"FAIL {fn.__name__}"); traceback.print_exc()
    print(f"\n{len(fns)-fails}/{len(fns)} passed")
    sys.exit(1 if fails else 0)
