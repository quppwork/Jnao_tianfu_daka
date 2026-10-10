"""家长天赋咨询 — Agent 核在 runner；人设真相源在 harness.llm PROFILES。"""

from app.agents.consult.personas import (
    CONSULT_PERSONAS,
    get_persona,
    persona_system_prompt,
    persona_welcome,
)
from app.agents.consult.runner import generate_consult_reply

__all__ = [
    "CONSULT_PERSONAS",
    "generate_consult_reply",
    "get_persona",
    "persona_system_prompt",
    "persona_welcome",
]
