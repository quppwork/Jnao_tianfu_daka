"""开发者训练工具 — 多日闭环测试（仅 DEV 环境）"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import TrainingItem, TrainingPlan, TrainingRecord, TrainingWindow
from app.services.assessment_service import delete_assessment, get_latest_assessment
from app.services.training_service import (
    TrainingError,
    _get_plan_by_date,
    _plan_to_response,
    get_or_create_today_plan,
    get_progress,
    purge_today_plan_without_assessment,
)


def _delete_plan(db: Session, plan: TrainingPlan) -> None:
    db.execute(delete(TrainingRecord).where(TrainingRecord.plan_id == plan.id))
    for item in list(plan.items):
        db.delete(item)
    db.delete(plan)


def get_dev_training_status(db: Session, child_user_id: int) -> dict:
    today = date.today()
    today_plan = _get_plan_by_date(db, child_user_id, today)
    yesterday_plan = _get_plan_by_date(db, child_user_id, today - timedelta(days=1))
    plan_count = db.scalar(
        select(func.count())
        .select_from(TrainingPlan)
        .where(TrainingPlan.child_user_id == child_user_id)
    ) or 0
    record_count = db.scalar(
        select(func.count())
        .select_from(TrainingRecord)
        .where(TrainingRecord.child_user_id == child_user_id)
    ) or 0
    progress = get_progress(db, child_user_id)
    return {
        "today": today.isoformat(),
        "plan_count": plan_count,
        "record_count": record_count,
        "today_plan_id": today_plan.id if today_plan else None,
        "today_status": today_plan.status if today_plan else None,
        "today_content_index": today_plan.content_index if today_plan else None,
        "today_planned_minutes": today_plan.planned_minutes if today_plan else None,
        "today_item_count": len(today_plan.items) if today_plan else 0,
        "yesterday_status": yesterday_plan.status if yesterday_plan else None,
        "yesterday_content_index": yesterday_plan.content_index if yesterday_plan else None,
        "content_index": progress.get("content_index"),
        "talent_code": progress.get("talent_code"),
        "talent_tag": progress.get("talent_tag"),
    }


def reset_today_training(db: Session, child_user_id: int) -> dict:
    """清空今日计划、打卡、时段"""
    today = date.today()
    plan = _get_plan_by_date(db, child_user_id, today)
    deleted_plan = bool(plan)
    if plan:
        _delete_plan(db, plan)

    db.execute(
        delete(TrainingWindow).where(
            TrainingWindow.child_user_id == child_user_id,
            TrainingWindow.train_date == today,
        )
    )
    db.commit()
    return {
        "action": "reset_today",
        "deleted_plan": deleted_plan,
        "status": get_dev_training_status(db, child_user_id),
    }


def reset_all_training(db: Session, child_user_id: int) -> dict:
    """清空该用户全部训练计划与打卡（保留天赋测评）"""
    plan_ids = list(
        db.scalars(select(TrainingPlan.id).where(TrainingPlan.child_user_id == child_user_id)).all()
    )
    if plan_ids:
        db.execute(delete(TrainingRecord).where(TrainingRecord.plan_id.in_(plan_ids)))
        db.execute(delete(TrainingItem).where(TrainingItem.plan_id.in_(plan_ids)))
        db.execute(delete(TrainingPlan).where(TrainingPlan.id.in_(plan_ids)))
    db.execute(delete(TrainingRecord).where(TrainingRecord.child_user_id == child_user_id))
    db.execute(delete(TrainingWindow).where(TrainingWindow.child_user_id == child_user_id))
    db.commit()
    return {
        "action": "reset_all",
        "deleted_plans": len(plan_ids),
        "status": get_dev_training_status(db, child_user_id),
    }


def reset_talent_assessment(db: Session, child_user_id: int) -> dict:
    """开发者：清除最新天赋测评及今日训练计划"""
    latest = get_latest_assessment(db, child_user_id)
    deleted_assessment = False
    if latest:
        delete_assessment(db, latest.id, child_user_id)
        deleted_assessment = True
    else:
        purge_today_plan_without_assessment(db, child_user_id)
    reset_today_training(db, child_user_id)
    return {
        "action": "reset_talent",
        "deleted_assessment": deleted_assessment,
        "status": get_dev_training_status(db, child_user_id),
    }


def simulate_next_training_day(db: Session, child_user_id: int) -> dict:
    """
    模拟进入下一天：
    1. 今日计划标记完成并归档为「昨天」
    2. 重新生成今日计划（content_index 按昨日完成情况推进）
    """
    assessment = get_latest_assessment(db, child_user_id)
    if not assessment or not assessment.talent_code:
        raise TrainingError("请先完成天赋测评", 403)

    today = date.today()
    yesterday = today - timedelta(days=1)
    today_plan = _get_plan_by_date(db, child_user_id, today)
    prev_index = today_plan.content_index if today_plan else None

    if today_plan:
        today_plan.status = "completed"
        for item in today_plan.items:
            item.checkin_status = "done"

        old_yesterday = _get_plan_by_date(db, child_user_id, yesterday)
        if old_yesterday and old_yesterday.id != today_plan.id:
            _delete_plan(db, old_yesterday)

        today_plan.plan_date = yesterday
        db.flush()

    db.execute(
        delete(TrainingWindow).where(
            TrainingWindow.child_user_id == child_user_id,
            TrainingWindow.train_date == today,
        )
    )
    db.commit()

    new_plan = get_or_create_today_plan(db, child_user_id, today)
    return {
        "action": "next_day",
        "previous_content_index": prev_index,
        "today": new_plan,
        "status": get_dev_training_status(db, child_user_id),
    }
