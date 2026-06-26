"""学科答疑 Prompt — 兼容层，实现已迁至 app.agents.qa"""

from app.agents.qa.persona import RAG_KEYWORDS
from app.agents.qa.prompt_builder import build_qa_system_prompt
from app.agents.shared.stage import STAGE_RULES, infer_school_stage
from app.agents.shared.talent import TALENT_COACH, talent_coaching_hint

__all__ = [
    "STAGE_RULES",
    "TALENT_COACH",
    "RAG_KEYWORDS",
    "infer_school_stage",
    "talent_coaching_hint",
    "build_qa_system_prompt",
]
