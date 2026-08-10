"""工具：近史打卡质量按技能摘要（只读）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.training_schedule.tools import register
from app.agents.training_schedule.tools._ctx import get_request_ctx
from app.agents.training_schedule.tools.checkin_summary import build_checkin_skill_summary


@register("get_checkin_skill_summary")
def get_checkin_skill_summary(db: Session, child_user_id: int, args: dict) -> dict:
    ctx = get_request_ctx()
    days = int(args.get("days") or 14)
    return build_checkin_skill_summary(
        db,
        child_user_id,
        days=days,
        skill_tiers=ctx.skill_tiers,
        grade_band=ctx.grade_band,
    )
