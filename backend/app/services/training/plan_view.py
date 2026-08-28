"""方案响应视图：item/plan dict、计时字段、待确认与窗口愈合"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ContentItem, TrainingItem, TrainingPlan, TrainingWindow
from app.services.content_meta import parse_item_instruction, resolve_training_item_title
from app.services.oss_stream_service import training_item_stream_path
from app.services.training.common import _today_for, _user_now
from app.services.training.media import (
    _should_hide_media,
    _watch_pct,
    is_item_video_complete,
)
from app.services.training.window import set_training_window
from app.services.training_day import (
    is_plan_day_locked,
    is_plan_globally_cutoff,
    training_day_meta,
    training_now,
    TZ,
)


def _refresh_volatile_plan_fields(
    db: Session, child_user_id: int, plan_date: date, cached: dict
) -> dict:
    """缓存命中时仍刷新计时/时钟字段，避免倒计时冻结在旧快照。"""
    from app.services.training.service import _resolve_today_plan

    now = _user_now(db, child_user_id)
    out = dict(cached)
    out.update(training_day_meta(now, plan_date=plan_date))
    plan = _resolve_today_plan(db, child_user_id, plan_date)
    if plan:
        _heal_started_plan_missing_window(db, child_user_id, plan)
        out.update(_build_timer_fields(db, child_user_id, plan, now))
        out["pending_confirm"] = _pending_confirm_flag(db, plan, out.get("timer_phase"))
    return out


def _item_to_dict(
    item: TrainingItem,
    *,
    hide_media: bool = False,
    content: ContentItem | None = None,
    child_user_id: int | None = None,
) -> dict:
    meta = parse_item_instruction(
        item.instructions if item.instructions and item.instructions.strip().startswith("{") else None
    )
    wp = item.watch_progress if isinstance(item.watch_progress, dict) else {}
    if hide_media:
        audio_url = None
        video_url = None
    else:
        from app.services.oss_client import sign_cdn_play_url, use_cdn_for_media

        if item.id and item.audio_url:
            audio_url = (
                sign_cdn_play_url(item.audio_url)
                if use_cdn_for_media()
                else training_item_stream_path(item.id, "audio")
            )
        else:
            audio_url = None
        if item.id and item.video_url:
            video_url = (
                sign_cdn_play_url(item.video_url)
                if use_cdn_for_media()
                else training_item_stream_path(item.id, "video")
            )
        else:
            video_url = None
        if child_user_id and item.id and not use_cdn_for_media():
            from app.core.media_stream_token import append_media_stream_token

            if audio_url:
                audio_url = append_media_stream_token(audio_url, item.id, child_user_id, "audio")
            if video_url:
                video_url = append_media_stream_token(video_url, item.id, child_user_id, "video")
    return {
        "id": item.id,
        "sort_order": item.sort_order,
        "title": resolve_training_item_title(item, content),
        "audio_url": audio_url,
        "video_url": video_url,
        "duration_min": item.duration_min,
        "instructions": item.instructions,
        "checkin_status": item.checkin_status,
        "block": meta.get("block"),
        "item_type": meta.get("item_type") or item.ability_type or "audio",
        "watch_progress": wp,
        "video_complete": is_item_video_complete(item),
        "media_hidden": hide_media,
    }


def _plan_session_started(db: Session, plan: TrainingPlan | None) -> bool:
    """已真正开练：完成过、打过卡、或有观看进度。不含「仅排课未确认」。"""
    if not plan:
        return False
    if plan.status == "completed":
        return True
    from app.services.training.service import _plan_has_any_checkin
    if _plan_has_any_checkin(db, plan):
        return True
    for it in plan.items:
        if _watch_pct(it) > 0:
            return True
    return False


def _pending_confirm_flag(db: Session | None, plan: TrainingPlan | None, timer_phase: str | None) -> bool:
    """已排课、未建计时窗口、未开练 → 待确认今日方案。"""
    if not plan or timer_phase != "setup":
        return False
    if plan.status == "completed":
        return False
    if not _has_plan_content(plan):
        return False
    if int(plan.planned_minutes or 0) < 20:
        return False
    if db is not None and _plan_session_started(db, plan):
        return False
    return True


def _heal_started_plan_missing_window(
    db: Session, child_user_id: int, plan: TrainingPlan | None
) -> bool:
    """旧流程已开练但没有 TrainingWindow 时补窗口，避免被新「待确认」流程踢回上锁。"""
    if not plan or not _has_plan_content(plan):
        return False
    if plan.status == "completed" or getattr(plan, "media_exhausted", 0):
        return False
    minutes = int(plan.planned_minutes or 0)
    if minutes < 20:
        return False
    now = _user_now(db, child_user_id)
    if is_plan_globally_cutoff(plan, now=now):
        return False
    today = _today_for(db, child_user_id)
    if plan.plan_date != today:
        return False
    if not _plan_session_started(db, plan):
        return False
    existing = db.scalar(
        select(TrainingWindow).where(
            TrainingWindow.child_user_id == child_user_id,
            TrainingWindow.train_date == today,
        )
    )
    if existing:
        return False
    end = now + timedelta(minutes=minutes)
    set_training_window(
        db,
        child_user_id,
        now.strftime("%H:%M:%S"),
        end.strftime("%H:%M:%S"),
        train_date=today,
    )
    return True


def _build_timer_fields(
    db: Session,
    child_user_id: int,
    plan: TrainingPlan | None,
    now: datetime,
) -> dict:
    """计时状态以 TrainingWindow + 方案为准，供前端唯一可信来源。"""
    setup = {
        "timer_phase": "setup",
        "timer_end_at": None,
        "timer_planned_seconds": None,
        "timer_remaining_seconds": None,
    }
    if not plan or not _has_plan_content(plan):
        return setup

    planned_sec_from_plan = (plan.planned_minutes or 0) * 60
    if plan.media_exhausted:
        return {
            "timer_phase": "expired",
            "timer_end_at": None,
            "timer_planned_seconds": planned_sec_from_plan or None,
            "timer_remaining_seconds": 0,
        }

    train_date = _today_for(db, child_user_id)
    row = db.scalar(
        select(TrainingWindow).where(
            TrainingWindow.child_user_id == child_user_id,
            TrainingWindow.train_date == train_date,
        )
    )
    if not row:
        return setup

    if now.tzinfo is None:
        now = now.replace(tzinfo=TZ)
    start_dt = datetime.combine(train_date, row.start_time, tzinfo=TZ)
    end_dt = datetime.combine(train_date, row.end_time, tzinfo=TZ)
    # 跨日窗口（如 22:00→06:00）：end 在 start 之前 → end 推后一天
    if row.end_time <= row.start_time and end_dt <= start_dt:
        end_dt += timedelta(days=1)
    planned_sec = max(0, int((end_dt - start_dt).total_seconds()))
    remaining = max(0, int((end_dt - now).total_seconds()))

    if remaining <= 0:
        return {
            "timer_phase": "expired",
            "timer_end_at": end_dt.isoformat(),
            "timer_planned_seconds": planned_sec,
            "timer_remaining_seconds": 0,
        }
    return {
        "timer_phase": "running",
        "timer_end_at": end_dt.isoformat(),
        "timer_planned_seconds": planned_sec,
        "timer_remaining_seconds": remaining,
    }


def _plan_to_response(plan: TrainingPlan, *, now: datetime | None = None, db: Session | None = None) -> dict:
    if now is None:
        now = _user_now(db, plan.child_user_id) if db is not None else training_now()
    meta = training_day_meta(now, plan_date=plan.plan_date)
    locked = is_plan_day_locked(plan, now=now)
    globally_cutoff = is_plan_globally_cutoff(plan, now=now)
    hide_media = _should_hide_media(plan)
    content_map: dict[int, ContentItem] = {}
    main_line_key = "A"
    main_line_name = ""
    progress_main_line = "A"
    progress_main_line_name = ""
    tp: dict = {}
    o_tier = 1
    if db is not None:
        ids = [i.content_item_id for i in plan.items if i.content_item_id]
        if ids:
            for row in db.scalars(select(ContentItem).where(ContentItem.id.in_(ids))):
                content_map[row.id] = row
        from app.db.models import ChildUser
        from app.services.child_training_state import display_overall_tier, get_training_progress

        child = db.get(ChildUser, plan.child_user_id)
        tp = get_training_progress(child) if child else {}
        o_tier = display_overall_tier(db, child) if child else 1
        main_line_key = f"T{tp.get('training_days', 0)}"  # v2.0: tier-based, not main_line
        main_line_name = f"整体 Tier {o_tier}"
        progress_main_line = main_line_key
        progress_main_line_name = main_line_name
    from app.services.training.service import _training_day_for_child
    training_day = _training_day_for_child(db, plan.child_user_id) if db is not None else 1
    optional_offers: list[dict] = []
    if db is not None and plan.items:
        from app.services.training_elective_service import get_elective_offers
        # 勿用 plan.content_index：v3 虽常写入 overall_tier，壳/旧简单推送语义不同
        optional_offers = get_elective_offers(
            plan.planned_minutes or 0,
            overall_tier=o_tier,
        )
    timer_fields = _build_timer_fields(db, plan.child_user_id, plan, now) if db is not None else {
        "timer_phase": "setup",
        "timer_end_at": None,
        "timer_planned_seconds": None,
        "timer_remaining_seconds": None,
    }
    from app.services.training.service import _plan_has_any_checkin, _can_customize_plan
    has_checkin = _plan_has_any_checkin(db, plan) if db is not None else False
    plan_customized = bool(getattr(plan, "plan_customized", 0))
    can_customize = _can_customize_plan(db, plan, now=now) if db is not None else False
    return {
        "plan_id": plan.id,
        "plan_date": plan.plan_date,
        "status": plan.status,
        "report_text": plan.report_text,
        # v3 排课后存 overall_tier；建壳为 0；旧简单推送为课程序号。展示/选修请用 overall_tier 字段
        "content_index": plan.content_index,
        "main_line": main_line_key,
        "main_line_name": main_line_name,
        "progress_main_line": progress_main_line,
        "progress_main_line_name": progress_main_line_name,
        "lesson_day": training_day,
        "training_day_number": training_day,
        "planned_minutes": plan.planned_minutes,
        "media_exhausted": hide_media,
        "plan_customized": plan_customized,
        "can_customize_plan": can_customize,
        "has_checkin": has_checkin,
        "items": [
            _item_to_dict(
                item,
                hide_media=hide_media,
                content=content_map.get(item.content_item_id),
                child_user_id=plan.child_user_id,
            )
            for item in sorted(plan.items, key=lambda i: i.sort_order)
        ],
        "overall_tier": o_tier,
        "optional_offers": optional_offers,
        "day_locked": locked,
        "globally_cutoff": globally_cutoff,
        "pending_confirm": _pending_confirm_flag(db, plan, timer_fields.get("timer_phase")),
        **meta,
        **timer_fields,
    }


def _has_plan_content(plan: TrainingPlan) -> bool:
    """今日方案已生成训练项"""
    return len(plan.items) > 0


