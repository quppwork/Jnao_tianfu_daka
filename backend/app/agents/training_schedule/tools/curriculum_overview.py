"""工具：全课表 + 各阶重点（只读）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.training_schedule.tools import register
from app.agents.training_schedule.tools._ctx import get_request_ctx
from app.agents.training_schedule.tools.curriculum_map import build_curriculum_overview


@register("get_curriculum_overview")
def get_curriculum_overview(db: Session, child_user_id: int, args: dict) -> dict:
    _ = db, child_user_id, args
    ctx = get_request_ctx()
    return build_curriculum_overview(overall_tier=ctx.overall_tier)
