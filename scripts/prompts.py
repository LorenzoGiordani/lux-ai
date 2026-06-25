"""Loader dei prompt centralizzati (prompts/roles.yaml).

Centralizzare i prompt = tracciabilità: il journal può registrare quale versione
ha prodotto quali trade, e si possono A/B testare cambiando il testo + bumpando
`version`. Nessuna stringa di prompt nei file di logica di trading.

Uso:
    from scripts.prompts import get_role, SCHEMA
    r = get_role("strategist")     # Role(system=..., effort="max", schema_name="propose")
    SCHEMA["propose"]              # JSON Schema dict per structured output
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

PROMPTS_FILE = Path(__file__).resolve().parent.parent / "prompts/roles.yaml"


@dataclass(frozen=True)
class Role:
    name: str
    system: str
    effort: str = "max"
    schema_name: str | None = None  # se presente → structured output via tool use
    json: bool = False              # fallback parsing testuale (raramente usato)


@lru_cache(maxsize=1)
def _load() -> dict:
    return yaml.safe_load(PROMPTS_FILE.read_text())


def prompts_version() -> int:
    return _load().get("version", 0)


def SCHEMA() -> dict:
    """Dict nome→JSON Schema (Anthropic input_schema per tool use)."""
    return _load().get("schemas", {})


def role_names() -> list[str]:
    return list(_load().get("roles", {}).keys())


def get_role(name: str) -> Role:
    """Restituisce la Role configurata. KeyError se il ruolo non esiste
    (fail-fast: un typo nel nome si scopre subito, non a runtime in cron)."""
    roles = _load().get("roles", {})
    if name not in roles:
        raise KeyError(f"ruolo '{name}' non in {PROMPTS_FILE}. Disponibili: {list(roles)}")
    cfg = roles[name]
    return Role(
        name=name,
        system=cfg["system"].strip(),
        effort=cfg.get("effort", "max"),
        schema_name=cfg.get("schema_name"),
        json=cfg.get("json", False),
    )
