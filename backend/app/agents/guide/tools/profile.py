"""工具：画像与天赋（只读）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.guide.tools import register


@register("get_profile")
def get_profile(db: Session, child_user_id: int, args: dict) -> dict:
    _ = args
    from app.agents.guide.context import build_guide_context

    ctx = build_guide_context(db, child_user_id)
    return {
        "nickname": ctx.nickname or "",
        "grade": ctx.grade or "",
        "talent": ctx.talent or "",
        "has_assessment": ctx.has_assessment,
        "days_since_last_checkin": ctx.days_since_last_checkin,
    }
