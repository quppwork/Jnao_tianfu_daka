"""QA Agent 系统提示词组装"""

from __future__ import annotations

from app.agents.qa.persona import BASE_PERSONA, RAG_KEYWORDS
from app.agents.qa.subjects.registry import get_subject_agent
from app.agents.shared.stage import STAGE_RULES
from app.agents.shared.talent import talent_coaching_hint

__all__ = ["RAG_KEYWORDS", "build_qa_system_prompt"]


def build_qa_system_prompt(
    *,
    school_stage: str = "primary_high",
    grade: str | None = None,
    age: int | None = None,
    talent_primary: str | None = None,
    report_json: dict | None = None,
    subject: str | None = None,
    rag_context: str | None = None,
    ocr_preview: str | None = None,
) -> str:
    lines = [BASE_PERSONA, STAGE_RULES.get(school_stage, STAGE_RULES["primary_high"])]

    agent = get_subject_agent(subject)
    if agent:
        lines.append(agent.role_prompt)
        lines.append(agent.answer_style)
        lines.append(f"当前学科频道：{agent.display_name}。请严格按该学科的规范作答。")
    else:
        lines.append("学科范围：数学、语文、英语、科学。请根据学员问题判断学科并作答。")

    if grade:
        lines.append(f"年级：{grade}。")
    if age:
        lines.append(f"年龄：{age} 岁。")
    lines.append(talent_coaching_hint(talent_primary, report_json))
    if ocr_preview:
        lines.append(f"题目识别预览：{ocr_preview}")
    if rag_context:
        lines.append("以下参考资料供你核对后，用适合学员学段的语言改写回答（不要照抄）：")
        lines.append(rag_context)
    return "\n".join(lines)
