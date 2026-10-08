"""兼容门面/seed — 真相源在 harness.llm_catalog（LLM 路由层 PROFILES）。"""

from __future__ import annotations

from typing import Any

from app.harness.llm import profile_system
from app.harness.llm_catalog import (
    CONSULT_PERSONAS,
    FOUNDATION_DOCS,
    FOUNDATION_RULES,
    ConsultPersona,
    consult_persona_system,
)


def get_persona(code: str) -> ConsultPersona:
    key = (code or "dayu").strip().lower()
    return CONSULT_PERSONAS.get(key) or CONSULT_PERSONAS["dayu"]


def persona_welcome(code: str) -> str:
    return get_persona(code).welcome


def persona_system_prompt(code: str, *, custom: str | None = None) -> str:
    """委托 LLM 路由层 profile_system(consult, persona=…)。"""
    return profile_system("consult", persona=code, override=custom)


def persona_meta_seed(code: str) -> dict[str, Any]:
    p = get_persona(code)
    return {
        "tag": p.tag,
        "tp": p.tp,
        "skill": p.skill,
        "chips": list(p.chips),
        "welcome": p.welcome,
        "kb_route": ",".join(p.kb_docs),
        "kb_keywords": list(p.kb_keywords),
        "talent": p.talent,
        "board_enabled": p.board_enabled,
        "foundation": "01,02,03",
    }


def all_persona_codes() -> list[str]:
    return list(CONSULT_PERSONAS.keys())


__all__ = [
    "CONSULT_PERSONAS",
    "ConsultPersona",
    "FOUNDATION_DOCS",
    "FOUNDATION_RULES",
    "all_persona_codes",
    "consult_persona_system",
    "get_persona",
    "persona_meta_seed",
    "persona_system_prompt",
    "persona_welcome",
]
