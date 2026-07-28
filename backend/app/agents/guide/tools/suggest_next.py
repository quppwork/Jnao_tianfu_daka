"""工具：建议下一步（只读，复用 situation 判定）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.guide.tools import register


@register("suggest_next_action")
def suggest_next_action(db: Session, child_user_id: int, args: dict) -> dict:
    _ = args
    from app.agents.guide.context import build_guide_context
    from app.agents.guide.situations import apply_situation
    from app.agents.shared.handoff import situation_label

    ctx = apply_situation(build_guide_context(db, child_user_id))
    return {
        "situation": ctx.situation,
        "next_action": ctx.next_action,
        "situation_label": situation_label(ctx.situation),
    }
