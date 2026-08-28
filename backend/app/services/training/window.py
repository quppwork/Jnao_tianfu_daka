"""训练时段窗口"""

from datetime import date, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import TrainingPlan, TrainingWindow
from app.services.training.common import (
    _format_time,
    _parse_time,
    _time_in_training_window,
    _today_for,
    _user_now,
    invalidate_plan_cache,
)

def sync_media_exhausted_from_window(db: Session, child_user_id: int, plan: TrainingPlan | None) -> bool:
    """计时窗口结束后自动标记媒体用尽"""
    if not plan or plan.media_exhausted:
        return bool(plan and plan.media_exhausted)
    now = _user_now(db, child_user_id)
    train_date = _today_for(db, child_user_id)
    row = db.scalar(
        select(TrainingWindow).where(
            TrainingWindow.child_user_id == child_user_id,
            TrainingWindow.train_date == train_date,
        )
    )
    if not row:
        return False
    if _time_in_training_window(row.start_time, row.end_time, now.time()):
        return False
    from app.services.training.service import mark_plan_media_exhausted
    return mark_plan_media_exhausted(db, plan)

def set_training_window(
    db: Session, child_user_id: int, start_time: str, end_time: str, train_date: date | None = None
) -> dict:
    train_date = train_date or _today_for(db, child_user_id)
    start = _parse_time(start_time)
    end = _parse_time(end_time)
    existing = db.scalar(
        select(TrainingWindow).where(
            TrainingWindow.child_user_id == child_user_id,
            TrainingWindow.train_date == train_date,
        )
    )
    if existing:
        existing.start_time = start
        existing.end_time = end
    else:
        existing = TrainingWindow(
            child_user_id=child_user_id,
            train_date=train_date,
            start_time=start,
            end_time=end,
        )
        db.add(existing)
    db.commit()
    db.refresh(existing)
    invalidate_plan_cache(child_user_id, train_date)
    from app.core.cache import invalidate_user_training

    invalidate_user_training(child_user_id, plan_date=train_date)
    return {
        "train_date": existing.train_date,
        "start_time": _format_time(existing.start_time),
        "end_time": _format_time(existing.end_time),
    }


def get_training_window(db: Session, child_user_id: int, train_date: date | None = None) -> dict | None:
    train_date = train_date or _today_for(db, child_user_id)
    row = db.scalar(
        select(TrainingWindow).where(
            TrainingWindow.child_user_id == child_user_id,
            TrainingWindow.train_date == train_date,
        )
    )
    if not row:
        return None
    return {
        "train_date": row.train_date,
        "start_time": _format_time(row.start_time),
        "end_time": _format_time(row.end_time),
    }


def clear_training_window(
    db: Session, child_user_id: int, train_date: date | None = None
) -> bool:
    train_date = train_date or _today_for(db, child_user_id)
    result = db.execute(
        delete(TrainingWindow).where(
            TrainingWindow.child_user_id == child_user_id,
            TrainingWindow.train_date == train_date,
        )
    )
    db.commit()
    if result.rowcount > 0:
        invalidate_plan_cache(child_user_id, train_date)
        from app.core.cache import invalidate_user_training

        invalidate_user_training(child_user_id, plan_date=train_date)
    return result.rowcount > 0


def get_window_status(db: Session, child_user_id: int, now: datetime | None = None) -> dict:
    now = now or _user_now(db, child_user_id)
    train_date = _today_for(db, child_user_id)
    row = db.scalar(
        select(TrainingWindow).where(
            TrainingWindow.child_user_id == child_user_id,
            TrainingWindow.train_date == train_date,
        )
    )
    if not row:
        return {
            "in_window": True,
            "train_date": train_date,
            "start_time": None,
            "end_time": None,
        }
    current = now.time()
    in_window = _time_in_training_window(row.start_time, row.end_time, current)
    result = {
        "in_window": in_window,
        "train_date": train_date,
        "start_time": _format_time(row.start_time),
        "end_time": _format_time(row.end_time),
    }
    if not in_window:
        from app.services.training.service import _get_plan_by_date
        plan = _get_plan_by_date(db, child_user_id, train_date)
        if plan:
            sync_media_exhausted_from_window(db, child_user_id, plan)
    return result

