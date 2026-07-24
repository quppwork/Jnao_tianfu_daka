"""对话编排（A1/A2/B）：情境注入 + 只读 tool-loop + navigate actions。

guide_service 只负责会话落库，生成回复一律走本模块。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.orm import Session

from app.agents.guide.context import GuideContext, build_guide_context
from app.agents.guide.long_term import build_long_term_summary
from app.agents.guide.memory import truncate_history
from app.agents.guide.persona import SYSTEM_PROMPT
from app.agents.guide.situations import apply_situation
from app.agents.guide.tools.planner import execute_tools, plan_tools
from app.agents.shared.handoff import actions_for_next, situation_label
from app.core.logger import get_logger

logger = get_logger("guide.runner")

HISTORY_MAX_TURNS = 12


def _prepare_context(db: Session, child_user_id: int) -> GuideContext:
    ctx = build_guide_context(db, child_user_id)
    return apply_situation(ctx)


def build_chat_system_prompt(
    db: Session,
    child_user_id: int,
    *,
    tool_block: str = "",
) -> str:
    """人设 + 当日情境卡片 + DB 长期摘要（+ 可选工具结果）。"""
    ctx = _prepare_context(db, child_user_id)
    parts = [
        SYSTEM_PROMPT,
        "",
        "—— 学生情境（仅基于下列事实回答，勿编造）——",
        ctx.to_prompt_block(),
        "—— 情境结束 ——",
    ]
    lt = build_long_term_summary(
        db, child_user_id, training_day=ctx.training_day
    )
    lt_block = lt.to_prompt_block()
    if lt_block:
        parts.extend([
            "",
            "—— 长期摘要（DB）——",
            lt_block,
            "—— 长期摘要结束 ——",
        ])
    if tool_block:
        parts.extend([
            "",
            "—— 工具查询结果（只读，优先采信）——",
            tool_block,
            "—— 工具结果结束 ——",
        ])
    return "\n".join(parts)


def prepare_history(history: list[dict] | None) -> list[dict]:
    return truncate_history(history or [], max_turns=HISTORY_MAX_TURNS)


def _meta_from_ctx(
    ctx: GuideContext,
    *,
    tools_used: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "situation": ctx.situation,
        "next_action": ctx.next_action,
        "situation_label": situation_label(ctx.situation),
        "actions": actions_for_next(ctx.next_action),
        "tools_used": tools_used or [],
    }


async def _gather_tools(
    db: Session,
    child_user_id: int,
    message: str,
    *,
    use_tools: bool = True,
) -> tuple[list[dict[str, Any]], str]:
    if not use_tools:
        return [], ""
    picks = await plan_tools(message, use_llm_fallback=True)
    if not picks:
        return [], ""
    audit, block = execute_tools(db, child_user_id, picks)
    names = [a["name"] for a in audit]
    logger.info(
        f"guide tools uid={child_user_id} used={names}"
    )
    return audit, block


async def run_chat(
    db: Session,
    child_user_id: int,
    message: str,
    *,
    history: list[dict] | None = None,
    use_tools: bool = True,
) -> dict[str, Any]:
    """单轮回复。返回 reply + actions + tools_used。"""
    from app.services.doubao_client import chat_completion

    ctx = _prepare_context(db, child_user_id)
    tools_used, tool_block = await _gather_tools(
        db, child_user_id, message, use_tools=use_tools
    )
    system = build_chat_system_prompt(
        db, child_user_id, tool_block=tool_block
    )
    reply = await chat_completion(
        system_prompt=system,
        user_message=message,
        history=prepare_history(history),
        max_tokens=500,
    )
    text = (reply or "").strip() or "抱歉，AI 暂时无法响应，请稍后再试。"
    return {"reply": text, **_meta_from_ctx(ctx, tools_used=tools_used)}


async def run_chat_stream(
    db: Session,
    child_user_id: int,
    message: str,
    *,
    history: list[dict] | None = None,
    use_tools: bool = True,
) -> AsyncIterator[tuple[str, Any]]:
    """流式：先 tool-loop，再 yield meta / token。

    yield ('meta', dict) | ('token', str) | ('error', str)
    """
    from app.services.doubao_client import chat_completion_stream

    ctx = _prepare_context(db, child_user_id)
    tools_used, tool_block = await _gather_tools(
        db, child_user_id, message, use_tools=use_tools
    )
    yield ("meta", _meta_from_ctx(ctx, tools_used=tools_used))

    system = build_chat_system_prompt(
        db, child_user_id, tool_block=tool_block
    )
    async for token in chat_completion_stream(
        system_prompt=system,
        user_message=message,
        history=prepare_history(history),
        max_tokens=800,
    ):
        if token.startswith("[ERROR]"):
            yield ("error", token)
            return
        yield ("token", token)
