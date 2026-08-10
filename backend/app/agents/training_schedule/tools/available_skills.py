"""工具：今日可排技能 + 全表参考 + 本阶重点（只读）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.training_schedule.tools import register
from app.agents.training_schedule.tools._ctx import get_request_ctx
from app.agents.training_schedule.tools.curriculum_map import build_skill_availability


@register("get_available_skills")
def get_available_skills(db: Session, child_user_id: int, args: dict) -> dict:
    _ = db, child_user_id, args
    ctx = get_request_ctx()
    return build_skill_availability(overall_tier=ctx.overall_tier)
