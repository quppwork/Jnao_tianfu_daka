"""进页开场编排 — sense → decide → speak。"""

from __future__ import annotations

import asyncio
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.agents.guide.context import GuideContext, build_guide_context
from app.agents.guide.long_term import build_daily_snapshot, build_long_term_summary
from app.agents.guide.memory import get_cached_welcome, set_cached_welcome
from app.agents.guide.persona import BOOTSTRAP_SYSTEM
from app.agents.guide.situations import apply_situation, template_welcome
from app.core.logger import get_logger

logger = get_logger("guide.bootstrap")

Source = Literal["template", "llm", "cache"]

LLM_TIMEOUT_SEC = 4.0


async def run_bootstrap(
    db: Session,
    child_user_id: int,
    *,
    force: bool = False,
    use_llm: bool = True,
) -> dict[str, Any]:
    """运行开场流水线，返回 bootstrap 载荷。"""
    ctx = build_guide_context(db, child_user_id)
    ctx = apply_situation(ctx)
    assert ctx.situation and ctx.next_action

    long_term = build_long_term_summary(
        db, child_user_id, training_day=ctx.training_day
    )

    if not force:
        cached = get_cached_welcome(db, child_user_id, ctx.training_day)
        if cached and cached.get("welcome"):
            from app.agents.shared.handoff import actions_for_next, situation_label

            sit = cached.get("situation") or ctx.situation
            nxt = cached.get("next_action") or ctx.next_action
            return {
                "training_day": ctx.training_day,
                "situation": sit,
                "next_action": nxt,
                "situation_label": situation_label(sit),
                "welcome": cached["welcome"],
                "actions": actions_for_next(nxt),
                "context_summary": ctx.to_dict(),
                "snapshot": cached.get("snapshot") or {},
                "source": "cache",
            }

    welcome, source = await _speak(ctx, long_term=long_term, use_llm=use_llm)
    from app.agents.shared.handoff import actions_for_next, situation_label

    snapshot = build_daily_snapshot(ctx, long_term)
    payload = {
        "training_day": ctx.training_day,
        "situation": ctx.situation,
        "next_action": ctx.next_action,
        "situation_label": situation_label(ctx.situation),
        "welcome": welcome,
        "actions": actions_for_next(ctx.next_action),
        "context_summary": ctx.to_dict(),
        "snapshot": snapshot,
        "source": source,
    }
    set_cached_welcome(db, child_user_id, ctx.training_day, {
        "situation": ctx.situation,
        "next_action": ctx.next_action,
        "welcome": welcome,
        "source": source,
        "snapshot": snapshot,
    })
    return payload


async def _speak(
    ctx: GuideContext,
    *,
    long_term,
    use_llm: bool,
) -> tuple[str, Source]:
    base = template_welcome(ctx.situation or "ready_to_train", nickname=ctx.nickname, talent=ctx.talent)
    if not use_llm:
        return base, "template"

    from app.services.doubao_client import chat_completion, is_configured

    if not is_configured():
        return base, "template"

    lt_block = long_term.to_prompt_block() if long_term else ""
    user_msg = (
        f"学生情境：\n{ctx.to_prompt_block()}\n\n"
    )
    if lt_block:
        user_msg += f"{lt_block}\n\n"
    user_msg += f"请写首页欢迎开场。建议动作入口：{ctx.next_action}"
    try:
        reply = await asyncio.wait_for(
            chat_completion(
                system_prompt=BOOTSTRAP_SYSTEM,
                user_message=user_msg,
                history=None,
                max_tokens=200,
            ),
            timeout=LLM_TIMEOUT_SEC,
        )
    except Exception as e:
        logger.warning(f"bootstrap LLM failed uid={ctx.child_user_id}: {e}")
        return base, "template"

    text = (reply or "").strip()
    if not text or text.startswith("[ERROR]"):
        return base, "template"
    return text, "llm"
