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

RAG_PRACTICE_ANSWER_HINT = (
    "本轮为练法类问题：从知识库参考提炼 1–2 条可操作方法，用教练口吻转述；"
    "禁止天赋套话（小目标/闯关/拆解目标）替代知识库内容。"
)

KB_PRIMARY_PERSONA = (
    "你是张宇老师，陪伴孩子的训练教练。用温暖简洁口吻（2-4句）。"
    "学科解题引导去学科答疑；不解释排课/晋级/Tier 规则；不编造进度。"
)

KB_POLISH_HINT = (
    "【回答优先级】下方「知识库参考」是唯一主要事实来源，必须优先转述其中内容；"
    "人设与工具结果仅作语气与情境补充，不得用策略套话覆盖或替代知识库。"
)


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
    message: str = "",
) -> str:
    """人设 + 当日情境 + 策略 + 长期摘要 + 对话记忆 + 可选知识库/工具结果。"""
    from app.services.guide_rag_query import is_guide_practice_method_question

    ctx = _prepare_context(db, child_user_id)
    has_kb = bool((rag_block or "").strip())
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
    strategy_block = strategy_to_prompt_block(
        resolve_strategy(ctx, lt, kb_context=has_kb)
    )
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
        rag_parts = [
            "",
            "—— 知识库参考（仅作事实依据，用教练口吻转述，勿整段背诵）——",
            rag_block,
            "—— 知识库结束 ——",
            "说明：知识库只补充说明性内容；今日进度/是否已练等仍以「学生情境」和「工具查询结果」为准。",
        ]
        if is_guide_practice_method_question(message):
            rag_parts.extend(["", "—— 练法回答要求 ——", RAG_PRACTICE_ANSWER_HINT, "—— 练法要求结束 ——"])
        else:
            rag_parts.append(
                "需要动手时仍按人设做「先答后导」，自然导向天赋测试/今日训练/学科答疑/成长里程碑等入口（前端会出按钮）。"
            )
        parts.extend(rag_parts)
    if tool_block:
        parts.extend([
            "",
            "—— 工具查询结果（只读，优先采信）——",
            tool_block,
            "—— 工具结果结束 ——",
        ])
    return "\n".join(parts)


def build_kb_primary_system_prompt(
    db: Session,
    child_user_id: int,
    *,
    tool_block: str = "",
    memory_block: str = "",
    rag_block: str = "",
    message: str = "",
) -> str:
    """知识库命中：KB 为主，提示词仅润色（不注入完整策略层）。"""
    from app.services.guide_rag_query import is_guide_practice_method_question

    ctx = _prepare_context(db, child_user_id)
    parts = [
        KB_PRIMARY_PERSONA,
        "",
        "—— 学生情境 ——",
        ctx.to_prompt_block(),
        "—— 情境结束 ——",
        "",
        "—— 知识库参考（优先依据，必须转述）——",
        rag_block,
        "—— 知识库结束 ——",
        KB_POLISH_HINT,
    ]
    if is_guide_practice_method_question(message):
        parts.extend(["", RAG_PRACTICE_ANSWER_HINT])
    if memory_block:
        parts.extend(["", "—— 对话记忆 ——", memory_block, "—— 对话记忆结束 ——"])
    if tool_block:
        parts.extend([
            "",
            "—— 工具查询结果（情境补充，不覆盖知识库练法）——",
            tool_block,
            "—— 工具结果结束 ——",
        ])
    return "\n".join(parts)


async def _gather_rag(message: str) -> tuple[str, list[str]]:
    """百炼 Retrieve 切片 → rag_block（主链路，BAILIAN_RAG_GENERATE=0 时）。"""
    from app.services.bailian import guide_rag_query
    from app.services.guide_rag_query import build_guide_rag_query
    from app.services.guide_rag_router import should_guide_use_rag

    if not should_guide_use_rag(message):
        return "", []
    query = build_guide_rag_query(message)
    rag = await guide_rag_query(query)
    if not rag or not rag.rag_block:
        return "", []
    sources = list(rag.sources)
    logger.info(
        "guide rag mode=%s nodes=%s query=%r sources=%s",
        rag.mode,
        rag.node_count,
        query[:80],
        sources[:3],
    )
    return rag.rag_block, sources


GUIDE_BAILIAN_INSTRUCTIONS = (
    "你是张宇老师，陪伴孩子的训练教练。"
    "根据知识库内容用温暖、简短的教练口吻回答（2-4句）。"
    "不要编造平台进度；需要动手时可提示去天赋报告、今日训练、学科答疑或成长里程碑。"
    "学科解题类问题引导去学科答疑，不要在首页讲题。"
    "不要解释排课/晋级/Tier 等内部规则。"
)


def build_guide_bailian_instructions(db: Session, child_user_id: int, *, memory_block: str = "") -> str:
    """百炼直答时注入精简版人设 + 学生情境（完整 SYSTEM_PROMPT 仍留给豆包兜底）。"""
    ctx = _prepare_context(db, child_user_id)
    parts = [GUIDE_BAILIAN_INSTRUCTIONS, "", "—— 学生情境 ——", ctx.to_prompt_block()]
    if memory_block:
        parts.extend(["", "—— 对话记忆 ——", memory_block])
    return "\n".join(parts)


async def _try_bailian_direct_reply(
    db: Session,
    child_user_id: int,
    message: str,
    *,
    memory_block: str = "",
) -> tuple[str | None, bool]:
    """百炼 file_search 直答；命中 RAG 路由且配置就绪时启用。"""
    from app.services.bailian import guide_knowledge_reply
    from app.services.bailian.config import config_ready_for_generate, load_bailian_config
    from app.services.guide_rag_router import should_guide_use_rag

    if not should_guide_use_rag(message):
        return None, False
    cfg = load_bailian_config()
    if not config_ready_for_generate(cfg):
        return None, True
    instructions = build_guide_bailian_instructions(
        db, child_user_id, memory_block=memory_block
    )
    text = await guide_knowledge_reply(message, instructions=instructions)
    if text:
        logger.info("guide bailian direct reply len=%s", len(text))
        return text.strip(), True
    return None, True


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
    reply: str = "",
) -> dict[str, Any]:
    from app.agents.shared.handoff import primary_navigate_target

    tools = tools_used or []
    actions = resolve_reply_actions(
        situation_next=ctx.next_action,
        message=message,
        tools_used=tools,
        has_assessment=bool(ctx.has_assessment),
        reply=reply,
    )
    # R5：显式「记下」意图 → 确认卡置顶（确认前不落库）
    confirms = propose_write_confirms(message)
    if confirms:
        actions = list(confirms) + list(actions)
    # 按钮意图优先：避免 reply 已导学科答疑而 next_action 仍是情境默认 train
    effective_next = primary_navigate_target(actions) or ctx.next_action
    return {
        "situation": ctx.situation,
        "next_action": effective_next,
        "situation_label": situation_label(ctx.situation),
        "actions": actions,
        "tools_used": tools,
        "blocks": build_ui_blocks(tools),
    }


async def _qa_handoff_reply(
    message: str,
    history: list[dict] | None = None,
) -> str:
    """学科题意图：豆包只做引导话术，不讲题。"""
    from app.services.doubao_client import chat_completion, is_configured

    if not is_configured():
        return "具体题目去「学科答疑」里问更合适，我可以帮你在那边讲解思路～"
    system = (
        "你是训练教练张宇老师。用户在问学科题目或作业，不要直接讲题或给答案。"
        "用一两句自然中文引导去「学科答疑」，可点下方按钮进入。"
        "不要提今日训练，不要提知识库。"
    )
    reply = await chat_completion(
        system_prompt=system,
        user_message=message,
        history=history,
        max_tokens=160,
    )
    text = (reply or "").strip()
    if "学科答疑" not in text:
        text = "具体题目去「学科答疑」里问更合适，我可以帮你在那边讲解思路～"
    return text


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


async def _minimal_guide_reply(
    message: str,
    history: list[dict] | None = None,
) -> str:
    """KB Agent 未命中时的轻量兜底（无长人设/策略）。"""
    from app.services.doubao_client import chat_completion, is_configured

    if not is_configured():
        return "我这边暂时没接上，你可以先去「今日训练」看看～"
    system = (
        "你是训练教练张宇，用简短中文回答。"
        "学科具体解题引导去「学科答疑」；需要示范引导去「今日训练」。"
    )
    reply = await chat_completion(
        system_prompt=system,
        user_message=message,
        history=history,
        max_tokens=320,
    )
    return (reply or "").strip() or "好的，有需要随时问我～"


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

    from app.agents.guide.kb_agent import guide_kb_agent_ready, run_guide_kb_turn
    from app.agents.shared.handoff import should_route_to_qa

    # 学科解题类：豆包引导 → 学科答疑按钮（不进知识库 / 不贴今日训练）
    if should_route_to_qa(message):
        text = await _qa_handoff_reply(message, history=hist)
        tools_used = [{"name": "qa_handoff", "ok": True}]
        meta = _meta_from_ctx(ctx, message=message, tools_used=tools_used, reply=text)
        meta["rag_source"] = "qa_handoff"
        leak_hits = scan_guide_leaks(text)
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
        return {"reply": text, **meta}

    if guide_kb_agent_ready():
        kb_result = await run_guide_kb_turn(
            db, child_user_id, message, history=hist, ctx=ctx
        )
        if kb_result is not None:
            text = (kb_result.get("reply") or "").strip()
            leak_hits = scan_guide_leaks(text)
            tools_used = list(kb_result.get("tools_used") or [])
            # 再对齐一次：KB 回复若指向学科答疑，按钮必须同步
            meta = _meta_from_ctx(ctx, message=message, tools_used=tools_used, reply=text)
            for k, v in kb_result.items():
                if k not in ("reply", "actions", "next_action", "situation", "situation_label", "tools_used", "blocks"):
                    meta[k] = v
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
            return {"reply": text, **meta}

        text = await _minimal_guide_reply(message, history=hist)
        meta = _meta_from_ctx(ctx, message=message, tools_used=[], reply=text)
        meta["rag_source"] = "minimal_doubao"
        leak_hits = scan_guide_leaks(text)
        emit_guide_trace(
            build_turn_trace(
                child_user_id=child_user_id,
                message=message,
                tools_used=[],
                duration_ms=timer.ms(),
                situation=meta.get("situation"),
                next_action=meta.get("next_action"),
                reply=text,
                leak_hits=leak_hits,
                stream=False,
            )
        )
        return {"reply": text, **meta}

    tools_used, tool_block = await _gather_tools(
        db, child_user_id, message, history=hist, use_tools=use_tools
    )

    from app.services.bailian.config import load_bailian_config
    from app.services.guide_rag_router import should_guide_use_rag

    cfg = load_bailian_config()
    rag_route_hit = should_guide_use_rag(message)

    bailian_reply: str | None = None
    if rag_route_hit and cfg.rag_generate:
        bailian_reply, _ = await _try_bailian_direct_reply(
            db, child_user_id, message, memory_block=memory_block
        )
    if bailian_reply:
        text = bailian_reply
        meta = _meta_from_ctx(ctx, message=message, tools_used=tools_used, reply=text)
        meta["rag_used"] = True
        meta["rag_source"] = "bailian_generate"
        leak_hits = scan_guide_leaks(text)
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
        return {"reply": text, **meta}

    if rag_route_hit and not cfg.rag_fallback_doubao:
        text = "知识库暂时不可用，请稍后再试或直接去今日训练看看。"
        meta = _meta_from_ctx(ctx, message=message, tools_used=tools_used, reply=text)
        meta["rag_used"] = True
        meta["rag_source"] = "retrieve_unavailable"
        return {"reply": text, **meta}

    rag_block, rag_sources = await _gather_rag(message) if rag_route_hit else ("", [])

    if rag_route_hit and not rag_block:
        from app.services.guide_rag_fallback import build_rag_miss_fallback

        fallback = build_rag_miss_fallback(message, ctx)
        if fallback:
            logger.info("guide rag template fallback uid=%s", child_user_id)
            meta = _meta_from_ctx(ctx, message=message, tools_used=tools_used, reply=fallback)
            meta["rag_used"] = True
            meta["rag_source"] = "template_fallback"
            emit_guide_trace(
                build_turn_trace(
                    child_user_id=child_user_id,
                    message=message,
                    tools_used=tools_used,
                    duration_ms=timer.ms(),
                    situation=meta.get("situation"),
                    next_action=meta.get("next_action"),
                    reply=fallback,
                    leak_hits=[],
                    stream=False,
                )
            )
            return {"reply": fallback, **meta}
        logger.warning("guide retrieve empty, doubao without kb chunks uid=%s", child_user_id)

    if rag_block:
        system = build_kb_primary_system_prompt(
            db,
            child_user_id,
            tool_block=tool_block,
            memory_block=memory_block,
            rag_block=rag_block,
            message=message,
        )
    else:
        system = build_chat_system_prompt(
            db,
            child_user_id,
            tool_block=tool_block,
            memory_block=memory_block,
            rag_block=rag_block,
            message=message,
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
    meta = _meta_from_ctx(ctx, message=message, tools_used=tools_used, reply=text)
    if rag_route_hit or rag_sources:
        meta["rag_used"] = True
        meta["rag_source"] = "retrieve_doubao" if rag_sources else "doubao_no_kb_chunks"
        if rag_sources:
            meta["rag_sources"] = rag_sources
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

    from app.agents.guide.kb_agent import guide_kb_agent_ready, run_guide_kb_turn
    from app.agents.shared.handoff import should_route_to_qa

    if should_route_to_qa(message):
        text = await _qa_handoff_reply(message, history=hist)
        tools_used = [{"name": "qa_handoff", "ok": True}]
        meta = _meta_from_ctx(ctx, message=message, tools_used=tools_used, reply=text)
        meta["rag_source"] = "qa_handoff"
        yield ("meta", meta)
        yield ("token", text)
        emit_guide_trace(
            build_turn_trace(
                child_user_id=child_user_id,
                message=message,
                tools_used=tools_used,
                duration_ms=timer.ms(),
                situation=meta.get("situation"),
                next_action=meta.get("next_action"),
                reply=text,
                leak_hits=scan_guide_leaks(text),
                stream=True,
            )
        )
        return

    if guide_kb_agent_ready():
        kb_result = await run_guide_kb_turn(
            db, child_user_id, message, history=hist, ctx=ctx
        )
        if kb_result is not None:
            text = (kb_result.get("reply") or "").strip()
            tools_used = list(kb_result.get("tools_used") or [])
            meta = _meta_from_ctx(ctx, message=message, tools_used=tools_used, reply=text)
            for k, v in kb_result.items():
                if k not in (
                    "reply",
                    "actions",
                    "next_action",
                    "situation",
                    "situation_label",
                    "tools_used",
                    "blocks",
                ):
                    meta[k] = v
            yield ("meta", meta)
            yield ("token", text)
            leak_hits = scan_guide_leaks(text)
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
            return

        text = await _minimal_guide_reply(message, history=hist)
        meta = _meta_from_ctx(ctx, message=message, tools_used=[], reply=text)
        meta["rag_source"] = "minimal_doubao"
        yield ("meta", meta)
        yield ("token", text)
        emit_guide_trace(
            build_turn_trace(
                child_user_id=child_user_id,
                message=message,
                tools_used=[],
                duration_ms=timer.ms(),
                situation=meta.get("situation"),
                next_action=meta.get("next_action"),
                reply=text,
                leak_hits=scan_guide_leaks(text),
                stream=True,
            )
        )
        return

    tools_used, tool_block = await _gather_tools(
        db, child_user_id, message, history=hist, use_tools=use_tools
    )

    from app.services.bailian.config import load_bailian_config
    from app.services.guide_rag_router import should_guide_use_rag

    cfg = load_bailian_config()
    rag_route_hit = should_guide_use_rag(message)

    bailian_reply: str | None = None
    if rag_route_hit and cfg.rag_generate:
        bailian_reply, _ = await _try_bailian_direct_reply(
            db, child_user_id, message, memory_block=memory_block
        )
    # 流式前先按问句意图出按钮；完整 reply 结束后再对齐一次
    meta = _meta_from_ctx(ctx, message=message, tools_used=tools_used)
    if bailian_reply or rag_route_hit:
        meta["rag_used"] = True
        if bailian_reply:
            meta["rag_source"] = "bailian_generate"
        else:
            meta["rag_source"] = "retrieve_doubao_pending"
    yield ("meta", meta)

    if bailian_reply:
        meta = _meta_from_ctx(
            ctx, message=message, tools_used=tools_used, reply=bailian_reply
        )
        meta["rag_used"] = True
        meta["rag_source"] = "bailian_generate"
        yield ("meta", meta)
        yield ("token", bailian_reply)
        leak_hits = scan_guide_leaks(bailian_reply)
        emit_guide_trace(
            build_turn_trace(
                child_user_id=child_user_id,
                message=message,
                tools_used=tools_used,
                duration_ms=timer.ms(),
                situation=meta.get("situation"),
                next_action=meta.get("next_action"),
                reply=bailian_reply,
                leak_hits=leak_hits,
                stream=True,
            )
        )
        return

    if rag_route_hit and not cfg.rag_fallback_doubao:
        yield ("token", "知识库暂时不可用，请稍后再试。")
        return

    rag_block, rag_sources = await _gather_rag(message) if rag_route_hit else ("", [])
    if rag_route_hit and not rag_block:
        from app.services.guide_rag_fallback import build_rag_miss_fallback

        fallback = build_rag_miss_fallback(message, ctx)
        if fallback:
            meta = _meta_from_ctx(
                ctx, message=message, tools_used=tools_used, reply=fallback
            )
            meta["rag_source"] = "template_fallback"
            meta["rag_used"] = True
            yield ("meta", meta)
            yield ("token", fallback)
            emit_guide_trace(
                build_turn_trace(
                    child_user_id=child_user_id,
                    message=message,
                    tools_used=tools_used,
                    duration_ms=timer.ms(),
                    situation=meta.get("situation"),
                    next_action=meta.get("next_action"),
                    reply=fallback,
                    leak_hits=[],
                    stream=True,
                )
            )
            return
        logger.warning("guide retrieve empty stream, doubao without kb uid=%s", child_user_id)

    if rag_block:
        system = build_kb_primary_system_prompt(
            db,
            child_user_id,
            tool_block=tool_block,
            memory_block=memory_block,
            rag_block=rag_block,
            message=message,
        )
    else:
        system = build_chat_system_prompt(
            db,
            child_user_id,
            tool_block=tool_block,
            memory_block=memory_block,
            rag_block=rag_block,
            message=message,
        )
    if rag_route_hit:
        meta["rag_source"] = "retrieve_doubao" if rag_sources else "doubao_no_kb_chunks"
    if rag_sources:
        meta["rag_sources"] = rag_sources
        meta["rag_used"] = True
    if rag_route_hit or rag_sources:
        yield ("meta", meta)

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
    # 完整回复后再对齐按钮（解决「文案学科答疑、按钮今日训练」）
    aligned = _meta_from_ctx(ctx, message=message, tools_used=tools_used, reply=text)
    meta["actions"] = aligned.get("actions") or meta.get("actions") or []
    meta["next_action"] = aligned.get("next_action") or meta.get("next_action")
    yield ("meta", meta)
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
