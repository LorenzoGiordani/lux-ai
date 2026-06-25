"""Layer LLM — GLM-5.2 via Z.ai Coding Plan (endpoint Anthropic-Messages).

Un solo modello, pinnato: GLM-5.2. Nessun claude, nessun opencode: una sola
chiamata HTTP all'endpoint del coding plan di Z.ai (kind=anthropic, header
x-api-key). Punto d'ingresso unico ask() per tutta la pipeline.

Capacità del layer (evoluzione v2):
  • EFFORT MULTI-LIVELLO — max/medium/low/none controllano il budget di extended
    thinking. I ruoli "pesanti" (Analyst, Strategist, evolve) usano max; i ruoli
    di veto/checkbox (Bull, Bear, Risk, Auditor) usano low/medium → risparmio
    token/latenza a parità di decisioni.
  • STRUCTURED OUTPUT NATIVO — passa `schema=<JSON Schema>` e la risposta torna
    come dict già validato via Anthropic tool use (tool_choice forzato). Niente
    più parsing regex fragile: il modello è vincolato dallo schema.
  • TRACING — ogni chiamata logga su paper/llm_calls.jsonl (role, model, effort,
    tokens, latency). Base per osservabilità e ottimizzazione.
  • CACHE APPLICATIVO — cache=True memorizza il risultato per hash(prompt) in
    paper/llm_cache/. Determinismo + costo zero per eval/test/dedup. Il caching
    lato-API (cache_control) NON è supportato dal bridge Z.ai (verificato: il
    campo cache_read resta 0), quindi è tutto client-side.

Config (priorità: env di processo → .env del progetto → config di zcode locale):
  ZAI_API_KEY           api key del coding plan (header x-api-key).
  ZAI_BASE_URL          default https://api.z.ai/api/anthropic
  GLM_MODEL             default GLM-5.2
  GLM_THINKING_BUDGET   budget thinking per effort=max (default 32000).
  GLM_CACHE_DIR         dir cache applicativo (default: paper/llm_cache, attiva).
                        stringa vuota = cache off.
  GLM_CACHE_TTL         TTL cache secondi (default 86400, 0=senza scadenza).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_BASE_URL = "https://api.z.ai/api/anthropic"
DEFAULT_MODEL = "GLM-5.2"
ANTHROPIC_VERSION = "2023-06-01"

# Budget di extended thinking per livello di effort. "max" è overridabile via
# GLM_THINKING_BUDGET; gli altri sono fissi (calibrati sul ruolo: low basta per
# un veto sì/no, medium per un giudizio motivato).
EFFORT_BUDGETS = {"max": 32000, "medium": 4000, "low": 1024, "none": 0}
DEFAULT_MAX_BUDGET = 32000
OUTPUT_RESERVE = 16384  # token riservati alla risposta finale oltre al thinking

# Pattern di errore LLM NON transiente (quota/auth/entitlement): un retry non li
# risolve. Derivati da errori reali del coding plan. Testabili senza rete.
NON_TRANSIENT_ERRORS = (
    "usage limit reached", "weekly usage limit", "resets in",
    "ai_retryerror", "ai_apicallerror", "failed after",
    "insufficient balance", "insufficient credit", "insufficient_quota",
    "rate_limit_error", "unauthorized", "invalid api key",
    "authentication failed", "permission_denied", "not_entitled",
    "coding_plan_not_entitled", "coding_plan_not_connected",
)

LLM_CALLS_LOG = ROOT / "paper/llm_calls.jsonl"


def _dotenv_get(key: str) -> str | None:
    env = ROOT / ".env"
    if not env.exists():
        return None
    for line in env.read_text().splitlines():
        line = line.strip()
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _zcode_api_key() -> str | None:
    cfg = Path.home() / ".zcode/v2/config.json"
    if not cfg.exists():
        return None
    try:
        providers = json.loads(cfg.read_text()).get("provider", {})
        prov = providers.get("builtin:zai-coding-plan", {})
        if prov.get("enabled"):
            return prov.get("options", {}).get("apiKey") or None
    except (json.JSONDecodeError, OSError):
        return None
    return None


def _config(key: str, default: str | None = None) -> str | None:
    val = os.environ.get(key) or _dotenv_get(key)
    return val if val else default


def get_api_key() -> str:
    key = _config("ZAI_API_KEY") or _zcode_api_key()
    if not key:
        raise RuntimeError(
            "ZAI_API_KEY mancante: imposta il secret/env (coding plan Z.ai), "
            "oppure scrivi ZAI_API_KEY=... in .env, oppure fai login in zcode "
            "(provider builtin:zai-coding-plan in ~/.zcode/v2/config.json).")
    return key


def thinking_budget(effort: str) -> int:
    if effort == "max":
        raw = _config("GLM_THINKING_BUDGET", str(DEFAULT_MAX_BUDGET))
        try:
            return max(0, int(raw))
        except ValueError:
            return DEFAULT_MAX_BUDGET
    return EFFORT_BUDGETS.get(effort, 0)


# ─── text helpers ────────────────────────────────────────────────────────────

def _strip_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    return text.strip()


def extract_text(content: list) -> str:
    """Concatena solo i blocchi `text` di una risposta (scarta `thinking`)."""
    out = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            out.append(block.get("text", ""))
    return "".join(out).strip()


def extract_tool_input(content: list):
    """Estrae l'input del primo blocco `tool_use` (structured output)."""
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_use":
            return block.get("input")
    return None


def parse_json(text: str):
    """Fallback robusto: JSON anche circondato da prosa/fence."""
    text = _strip_fence(text)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        text = m.group(0)
    return json.loads(text)


# ─── tracing ─────────────────────────────────────────────────────────────────

def _trace(record: dict) -> None:
    record["ts"] = datetime.now(timezone.utc).isoformat()
    try:
        LLM_CALLS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with LLM_CALLS_LOG.open("a") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except OSError:
        pass  # il tracing non deve mai rompere una chiamata


# ─── cache applicativo (content-hash) ────────────────────────────────────────

def _cache_dir() -> Path | None:
    d = _config("GLM_CACHE_DIR", "paper/llm_cache")
    if not d:
        return None
    return (ROOT / d) if not Path(d).is_absolute() else Path(d)


def _cache_ttl() -> int:
    try:
        return max(0, int(_config("GLM_CACHE_TTL", "86400")))
    except ValueError:
        return 86400


def _cache_key(model: str, system, prompt: str, effort: str, schema, temperature) -> str:
    payload = json.dumps({"m": model, "s": system, "p": prompt, "e": effort,
                          "sc": json.dumps(schema, sort_keys=True) if schema else None,
                          "t": temperature}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def _cache_get(key: str):
    d = _cache_dir()
    if not d:
        return None
    f = d / f"{key}.json"
    if not f.exists():
        return None
    try:
        rec = json.loads(f.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    ttl = _cache_ttl()
    age = time.time() - rec.get("ts_epoch", 0)
    if ttl and age > ttl:
        return None
    return rec.get("result")


def _cache_put(key: str, result, usage: dict) -> None:
    d = _cache_dir()
    if not d:
        return
    try:
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{key}.json").write_text(json.dumps(
            {"result": result, "usage": usage, "ts_epoch": time.time(),
             "ts": datetime.now(timezone.utc).isoformat()}, default=str))
    except OSError:
        pass


# ─── HTTP ────────────────────────────────────────────────────────────────────

def _is_non_transient(text: str) -> str | None:
    low = text.lower()
    for p in NON_TRANSIENT_ERRORS:
        if p in low:
            return p
    return None


def _post(base_url: str, api_key: str, payload: dict, timeout: int) -> dict:
    url = f"{base_url.rstrip('/')}/v1/messages"
    headers = {"content-type": "application/json",
               "anthropic-version": ANTHROPIC_VERSION, "x-api-key": api_key}
    last_err = None
    for attempt in range(3):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=timeout)
        except requests.RequestException as e:
            last_err = f"rete irraggiungibile: {type(e).__name__}: {str(e)[:160]}"
            time.sleep(2 ** attempt)
            continue
        if r.status_code == 200:
            return r.json()
        body = (r.text or "")[:500]
        marker = _is_non_transient(body) or _is_non_transient(f"{r.status_code} {body}")
        if marker:
            raise RuntimeError(f"GLM-5.2 non disponibile (non transiente: {marker}): "
                               f"HTTP {r.status_code} {body[:200]}")
        if r.status_code in (401, 403):
            raise RuntimeError(f"auth coding plan fallita (HTTP {r.status_code}): {body[:200]}")
        if r.status_code == 429 or 500 <= r.status_code < 600:
            last_err = f"HTTP {r.status_code} {body[:200]}"
            time.sleep(2 ** attempt)
            continue
        raise RuntimeError(f"chiamata LLM fallita (HTTP {r.status_code}): {body[:200]}")
    raise RuntimeError(f"GLM-5.2 non raggiungibile dopo 3 tentativi: {last_err}")


def ask(prompt: str, system: str | None = None, as_json: bool = False,
        effort: str = "max", schema: dict | None = None, schema_name: str = "answer",
        role: str | None = None, cache: bool = False, temperature: float | None = None,
        timeout: int = 300):
    """Una chiamata a GLM-5.2 via Z.ai Coding Plan.

    - effort: max/medium/low/none (budget di extended thinking). Default max.
    - schema: se passato (JSON Schema dict), la risposta è structured via tool use
      forzato → ritorna un dict già validato (as_json implicito, niente parsing).
    - as_json: fallback (senza schema) — parsare JSON dal testo libero.
    - role: etichetta per il tracing (es. "strategist").
    - cache: se True, memoizza per hash(prompt) — determinismo + costo zero su
      ripetizioni (eval, test, re-run).
    - temperature: inoltrata all'API (per self-consistency: più alto = più varianza).

    Ritorna str (testo), oppure dict/list se schema/as_json. Solleva RuntimeError
    su errori di quota/auth/rete con messaggio actionable."""
    model = _config("GLM_MODEL", DEFAULT_MODEL)
    base_url = _config("ZAI_BASE_URL", DEFAULT_BASE_URL)
    api_key = get_api_key()

    key = _cache_key(model, system, prompt, effort, schema, temperature)
    if cache:
        hit = _cache_get(key)
        if hit is not None:
            _trace({"role": role, "model": model, "effort": effort, "ok": True,
                    "cached": True, "latency_s": 0.0, "usage": {}})
            return hit

    budget = thinking_budget(effort)
    thinking_on = budget > 0

    payload: dict = {
        "model": model,
        "max_tokens": (budget + OUTPUT_RESERVE) if thinking_on else OUTPUT_RESERVE,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        payload["system"] = system
    if temperature is not None:
        payload["temperature"] = temperature
    if thinking_on:
        payload["thinking"] = {"type": "enabled", "budget_tokens": budget}
    if schema:
        payload["tools"] = [{"name": schema_name, "description": f"Output strutturato per {schema_name}",
                             "input_schema": schema}]
        payload["tool_choice"] = {"type": "tool", "name": schema_name}

    t0 = time.time()
    ok, err, data, result = True, None, None, None
    try:
        data = _post(base_url, api_key, payload, timeout)
        if schema:
            result = extract_tool_input(data.get("content", []))
            if result is None:  # safety net: il modello a volte risponde in testo
                txt = extract_text(data.get("content", []))
                result = parse_json(txt) if txt else None
            if result is None:
                raise RuntimeError("risposta senza tool_use e senza JSON testuale")
        elif as_json:
            result = parse_json(extract_text(data.get("content", [])))
        else:
            result = extract_text(data.get("content", []))
            if not result:
                raise RuntimeError("risposta GLM-5.2 senza testo")
    except Exception as e:
        ok, err = False, f"{type(e).__name__}: {str(e)[:200]}"
        _trace({"role": role, "model": model, "effort": effort, "ok": False, "cached": False,
                "latency_s": round(time.time() - t0, 2), "error": err, "usage": {}})
        raise
    latency = round(time.time() - t0, 2)
    usage = data.get("usage", {}) if data else {}
    _trace({"role": role, "model": model, "effort": effort, "ok": True, "cached": False,
            "latency_s": latency, "thinking_budget": budget if thinking_on else 0,
            "schema": schema_name if schema else None,
            "usage": {"in": usage.get("input_tokens"), "out": usage.get("output_tokens"),
                      "cache_read": usage.get("cache_read_input_tokens", 0)}})
    if cache:
        _cache_put(key, result, usage)
    return result


def model_label() -> str:
    return _config("GLM_MODEL", DEFAULT_MODEL)


if __name__ == "__main__":
    print(f"[llm] modello={model_label()} base={_config('ZAI_BASE_URL', DEFAULT_BASE_URL)}")
    out = ask("Rispondi con una sola parola: OK", effort="max", role="smoke")
    print(f"[llm] text: {out!r}")
    # structured output test
    sch = {"type": "object",
           "properties": {"ok": {"type": "boolean"}, "n": {"type": "integer"}},
           "required": ["ok", "n"]}
    st = ask("Rispondi ok=true e n=42", schema=sch, schema_name="smoke", role="smoke_struct")
    print(f"[llm] struct: {st!r} (type {type(st).__name__})")
