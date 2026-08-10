"""工具：今日项数预算提示（软约束；非规则草案名单）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.training_schedule.tools import register
from app.agents.training_schedule.tools._ctx import get_request_ctx
from app.agents.training_schedule.tools.curriculum_map import required_slot_count


@register("get_slot_budget_hint")
def get_slot_budget_hint(db: Session, child_user_id: int, args: dict) -> dict:
    _ = db, child_user_id, args
    ctx = get_request_ctx()
    n = ctx.target_slot_count or required_slot_count(ctx.rule_slots)
    return {
        "slot_budget": n,
        "planned_minutes": ctx.planned_minutes,
        "hint": (
            f"今日建议约 {n} 个必修项（按时长档）；"
            "请按画像自主排序，勿抄标准方案名单。"
            "最终长度由服务层对齐预算。"
        ),
    }


# 兼容旧工具名（测试/旧 prompt）；语义已改为软预算
@register("get_rule_slot_hint")
def get_rule_slot_hint(db: Session, child_user_id: int, args: dict) -> dict:
    return get_slot_budget_hint(db, child_user_id, args)
