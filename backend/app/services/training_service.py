"""今日训练业务逻辑 — 推送、打卡、时段"""

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    ContentItem,
    TrainingItem,
    TrainingPlan,
    TrainingRecord,
    TrainingWindow,
)
from app.services.assessment_service import get_latest_assessment
from app.services.oss_client import resolve_play_url


class TrainingError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _parse_time(value: str) -> time:
    parts = value.strip().split(":")
    if len(parts) < 2:
        raise TrainingError("时间格式应为 HH:MM")
    return time(int(parts[0]), int(parts[1]))


def _format_time(value: time) -> str:
    return value.strftime("%H:%M")


def get_content_series(db: Session, talent_code: int, *, skip_intro: bool = True) -> list[ContentItem]:
    rows = list(
        db.scalars(
            select(ContentItem)
            .where(ContentItem.talent_code == talent_code, ContentItem.status == 1)
            .order_by(ContentItem.lesson_sort, ContentItem.id)
        ).all()
    )
    if skip_intro:
        rows = [r for r in rows if r.lesson_sort != 0]
    return rows


def _get_plan_by_date(db: Session, child_user_id: int, plan_date: date) -> TrainingPlan | None:
    return db.scalar(
        select(TrainingPlan)
        .options(joinedload(TrainingPlan.items))
        .where(
            TrainingPlan.child_user_id == child_user_id,
            TrainingPlan.plan_date == plan_date,
        )
    )


def _compute_content_index(
    db: Session, child_user_id: int, plan_date: date, series_len: int
) -> int:
    if series_len == 0:
        return 0
    yesterday = plan_date - timedelta(days=1)
    y_plan = _get_plan_by_date(db, child_user_id, yesterday)
    if y_plan is None:
        return 0
    if y_plan.status == "completed":
        return (y_plan.content_index + 1) % series_len
    return y_plan.content_index


def _plan_to_response(plan: TrainingPlan) -> dict:
    return {
        "plan_id": plan.id,
        "plan_date": plan.plan_date,
        "status": plan.status,
        "report_text": plan.report_text,
        "content_index": plan.content_index,
        "items": [
            {
                "id": item.id,
                "sort_order": item.sort_order,
                "title": item.title,
                "audio_url": resolve_play_url(item.audio_url),
                "video_url": item.video_url,
                "duration_min": item.duration_min,
                "instructions": item.instructions,
                "checkin_status": item.checkin_status,
            }
            for item in plan.items
        ],
    }


def get_or_create_today_plan(db: Session, child_user_id: int, plan_date: date | None = None) -> dict:
    plan_date = plan_date or date.today()
    assessment = get_latest_assessment(db, child_user_id)
    if not assessment or not assessment.talent_code:
        raise TrainingError("请先完成天赋测评", 403)

    existing = _get_plan_by_date(db, child_user_id, plan_date)
    if existing:
        return _plan_to_response(existing)

    series = get_content_series(db, assessment.talent_code)
    if not series:
        raise TrainingError("暂无可用训练音频，请联系管理员导入资源", 503)

    content_index = _compute_content_index(db, child_user_id, plan_date, len(series))
    content = series[content_index]

    plan = TrainingPlan(
        child_user_id=child_user_id,
        plan_date=plan_date,
        level=assessment.talent_primary,
        report_text=f"今日音频：{content.lesson_title}",
        content_index=content_index,
        status="pending",
        generated_at=datetime.now(timezone.utc),
    )
    db.add(plan)
    db.flush()

    item = TrainingItem(
        plan_id=plan.id,
        sort_order=1,
        title=content.lesson_title,
        audio_url=content.play_url,
        video_url=content.video_url,
        duration_min=content.duration_min,
        instructions=content.instructions,
        content_item_id=content.id,
        checkin_status="pending",
    )
    db.add(item)
    db.commit()
    db.refresh(plan)
    plan = _get_plan_by_date(db, child_user_id, plan_date)
    return _plan_to_response(plan)


def submit_checkin(
    db: Session,
    child_user_id: int,
    *,
    plan_id: int,
    item_id: int | None = None,
    ability_type: str | None = None,
    time_spent: str | None = None,
    content: str | None = None,
    result: str | None = None,
    note: str | None = None,
    attitude_pct: int | None = None,
    cards: list[dict] | None = None,
) -> dict:
    plan = db.scalar(
        select(TrainingPlan)
        .options(joinedload(TrainingPlan.items))
        .where(TrainingPlan.id == plan_id)
    )
    if not plan or plan.child_user_id != child_user_id:
        raise TrainingError("训练计划不存在", 404)
    if plan.status == "completed":
        raise TrainingError("今日训练已完成打卡")

    # 顺序打卡：必须按 sort_order 完成
    sorted_items = sorted(plan.items, key=lambda x: x.sort_order)
    target_item = None
    if item_id:
        target_item = db.get(TrainingItem, item_id)
        first_pending = next((it for it in sorted_items if it.checkin_status != "done"), None)
        if first_pending and target_item and target_item.id != first_pending.id:
            raise TrainingError("请按顺序完成训练项")
    else:
        target_item = next((it for it in sorted_items if it.checkin_status != "done"), None)
    if not target_item or target_item.plan_id != plan.id:
        raise TrainingError("训练项不存在", 404)

    record = TrainingRecord(
        child_user_id=child_user_id,
        plan_id=plan.id,
        item_id=target_item.id,
        ability_type=ability_type,
        time_spent=time_spent,
        content=content,
        result=result,
        note=note,
        attitude_pct=attitude_pct,
        files_json=cards,
    )
    db.add(record)
    target_item.checkin_status = "done"

    pending = [it for it in plan.items if it.checkin_status != "done"]
    plan.status = "pending" if pending else "completed"
    db.commit()
    db.refresh(record)
    return {"record_id": record.id, "plan_status": plan.status}


def get_progress(db: Session, child_user_id: int) -> dict:
    assessment = get_latest_assessment(db, child_user_id)
    total = db.scalar(
        select(func.count())
        .select_from(TrainingRecord)
        .where(TrainingRecord.child_user_id == child_user_id)
    ) or 0
    today_plan = _get_plan_by_date(db, child_user_id, date.today())
    return {
        "total_checkins": total,
        "content_index": today_plan.content_index if today_plan else 0,
        "talent_code": assessment.talent_code if assessment else None,
        "talent_tag": assessment.talent_tag if assessment else None,
        "today_completed": bool(today_plan and today_plan.status == "completed"),
    }


def set_training_window(
    db: Session, child_user_id: int, start_time: str, end_time: str, train_date: date | None = None
) -> dict:
    train_date = train_date or date.today()
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
    return {
        "train_date": existing.train_date,
        "start_time": _format_time(existing.start_time),
        "end_time": _format_time(existing.end_time),
    }


def get_training_window(db: Session, child_user_id: int, train_date: date | None = None) -> dict | None:
    train_date = train_date or date.today()
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


def get_window_status(db: Session, child_user_id: int, now: datetime | None = None) -> dict:
    now = now or datetime.now()
    train_date = now.date()
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
    in_window = row.start_time <= current <= row.end_time
    return {
        "in_window": in_window,
        "train_date": train_date,
        "start_time": _format_time(row.start_time),
        "end_time": _format_time(row.end_time),
    }


def get_plan_by_date(db: Session, child_user_id: int, plan_date: date) -> dict | None:
    plan = _get_plan_by_date(db, child_user_id, plan_date)
    if not plan:
        return None
    return _plan_to_response(plan)


def get_checkin_history(db: Session, child_user_id: int, limit: int = 30) -> list[dict]:
    rows = db.scalars(
        select(TrainingRecord)
        .where(TrainingRecord.child_user_id == child_user_id)
        .order_by(TrainingRecord.id.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": r.id,
            "plan_id": r.plan_id,
            "item_id": r.item_id,
            "ability_type": r.ability_type,
            "content": r.content,
            "result": r.result,
            "attitude_pct": r.attitude_pct,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
