"""开发者训练工具 — 多日闭环测试（仅 DEV 环境）"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import ChildUser, TrainingItem, TrainingPlan, TrainingRecord, TrainingWindow
from app.services.assessment_service import delete_assessment, get_latest_assessment, resolve_effective_talent
from app.services.child_training_state import (
    _default_state,
    get_training_progress,
    save_training_progress,
)
from app.services.dev_clock import clear_time_override, get_time_override, resolve_training_now, set_time_override
from app.services.training_day import get_training_day, plan_cutoff_at, plan_new_day_at
from app.services.training_day_settlement import settle_training_day
from app.services.training_service import (
    TrainingError,
    _detach_checkin_records_from_plan,
    _get_plan_by_date,
    _plan_to_response,
    get_progress,
    get_today_plan,
    mark_plan_media_exhausted,
    purge_today_plan_without_assessment,
)


def _delete_plan(db: Session, plan: TrainingPlan) -> None:
    _detach_checkin_records_from_plan(db, plan)
    for item in list(plan.items):
        db.delete(item)
    db.delete(plan)


def reset_training_progress(db: Session, child_user_id: int) -> dict:
    """仅重置 profile 内 training_progress（回到主线 A），不删打卡历史"""
    child = db.get(ChildUser, child_user_id)
    if not child:
        raise TrainingError("学员不存在", 404)
    save_training_progress(db, child, _default_state())
    db.commit()
    return {
        "action": "reset_progress",
        "message": "主线进度已回到 A，打卡历史与虚拟时钟不受影响",
        "status": get_dev_training_status(db, child_user_id),
    }


def get_dev_training_status(db: Session, child_user_id: int) -> dict:
    now = resolve_training_now(db, child_user_id)
    today = get_training_day(now)
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
    child = db.get(ChildUser, child_user_id)
    tp = get_training_progress(child) if child else {}
    override = get_time_override(db, child_user_id)
    return {
        "today": today.isoformat(),
        "server_now": now.isoformat(),
        "dev_time_override": override.isoformat() if override else None,
        "plan_count": plan_count,
        "record_count": record_count,
        "today_plan_id": today_plan.id if today_plan else None,
        "today_status": today_plan.status if today_plan else None,
        "today_content_index": today_plan.content_index if today_plan else None,
        "today_planned_minutes": today_plan.planned_minutes if today_plan else None,
        "today_item_count": len(today_plan.items) if today_plan else 0,
        "yesterday_plan_id": yesterday_plan.id if yesterday_plan else None,
        "yesterday_status": yesterday_plan.status if yesterday_plan else None,
        "yesterday_content_index": yesterday_plan.content_index if yesterday_plan else None,
        "content_index": progress.get("content_index"),
        "main_line": tp.get("main_line"),
        "main_line_sessions": tp.get("main_line_sessions"),
        "training_days": tp.get("training_days"),
        "training_day_number": int(tp.get("training_days") or 0) + 1,
        "talent_code": progress.get("talent_code"),
        "talent_tag": progress.get("talent_tag"),
    }


def reset_today_training(db: Session, child_user_id: int) -> dict:
    """仅清空当前训练日的方案与计时窗口；保留打卡历史、昨日方案与虚拟时钟"""
    now = resolve_training_now(db, child_user_id)
    today = get_training_day(now)
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
        "message": "已清空今日方案与计时窗口；历史打卡、昨日方案与虚拟时钟不受影响",
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
    child = db.get(ChildUser, child_user_id)
    if child:
        save_training_progress(db, child, _default_state())
    clear_time_override(db, child_user_id)
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


def simulate_4am_cutoff(db: Session, child_user_id: int) -> dict:
    """虚拟时钟快进到本训练日凌晨 4:00 全局截止；不移动 plan_date、不删昨日方案"""
    now = resolve_training_now(db, child_user_id)
    today = get_training_day(now)
    plan = _get_plan_by_date(db, child_user_id, today)
    if not plan:
        raise TrainingError("今日无训练方案，请先选时长并开始训练", 404)

    cutoff = plan_cutoff_at(plan.plan_date)
    set_time_override(db, child_user_id, cutoff)
    mark_plan_media_exhausted(db, plan)
    db.execute(
        delete(TrainingWindow).where(
            TrainingWindow.child_user_id == child_user_id,
            TrainingWindow.train_date == plan.plan_date,
        )
    )
    db.commit()

    plan = _get_plan_by_date(db, child_user_id, plan.plan_date)
    return {
        "action": "simulate_4am_cutoff",
        "message": f"虚拟时钟已快进到 {cutoff.strftime('%Y-%m-%d %H:%M')}（本训练日全局截止）",
        "dev_time_override": cutoff.isoformat(),
        "plan_date": plan.plan_date.isoformat() if plan else today.isoformat(),
        "today_plan": _plan_to_response(plan, now=cutoff, db=db) if plan else None,
        "status": get_dev_training_status(db, child_user_id),
    }


def simulate_next_training_day(db: Session, child_user_id: int) -> dict:
    """虚拟时钟快进到 4:05 新一天；归档当前方案，不删昨日 plan"""
    talent = resolve_effective_talent(db, child_user_id)
    if not talent or not talent.get("talent_code"):
        raise TrainingError("请先完成天赋测评或选择天赋", 403)

    now = resolve_training_now(db, child_user_id)
    today = get_training_day(now)
    today_plan = _get_plan_by_date(db, child_user_id, today)
    prev_index = today_plan.content_index if today_plan else None

    if today_plan:
        settle_training_day(db, child_user_id, today_plan.plan_date)
        db.refresh(today_plan)
        new_moment = plan_new_day_at(today_plan.plan_date)
        window_date = today_plan.plan_date
    else:
        settle_training_day(db, child_user_id, today)
        new_moment = plan_new_day_at(today)
        window_date = today

    set_time_override(db, child_user_id, new_moment)
    db.execute(
        delete(TrainingWindow).where(
            TrainingWindow.child_user_id == child_user_id,
            TrainingWindow.train_date == window_date,
        )
    )
    db.commit()

    new_today = get_training_day(new_moment)
    today_plan_resp = get_today_plan(db, child_user_id, new_today)
    return {
        "action": "next_day",
        "message": f"虚拟时钟已快进到 {new_moment.strftime('%Y-%m-%d %H:%M')}（新训练日）",
        "dev_time_override": new_moment.isoformat(),
        "previous_content_index": prev_index,
        "today": today_plan_resp,
        "status": get_dev_training_status(db, child_user_id),
    }
