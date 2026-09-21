"""今日训练只读快照。讨论区用来决定要不要引导，不生成方案。"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

log = logging.getLogger(__name__)


def today_training(db: Session, user_id: int) -> dict:
    """看今天的训练块做完没有。查不到就当作还没练，好引导。"""
    try:
        from app.db.models import TrainingPlan
        from app.services.dev_clock import resolve_training_now
        from app.services.training_day import get_training_day

        day = get_training_day(resolve_training_now(db, user_id))
        plan = db.scalar(
            select(TrainingPlan)
            .options(selectinload(TrainingPlan.items))
            .where(
                TrainingPlan.child_user_id == user_id,
                TrainingPlan.plan_date == day,
            )
        )
    except Exception:
        log.exception("今日训练快照读失败")
        return {"done": False, "known": False, "started": False}
    if plan is None:
        return {"done": False, "known": True, "started": False, "done_count": 0, "item_count": 0}
    items = list(plan.items or [])
    done_count = sum(1 for item in items if (item.checkin_status or "") == "done")
    return {
        "done": plan.status == "completed",
        "known": True,
        "started": plan.status == "completed" or done_count > 0,
        "done_count": done_count,
        "item_count": len(items),
    }
