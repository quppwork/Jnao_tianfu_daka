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
from app.agents.guide.strategy import resolve_strategy, strategy_to_prompt_block
from app.agents.guide.student_memory import (
    extract_from_user_message,
    fold_overflow_history,
    load_guide_memory,
    save_guide_memory,
    to_prompt_block as memory_to_prompt_block,
)
from app.agents.guide.tools.planner import (
    execute_tools,
    plan_tools,
    pick_key,
    suggest_followup_picks,
    build_grounding_hint,
    MAX_TOOL_ROUNDS,
    MAX_TOOLS_TOTAL,
    MAX_TOOLS_PER_TURN,
)
from app.agents.guide.tools.query_normalize import normalize_guide_query
from app.agents.guide.ui_blocks import build_ui_blocks
from app.agents.guide.eval_safety import scan_guide_leaks
from app.agents.guide.trace import TurnTimer, build_turn_trace, emit_guide_trace
from app.agents.guide.writes import propose_write_confirms
from app.agents.shared.handoff import resolve_reply_actions, situation_label
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
    memory_block: str = "",
    rag_block: str = "",
) -> str:
    """人设 + 当日情境 + 策略 + 长期摘要 + 对话记忆 + 可选知识库/工具结果。"""
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
    strategy_block = strategy_to_prompt_block(resolve_strategy(ctx, lt))
    if strategy_block:
        parts.extend([
            "",
            "—— 个性化策略 ——",
            strategy_block,
            "—— 策略结束 ——",
        ])
    lt_block = lt.to_prompt_block()
    if lt_block:
        parts.extend([
            "",
            "—— 长期摘要（DB）——",
            lt_block,
            "—— 长期摘要结束 ——",
        ])
    if memory_block:
        parts.extend([
            "",
            "—— 对话记忆 ——",
            memory_block,
            "—— 对话记忆结束 ——",
        ])
    if rag_block:
        parts.extend([
            "",
            "—— 知识库参考（仅作事实依据，用教练口吻转述，勿整段背诵）——",
            rag_block,
            "—— 知识库结束 ——",
            "说明：知识库只补充说明性内容；今日进度/是否已练等仍以「学生情境」和「工具查询结果」为准。",
            "需要动手时仍按人设做「先答后导」，自然导向天赋测试/今日训练/学科答疑/成长里程碑等入口（前端会出按钮）。",
        ])
    if tool_block:
        parts.extend([
            "",
            "—— 工具查询结果（只读，优先采信）——",
            tool_block,
            "—— 工具结果结束 ——",
        ])
    return "\n".join(parts)


async def _gather_rag(message: str) -> tuple[str, list[str]]:
    """完整百炼 RAG：Retrieve/Search → 切片块；失败返回空，不阻断对话。"""
    from app.services.bailian import guide_rag_query
    from app.services.guide_rag_router import should_guide_use_rag

    if not should_guide_use_rag(message):
        return "", []
    rag = await guide_rag_query(message)
    if not rag or not rag.rag_block:
        return "", []
    sources = list(rag.sources)
    logger.info(
        f"guide rag mode={rag.mode} nodes={rag.node_count} sources={sources[:3]}"
    )
    return rag.rag_block, sources


def prepare_history(history: list[dict] | None) -> list[dict]:
    return truncate_history(history or [], max_turns=HISTORY_MAX_TURNS)


def _prepare_memory_and_history(
    db: Session,
    child_user_id: int,
    message: str,
    history: list[dict] | None,
) -> tuple[list[dict], str]:
    """折叠超长历史、抽取本轮用户话、落库记忆，返回 (hist, memory_block)。"""
    mem = load_guide_memory(db, child_user_id)
    full = list(history or [])
    full, mem = fold_overflow_history(full, mem, keep=HISTORY_MAX_TURNS)
    mem = extract_from_user_message(message, mem)
    save_guide_memory(db, child_user_id, mem)
    hist = truncate_history(full, max_turns=HISTORY_MAX_TURNS)
    return hist, memory_to_prompt_block(mem)


def _meta_from_ctx(
    ctx: GuideContext,
    *,
    message: str = "",
    tools_used: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    tools = tools_used or []
    actions = resolve_reply_actions(
        situation_next=ctx.next_action,
        message=message,
        tools_used=tools,
        has_assessment=bool(ctx.has_assessment),
    )
    # R5：显式「记下」意图 → 确认卡置顶（确认前不落库）
    confirms = propose_write_confirms(message)
    if confirms:
        actions = list(confirms) + list(actions)
    return {
        "situation": ctx.situation,
        "next_action": ctx.next_action,
        "situation_label": situation_label(ctx.situation),
        "actions": actions,
        "tools_used": tools,
        "blocks": build_ui_blocks(tools),
    }


async def _gather_tools(
    db: Session,
    child_user_id: int,
    message: str,
    *,
    history: list[dict] | None = None,
    use_tools: bool = True,
) -> tuple[list[dict[str, Any]], str]:
    """多步只读 tool loop：归一后 plan_tools，再按结果 followup；末尾附 grounding 提示。"""
    if not use_tools:
        return [], ""

    hist = prepare_history(history)
    plan_msg = normalize_guide_query(message) or (message or "")
    all_audit: list[dict[str, Any]] = []
    block_parts: list[str] = []
    seen_keys: set[str] = set()

    for round_i in range(MAX_TOOL_ROUNDS):
        if len(all_audit) >= MAX_TOOLS_TOTAL:
            break

        if round_i == 0:
            picks = await plan_tools(
                plan_msg,
                history=hist,
                use_llm_fallback=True,
                prefer_native_fc=True,
            )
        else:
            picks = suggest_followup_picks(
                plan_msg,
                used_audit=all_audit,
                history=hist,
            )

        fresh: list[dict[str, Any]] = []
        for p in picks:
            k = pick_key(p)
            if k in seen_keys:
                continue
            if len(all_audit) + len(fresh) >= MAX_TOOLS_TOTAL:
                break
            if len(fresh) >= MAX_TOOLS_PER_TURN:
                break
            fresh.append(p)
        if not fresh:
            break

        audit, block = execute_tools(db, child_user_id, fresh)
        for entry, pick in zip(audit, fresh):
            entry["round"] = round_i
            seen_keys.add(pick_key(pick))
        all_audit.extend(audit)
        if block:
            block_parts.append(block)

        names = [a["name"] for a in audit]
        logger.info(
            f"guide tools uid={child_user_id} round={round_i} used={names}"
        )

        if round_i + 1 < MAX_TOOL_ROUNDS:
            nxt = suggest_followup_picks(
                plan_msg,
                used_audit=all_audit,
                history=hist,
            )
            if not any(pick_key(p) not in seen_keys for p in nxt):
                break

    text = "\n".join(block_parts) if block_parts else ""
    hint = build_grounding_hint(
        message,
        tools_used=all_audit,
        tool_block=text,
    )
    if hint:
        text = f"{text}\n{hint}".strip() if text else hint
    return all_audit, text


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

    timer = TurnTimer()
    ctx = _prepare_context(db, child_user_id)
    hist, memory_block = _prepare_memory_and_history(
        db, child_user_id, message, history
    )
    tools_used, tool_block = await _gather_tools(
        db, child_user_id, message, history=hist, use_tools=use_tools
    )
    rag_block, rag_sources = await _gather_rag(message)
    system = build_chat_system_prompt(
        db,
        child_user_id,
        tool_block=tool_block,
        memory_block=memory_block,
        rag_block=rag_block,
    )
    reply = await chat_completion(
        system_prompt=system,
        user_message=message,
        history=hist,
        max_tokens=500,
    )
    text = (reply or "").strip() or "抱歉，AI 暂时无法响应，请稍后再试。"
    leak_hits = scan_guide_leaks(text)
    if leak_hits:
        logger.warning(
            f"guide leak_suspect uid={child_user_id} hits={leak_hits}"
        )
    meta = _meta_from_ctx(ctx, message=message, tools_used=tools_used)
    if rag_sources:
        meta["rag_sources"] = rag_sources
        meta["rag_used"] = True
    emit_guide_trace(
        build_turn_trace(
            child_user_id=child_user_id,
            message=message,
            tools_used=tools_used,
            duration_ms=timer.ms(),
            situation=meta.get("situation"),
            next_action=meta.get("next_action"),
            reply=text,
            leak_hits=leak_hits,
            stream=False,
        )
    )
    return {
        "reply": text,
        **meta,
    }


async def run_chat_stream(
    db: Session,
    child_user_id: int,
    message: str,
    *,
    history: list[dict] | None = None,
    use_tools: bool = True,
) -> AsyncIterator[tuple[str, Any]]:
    """流式：先 tool-loop（含原生 FC），再 yield meta / token。

    yield ('meta', dict) | ('token', str) | ('error', str)
    """
    from app.services.doubao_client import chat_completion_stream

    timer = TurnTimer()
    ctx = _prepare_context(db, child_user_id)
    hist, memory_block = _prepare_memory_and_history(
        db, child_user_id, message, history
    )
    tools_used, tool_block = await _gather_tools(
        db, child_user_id, message, history=hist, use_tools=use_tools
    )
    rag_block, rag_sources = await _gather_rag(message)
    meta = _meta_from_ctx(ctx, message=message, tools_used=tools_used)
    if rag_sources:
        meta["rag_sources"] = rag_sources
        meta["rag_used"] = True
    yield ("meta", meta)

    system = build_chat_system_prompt(
        db,
        child_user_id,
        tool_block=tool_block,
        memory_block=memory_block,
        rag_block=rag_block,
    )
    parts: list[str] = []
    async for token in chat_completion_stream(
        system_prompt=system,
        user_message=message,
        history=hist,
        max_tokens=800,
    ):
        if token.startswith("[ERROR]"):
            emit_guide_trace(
                build_turn_trace(
                    child_user_id=child_user_id,
                    message=message,
                    tools_used=tools_used,
                    duration_ms=timer.ms(),
                    situation=meta.get("situation"),
                    next_action=meta.get("next_action"),
                    reply="".join(parts),
                    leak_hits=[],
                    stream=True,
                )
            )
            yield ("error", token)
            return
        parts.append(token)
        yield ("token", token)

    text = "".join(parts)
    leak_hits = scan_guide_leaks(text)
    if leak_hits:
        logger.warning(
            f"guide leak_suspect uid={child_user_id} hits={leak_hits}"
        )
    emit_guide_trace(
        build_turn_trace(
            child_user_id=child_user_id,
            message=message,
            tools_used=tools_used,
            duration_ms=timer.ms(),
            situation=meta.get("situation"),
            next_action=meta.get("next_action"),
            reply=text,
            leak_hits=leak_hits,
            stream=True,
        )
    )
