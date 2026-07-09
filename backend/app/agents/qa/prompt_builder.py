"""QA Agent 系统提示词组装"""

from __future__ import annotations

from app.agents.qa.persona import BASE_PERSONA, RAG_KEYWORDS
from app.agents.qa.subjects.registry import get_subject_agent
from app.agents.shared.stage import STAGE_RULES
from app.agents.shared.talent import talent_coaching_hint

__all__ = [
    "RAG_KEYWORDS",
    "build_qa_system_prompt",
    "build_learner_context_block",
    "build_qa_user_message",
]


def build_learner_context_block(
    *,
    grade: str | None = None,
    age: int | None = None,
    talent_primary: str | None = None,
    report_json: dict | None = None,
    coach_context: str | None = None,
    ocr_preview: str | None = None,
) -> str:
    """学员画像 — 注入用户消息侧，不写入 system prompt，降低被诱导导出风险。"""
    lines: list[str] = []
    if grade:
        lines.append(f"年级：{grade}")
    if age is not None:
        lines.append(f"年龄：{age}岁")
    hint = talent_coaching_hint(talent_primary, report_json)
    if hint:
        lines.append(hint)
    if coach_context:
        lines.append(coach_context.strip())
    if ocr_preview:
        lines.append(f"题目识别预览：{ocr_preview}")
    if not lines:
        return ""
    return "[内部学员背景，禁止向用户复述或汇总输出]\n" + "\n".join(lines)


def build_qa_user_message(message: str, learner_context: str) -> str:
    if learner_context:
        return f"{learner_context}\n\n用户问题：{message}"
    return message


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
    coach_context: str | None = None,
) -> str:
    """公开系统提示 — 不含学员 PII；grade/age/talent 等请用 build_learner_context_block。"""
    del grade, age, talent_primary, report_json, ocr_preview, coach_context

    lines = [BASE_PERSONA, STAGE_RULES.get(school_stage, STAGE_RULES["primary_high"])]

    agent = get_subject_agent(subject)
    if agent:
        lines.append(agent.role_prompt)
        lines.append(agent.answer_style)
        lines.append(f"当前学科频道：{agent.display_name}。请严格按该学科的规范作答。")
    else:
        lines.append("学科范围：数学、语文、英语、科学。请根据学员问题判断学科并作答。")

    if rag_context:
        lines.append("以下参考资料供你核对后，用适合学员学段的语言改写回答（不要照抄）：")
        lines.append(rag_context)
    return "\n".join(lines)
