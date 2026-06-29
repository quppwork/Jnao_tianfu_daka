"""训练日 4:00 结算 — 幂等归档打卡、推进进度（4:00–4:05 空窗期执行）"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ChildUser, TrainingPlan, TrainingRecord
from app.services.child_training_state import (
    apply_pending_main_line_advance,
    bump_training_completed_day,
    get_training_progress,
    save_training_progress,
)
from app.services.dev_clock import resolve_training_now
from app.services.training_day import get_training_day, is_in_day_transition
from app.services.training_service import _get_plan_by_date


def _next_training_day(plan_date: date) -> date:
    return plan_date + timedelta(days=1)


def settle_training_day(db: Session, child_user_id: int, plan_date: date) -> dict:
    """
    结算指定训练日（幂等）。

    返回字段（便于测试断言）:
      settled, already_settled, plan_date, plan_id, plan_status,
      records_stamped, training_days_bumped, pending_applied,
      main_line, next_training_day
    """
    child = db.get(ChildUser, child_user_id)
    if not child:
        return {
            "settled": False,
            "already_settled": False,
            "plan_date": plan_date.isoformat(),
            "plan_id": None,
            "plan_status": None,
            "records_stamped": 0,
            "training_days_bumped": False,
            "pending_applied": False,
            "main_line": None,
            "next_training_day": _next_training_day(plan_date).isoformat(),
            "error": "child_not_found",
        }

    state = get_training_progress(child)
    plan_key = plan_date.isoformat()
    if state.get("last_settled_plan_date") == plan_key:
        return {
            "settled": False,
            "already_settled": True,
            "plan_date": plan_key,
            "plan_id": None,
            "plan_status": None,
            "records_stamped": 0,
            "training_days_bumped": False,
            "pending_applied": False,
            "main_line": state.get("main_line"),
            "next_training_day": state.get("training_day_anchor")
            or _next_training_day(plan_date).isoformat(),
        }

    plan = _get_plan_by_date(db, child_user_id, plan_date)
    records_stamped = 0
    plan_status = None
    training_days_bumped = False
    pending_applied = False

    if plan:
        for rec in db.scalars(
            select(TrainingRecord).where(TrainingRecord.plan_id == plan.id)
        ).all():
            if rec.train_date != plan_date:
                rec.train_date = plan_date
                records_stamped += 1
            elif rec.train_date is None:
                rec.train_date = plan_date
                records_stamped += 1

        has_records = db.scalar(
            select(TrainingRecord.id)
            .where(TrainingRecord.plan_id == plan.id)
            .limit(1)
        ) is not None

        if has_records and plan.status != "completed":
            plan.status = "completed"

        plan_status = plan.status

        if plan.status == "completed":
            bump_training_completed_day(state)
            training_days_bumped = True

    pending_applied = apply_pending_main_line_advance(state)
    state["training_day_anchor"] = _next_training_day(plan_date).isoformat()
    state["last_settled_plan_date"] = plan_key
    save_training_progress(db, child, state)
    db.flush()

    return {
        "settled": True,
        "already_settled": False,
        "plan_date": plan_key,
        "plan_id": plan.id if plan else None,
        "plan_status": plan_status,
        "records_stamped": records_stamped,
        "training_days_bumped": training_days_bumped,
        "pending_applied": pending_applied,
        "main_line": state.get("main_line"),
        "next_training_day": state["training_day_anchor"],
    }


def settle_due_training_day(
    db: Session,
    child_user_id: int,
    *,
    now=None,
) -> dict | None:
    """4:00–4:05 空窗期内结算刚结束的训练日；非空窗期返回 None"""
    now = now or resolve_training_now(db, child_user_id)
    if not is_in_day_transition(now):
        return None
    ending_plan_date = get_training_day(now) - timedelta(days=1)
    return settle_training_day(db, child_user_id, ending_plan_date)
