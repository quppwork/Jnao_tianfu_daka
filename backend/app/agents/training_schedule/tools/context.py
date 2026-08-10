"""工具：排课上下文（只读，加厚基础信息 + 节奏摘要）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.training_schedule.tools import register
from app.agents.training_schedule.tools._ctx import get_request_ctx
from app.agents.training_schedule.tools.checkin_summary import build_rhythm_summary


@register("get_schedule_context")
def get_schedule_context(db: Session, child_user_id: int, args: dict) -> dict:
    _ = args
    ctx = get_request_ctx()
    rhythm = build_rhythm_summary(db, child_user_id, lookback_days=14)
    return {
        "planned_minutes": ctx.planned_minutes,
        "slot_budget": ctx.target_slot_count,
        "overall_tier": ctx.overall_tier,
        "grade": ctx.grade or "",
        "grade_band": ctx.grade_band,
        "talent_tag": ctx.talent_tag or "未知",
        "talent_code": ctx.talent_code,
        "training_days": ctx.training_days,
        "skill_tiers": dict(ctx.skill_tiers),
        "checkin_streak_days": rhythm.get("checkin_streak_days"),
        "days_since_last_checkin": rhythm.get("days_since_last_checkin"),
        "avg_completion_ratio": rhythm.get("avg_completion_ratio"),
        "hint": "按画像排序；slot_budget 为软提示；勿抄标准方案名单；勿解释晋级条件",
    }
