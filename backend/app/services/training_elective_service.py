"""v2.0 选修技能管理 — 弹窗触发 + 不阻塞打卡"""

from __future__ import annotations

from typing import TYPE_CHECKING

from config.loader import load_training_curriculum

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def get_elective_offers(
    planned_minutes: int,
    overall_tier: int = 1,
) -> list[dict]:
    """根据训练时长和整体 Tier 返回可用的选修技能列表。

    Returns:
        [{ skill, available, reason, has_checkin, blocks_next }]
    """
    cur = load_training_curriculum()
    elective_rules = cur.get("elective_rules") or {}

    offers = []
    for skill_name, rules in elective_rules.items():
        trigger = rules.get("trigger", "manual")
        available = False
        reason = ""

        if trigger == "duration_gte_8h":
            available = planned_minutes >= 480
            if not available:
                reason = "训练时长未达8小时"
        elif trigger == "formula_slot":
            available = True
        elif trigger == "manual":
            available = True

        offers.append({
            "skill": skill_name,
            "available": available,
            "reason": reason,
            "has_checkin": rules.get("has_checkin", False),
            "blocks_next": rules.get("blocks_next", True),
            "checkin_fields": rules.get("checkin_fields", []),
            "display_order": rules.get("display_order", "after_required"),
        })

    return offers


def submit_elective_checkin(
    db: Session,
    child_user_id: int,
    plan_id: int,
    skill: str,
    cards: list[dict] | None = None,
) -> dict:
    """提交选修打卡（仅多元感知支持打卡）。"""
    from app.db.models import TrainingRecord, TrainingPlan
    from app.services.dev_clock import resolve_training_now
    from app.services.training_day import is_plan_globally_cutoff
    from app.services.training_service import TrainingError, invalidate_plan_cache

    plan = db.get(TrainingPlan, plan_id)
    if not plan or plan.child_user_id != child_user_id:
        raise TrainingError("训练计划不存在", 404)

    now = resolve_training_now(db, child_user_id)
    if is_plan_globally_cutoff(plan, now=now):
        raise TrainingError("训练日已于凌晨4点截止", 403)

    record = TrainingRecord(
        child_user_id=child_user_id,
        plan_id=plan_id,
        item_id=None,
        train_date=plan.plan_date,
        ability_type="elective",
        files_json=cards,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    invalidate_plan_cache(child_user_id, plan.plan_date)

    return {"record_id": record.id, "status": "ok"}
