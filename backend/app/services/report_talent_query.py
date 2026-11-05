"""报告页问句：是否按需拉报告片段，再拼知识库问句。"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import TalentAssessment

# 问「我这份报告」才拉库；纯概念/练法不塞摘要
_REPORT_NEED = re.compile(
    r"(这份报告|我的报告|本份报告|测评报告|报告里|报告中|"
    r"我的(分数|五者|五维|状态|天赋)|"
    r"(五者分值|五维能量|当前状态)|"
    r"怎么看(这份|我的)?报告|"
    r"报告(怎么看|解读|分析))",
    re.I,
)

_SECTION_HINTS: tuple[tuple[str, str], ...] = (
    ("五维", "五维"),
    ("能力", "五维"),
    ("五者", "五者"),
    ("分值", "五者"),
    ("状态", "状态"),
    ("类型", "类型"),
    ("解读", "解读"),
)


def needs_report_context(question: str) -> bool:
    q = (question or "").strip()
    if not q:
        return False
    return bool(_REPORT_NEED.search(q))


def pick_report_section(question: str) -> str:
    q = (question or "").strip()
    for needle, section in _SECTION_HINTS:
        if needle in q:
            return section
    return "全部"


GROUNDED_SYSTEM = (
    "你是成人报告页「问大宇」助手。\n"
    "【事实优先级】用户消息里「本份测评报告事实」是唯一事实来源："
    "天赋类型、五维分数、五者分、状态等必须按原文引用；"
    "禁止使用知识库样例、其它人报告或训练记忆里的数字。\n"
    "【RAG 角色】「解读方法」只提供讲解框架与练法建议，不得覆盖或改写报告数字；"
    "若方法文案里出现与报告不符的分数，一律忽略那些分数。\n"
    "报告未写明的项如实说「本份报告未给出」，不要编造。\n"
    "回答简洁分点，先陈述真实分值再给解读建议。"
)


def _wrap_with_report(summary: str, user_text: str) -> str:
    return (
        "【本份测评报告摘要】\n"
        f"{summary}\n\n"
        "【用户问题】\n"
        f"{user_text}\n\n"
        "请结合报告摘要与知识库作答；报告里没有的分数/结论不要编造。"
    )


def build_grounded_messages(
    *,
    report_facts: str,
    rag_method: str,
    user_text: str,
) -> list[dict[str, str]]:
    rag = (rag_method or "").strip() or "（本次未检索到额外方法资料，仅依据报告事实作答。）"
    user = (
        "【本份测评报告事实】\n"
        f"{(report_facts or '').strip()}\n\n"
        "【解读方法（知识库补充，非事实）】\n"
        f"{rag}\n\n"
        "【用户问题】\n"
        f"{(user_text or '').strip()}"
    )
    return [
        {"role": "system", "content": GROUNDED_SYSTEM},
        {"role": "user", "content": user},
    ]


async def compose_kb_query(
    db: Session,
    row: TalentAssessment,
    user_text: str,
) -> dict[str, Any]:
    """按需 call get_report_content；通用问答只返回原问。"""
    q = (user_text or "").strip()
    if not needs_report_context(q):
        return {
            "query": q,
            "used_report": False,
            "report_tool": None,
            "section": None,
        }

    from app.harness.context import ToolContext
    from app.harness.runtime import call_tool
    import app.harness.tools.get_report_content  # noqa: F401 — 注册工具

    section = pick_report_section(q)
    ctx = ToolContext(
        db=db,
        actor_user_id=row.child_user_id,
        child_user_id=row.child_user_id,
        profile="report_talent",
        extra={"assessment_id": row.id},
    )
    result = await call_tool(
        "get_report_content",
        {"assessment_id": int(row.id), "section": section},
        profile="report_talent",
        ctx=ctx,
    )
    data = result.data if result.ok else {}
    summary = str(data.get("content") or "").strip()
    if not summary:
        # 工具失败时退回本地切片，避免整轮无报告上下文
        from app.services.report_talent_context import build_report_context

        report = row.report_json if isinstance(row.report_json, dict) else {}
        summary = build_report_context(report, getattr(row, "talent_primary", None))
    if not summary:
        return {
            "query": q,
            "used_report": False,
            "report_tool": {
                "ok": bool(result.ok),
                "error": result.error or data.get("error"),
            },
            "section": section,
        }
    return {
        "query": _wrap_with_report(summary, q),
        "summary": summary,
        "used_report": True,
        "report_tool": {
            "ok": True,
            "section": data.get("section") or section,
            "assessment_id": row.id,
        },
        "section": section,
    }


async def prepare_grounded_turn(
    db: Session,
    row: TalentAssessment,
    user_text: str,
) -> dict[str, Any]:
    """报告事实 + talent_doc RAG 方法 → 本地模型流式；不用 knowledge_qa 直答。"""
    composed = await compose_kb_query(db, row, user_text)
    summary = str(composed.get("summary") or "").strip()
    if not composed.get("used_report") or not summary:
        return {
            **composed,
            "mode": "kb_qa",
            "messages": None,
            "rag_tool": None,
        }

    from app.harness.context import ToolContext
    from app.harness.runtime import call_tool
    import app.harness.tools.talent_doc_rag  # noqa: F401

    ctx = ToolContext(
        db=db,
        actor_user_id=row.child_user_id,
        child_user_id=row.child_user_id,
        profile="report_talent",
        extra={"assessment_id": row.id},
    )
    rag_result = await call_tool(
        "talent_doc_retrieve",
        {"query": (user_text or "").strip(), "top_n": 3},
        profile="report_talent",
        ctx=ctx,
    )
    rag_data = rag_result.data if rag_result.ok else {}
    hits = rag_data.get("hits") if isinstance(rag_data.get("hits"), list) else []
    chunks: list[str] = []
    for h in hits[:3]:
        if not isinstance(h, dict):
            continue
        text = str(h.get("text") or "").strip()
        if text:
            chunks.append(text[:500])
    rag_block = "\n---\n".join(chunks)
    messages = build_grounded_messages(
        report_facts=summary,
        rag_method=rag_block,
        user_text=user_text,
    )
    return {
        **composed,
        "mode": "grounded",
        "messages": messages,
        "rag_tool": {
            "ok": bool(rag_result.ok),
            "name": "talent_doc_retrieve",
            "hit_count": len(chunks),
            "error": rag_result.error or rag_data.get("error"),
        },
    }
