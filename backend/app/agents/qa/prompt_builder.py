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


_METHOD_KB_HEADER = (
    "—— 平台特殊训练方法（知识库）——\n"
    "以下为平台知识库检索到的练法/学法资料。回答学法或训练相关问题时："
    "必须优先用这些方法组织建议，强调系统训练与正确步骤，不要改成普通刷题/题海套路；"
    "资料不足时再补充简短学科步骤。用适合学员学段的语言改写，不要照抄原文。"
)

_LEGACY_RAG_HEADER = "以下参考资料供你核对后，用适合学员学段的语言改写回答（不要照抄）："


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
    memory_digest: str | None = None,
    strategy_block: str | None = None,
    rag_kind: str | None = None,
) -> str:
    """公开系统提示 — 不含学员 PII；grade/age/talent 等请用 build_learner_context_block。

    rag_kind: \"method\" | \"legacy\" | None — 控制知识库注入口吻。
    """
    del grade, age, talent_primary, report_json, ocr_preview, coach_context

    lines = [BASE_PERSONA, STAGE_RULES.get(school_stage, STAGE_RULES["primary_high"])]

    agent = get_subject_agent(subject)
    if agent:
        lines.append(agent.role_prompt)
        lines.append(agent.answer_style)
        lines.append(
            f"当前学科频道：{agent.display_name}。"
            "请严格按该学科规范作答，并全程服从其中的【人物性格提示词】控制语气与句式。"
        )
    else:
        lines.append(
            "学科范围：数学、语文、英语、科学、学习心法。"
            "请根据学员问题判断学科并作答；未指定时先确认学科再精讲。"
        )

    if strategy_block:
        lines.append(strategy_block)
    if memory_digest:
        lines.append(memory_digest)
    if rag_context:
        kind = (rag_kind or "legacy").strip().lower()
        if kind == "method":
            lines.append(_METHOD_KB_HEADER)
        else:
            lines.append(_LEGACY_RAG_HEADER)
        lines.append(rag_context)
    return "\n".join(lines)
