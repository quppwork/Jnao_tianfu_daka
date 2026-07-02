"""今日训练业务逻辑 — 推送、打卡、时段"""

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    ChildUser,
    ContentItem,
    TrainingItem,
    TrainingPlan,
    TrainingRecord,
    TrainingWindow,
)
from app.services.assessment_service import effective_talent_code, get_latest_assessment, has_valid_talent
from app.services.child_training_state import (
    bump_training_completed_day,
    get_training_progress,
    overall_tier,
    save_training_progress,
    training_day_number,
)
from app.services.content_meta import parse_item_instruction, resolve_training_item_title
from app.services.oss_client import resolve_play_url
from app.services.training_day import (
    get_training_day,
    is_plan_day_locked,
    is_plan_globally_cutoff,
    is_plan_stale,
    is_new_day_ready,
    training_day_meta,
    training_now,
    TZ,
)

WATCH_COMPLETE_PCT = 90


def _user_now(db: Session | None, child_user_id: int | None = None):
    if db is not None and child_user_id is not None:
        from app.services.dev_clock import resolve_training_now

        return resolve_training_now(db, child_user_id)
    return training_now()


def _today() -> date:
    return get_training_day()


def _today_for(db: Session | None, child_user_id: int | None = None) -> date:
    return get_training_day(_user_now(db, child_user_id))


def _sync_training_day_counter(db: Session, child_user_id: int, plan_date: date) -> None:
    """进入新训练日：昨日已完成则累计训练天数（用于显示「第几天」）"""
    child = db.get(ChildUser, child_user_id)
    if not child:
        return
    state = get_training_progress(child)
    today_str = plan_date.isoformat()
    anchor = state.get("training_day_anchor")
    if anchor == today_str:
        return
    if anchor:
        yesterday = plan_date - timedelta(days=1)
        y_plan = _get_plan_by_date(db, child_user_id, yesterday)
        if y_plan and y_plan.status == "completed":
            bump_training_completed_day(state)
    # v2.0: Tier 晋级在打卡时实时判定，不再 pending
    state["training_day_anchor"] = today_str
    save_training_progress(db, child, state)


def _training_day_for_child(db: Session, child_user_id: int) -> int:
    child = db.get(ChildUser, child_user_id)
    if not child:
        return 1
    return training_day_number(get_training_progress(child))


def _resolve_today_plan(db: Session, child_user_id: int, plan_date: date | None = None) -> TrainingPlan | None:
    """按训练日查找方案；兼容旧数据用日历日期入库的情况。"""
    plan_date = plan_date or _today_for(db, child_user_id)
    plan = _get_plan_by_date(db, child_user_id, plan_date)
    if plan and is_plan_stale(plan, now=_user_now(db, child_user_id)):
        return None
    if plan:
        return plan
    now = _user_now(db, child_user_id)
    cal = now.date()
    if plan_date != cal:
        legacy = _get_plan_by_date(db, child_user_id, cal)
        if legacy and not is_plan_stale(legacy, now=now) and is_plan_day_locked(legacy, now=now):
            return legacy
    return None


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


def get_content_series(
    db: Session,
    talent_code: int,
    *,
    series: str = "chaonaoaomi",
    prefer_skill: str | None = None,
    skip_intro: bool = True,
) -> list[ContentItem]:
    from app.services.content_meta import parse_item_meta

    rows = list(
        db.scalars(
            select(ContentItem)
            .where(ContentItem.talent_code == talent_code, ContentItem.status == 1)
            .order_by(ContentItem.lesson_sort, ContentItem.id)
        ).all()
    )
    if series:
        rows = [r for r in rows if parse_item_meta(r).get("series", "chaonaoaomi") == series]
    if prefer_skill:
        preferred = [r for r in rows if parse_item_meta(r).get("skill", "") == prefer_skill]
        others = [r for r in rows if parse_item_meta(r).get("skill", "") != prefer_skill]
        rows = preferred + others
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


def _detach_checkin_records_from_plan(db: Session, plan: TrainingPlan) -> None:
    """删除 plan 前保留打卡历史：写入 train_date 并解除关联"""
    rows = db.scalars(select(TrainingRecord).where(TrainingRecord.plan_id == plan.id)).all()
    for rec in rows:
        if not rec.train_date and plan.plan_date:
            rec.train_date = plan.plan_date
        rec.plan_id = None
        rec.item_id = None


def _delete_training_plan(db: Session, plan: TrainingPlan) -> None:
    _detach_checkin_records_from_plan(db, plan)
    for item in list(plan.items):
        db.delete(item)
    db.delete(plan)


def _plan_matches_latest_talent(plan: TrainingPlan, assessment) -> bool:
    if isinstance(assessment, dict):
        tp = assessment.get("talent_primary")
    else:
        tp = assessment.talent_primary if assessment else None
    if not tp:
        return False
    return plan.level == tp


def purge_today_plan_without_assessment(
    db: Session,
    child_user_id: int,
    *,
    plan_date: date | None = None,
) -> bool:
    """无有效天赋测评时清除今日未完成计划（重置天赋后不留脏数据）"""
    plan_date = plan_date or _today()
    plan = _get_plan_by_date(db, child_user_id, plan_date)
    if not plan or plan.status == "completed":
        return False
    _delete_training_plan(db, plan)
    db.commit()
    return True


def refresh_today_plan_if_talent_changed(
    db: Session,
    child_user_id: int,
    *,
    plan_date: date | None = None,
    assessment=None,
) -> bool:
    """天赋变更或无天赋时清除今日未完成计划，以便按最新天赋重建"""
    plan_date = plan_date or _today()
    if assessment is None:
        assessment = get_latest_assessment(db, child_user_id)
    plan = _get_plan_by_date(db, child_user_id, plan_date)
    if not plan or plan.status == "completed":
        return False
    # 支持 dict (自选天赋) 和 TalentAssessment 两种输入
    talent_code = None
    if isinstance(assessment, dict):
        talent_code = assessment.get("talent_code")
    else:
        talent_code = effective_talent_code(assessment)
    if talent_code is None:
        _delete_training_plan(db, plan)
        db.commit()
        return True
    if _plan_matches_latest_talent(plan, assessment):
        return False
    _delete_training_plan(db, plan)
    db.commit()
    return True


def sync_pending_plan_content(
    db: Session,
    child_user_id: int,
    assessment,
    *,
    plan_date: date | None = None,
) -> bool:
    """天赋未变时同步今日方案：推进 content_index、更新推送音频与 level"""
    tc = _talent_attr(assessment, "talent_code")
    if not assessment or not tc:
        return False
    plan_date = plan_date or _today()
    plan = _get_plan_by_date(db, child_user_id, plan_date)
    if not plan or plan.status == "completed":
        return False
    if not _plan_matches_latest_talent(plan, assessment):
        return False

    talent_code = _talent_attr(assessment, "talent_code")
    talent_primary = _talent_attr(assessment, "talent_primary") or ""
    series = get_content_series(db, talent_code, prefer_skill="影像追忆")
    if not series:
        return False

    content_index = _compute_content_index(
        db, child_user_id, plan_date, len(series), talent_primary=talent_primary
    )
    content = series[content_index]
    changed = False

    if plan.content_index != content_index:
        plan.content_index = content_index
        changed = True
    if plan.level != talent_primary:
        plan.level = talent_primary
        changed = True

    # 仅同步「简单推送」单条音频计划；已排课的 A/B 方案保留结构
    is_simple = len(plan.items) <= 1 and not plan.planned_minutes
    if not is_simple:
        if changed:
            db.commit()
        return changed

    if not plan.items:
        return changed

    item = plan.items[0]
    if (
        item.content_item_id != content.id
        or item.title != content.lesson_title
        or item.audio_url != content.play_url
    ):
        item.title = content.lesson_title
        item.audio_url = content.play_url
        item.video_url = content.video_url
        item.duration_min = content.duration_min
        item.instructions = content.instructions
        item.content_item_id = content.id
        if item.checkin_status == "pending":
            plan.report_text = f"今日音频：{content.lesson_title}"
        changed = True

    if changed:
        db.commit()
    return changed


def _resolve_effective_talent(db: Session, child_user_id: int) -> dict | None:
    from app.services.assessment_service import resolve_effective_talent

    return resolve_effective_talent(db, child_user_id)


def ensure_assessment_for_training(db: Session, child_user_id: int):
    """进入训练前优先校验最新天赋测评（含自选天赋）"""
    talent = _resolve_effective_talent(db, child_user_id)
    if not talent:
        purge_today_plan_without_assessment(db, child_user_id)
        raise TrainingError("请先完成天赋测评", 403)
    return talent


def get_training_entry(db: Session, child_user_id: int) -> dict:
    """训练页入口：优先检查最新天赋，并同步今日方案"""
    talent = _resolve_effective_talent(db, child_user_id)
    if not talent:
        purge_today_plan_without_assessment(db, child_user_id)
        return {
            "has_assessment": False,
            "needs_assessment": True,
            "message": "需要先进行天赋测试才能帮你安排今日训练",
            "assessment_id": None,
            "talent_primary": None,
            "talent_tag": None,
            "talent_code": None,
        }

    refresh_today_plan_if_talent_changed(db, child_user_id, assessment=talent)
    # sync_pending_plan_content needs an actual assessment row; skip for onboarding
    if talent.get("talent_source") != "onboarding":
        assessment_row = get_latest_assessment(db, child_user_id)
        if assessment_row:
            sync_pending_plan_content(db, child_user_id, assessment_row)
    progress = get_progress(db, child_user_id)
    now = _user_now(db, child_user_id)
    today_plan = _resolve_today_plan(db, child_user_id, get_training_day(now))
    meta = training_day_meta(now)
    day_locked = is_plan_day_locked(today_plan, now=now) if today_plan else False
    profile = {}
    user = db.get(ChildUser, child_user_id)
    if user and user.profile_json:
        profile = dict(user.profile_json)
    onboarding = profile.get("onboarding") if isinstance(profile.get("onboarding"), dict) else {}
    return {
        "has_assessment": True,
        "needs_assessment": False,
        "message": None,
        "assessment_id": talent.get("assessment_id"),
        "talent_primary": talent.get("talent_primary"),
        "talent_tag": talent.get("talent_tag"),
        "talent_code": talent.get("talent_code"),
        "talent_source": talent.get("talent_source"),
        "talent_conflict": bool(profile.get("pending_talent")),
        "pending_talent": profile.get("pending_talent"),
        "onboarding_completed": bool(onboarding.get("completed_at")),
        "day_locked": day_locked,
        **meta,
        **progress,
    }


def _compute_content_index(
    db: Session, child_user_id: int, plan_date: date, series_len: int, *, talent_primary: str | None = None
) -> int:
    if series_len == 0:
        return 0
    yesterday = plan_date - timedelta(days=1)
    y_plan = _get_plan_by_date(db, child_user_id, yesterday)
    if y_plan is None:
        return 0
    if talent_primary and y_plan.level and y_plan.level != talent_primary:
        return 0
    if y_plan.status == "completed":
        return (y_plan.content_index + 1) % series_len
    return y_plan.content_index


def _item_is_video(item: TrainingItem) -> bool:
    meta = parse_item_instruction(
        item.instructions if item.instructions and item.instructions.strip().startswith("{") else None
    )
    item_type = meta.get("item_type") or item.ability_type
    return bool(item.video_url) or item_type == "video"


def _watch_pct(item: TrainingItem) -> float:
    wp = item.watch_progress if isinstance(item.watch_progress, dict) else {}
    return float(wp.get("pct") or 0)


def is_item_video_complete(item: TrainingItem) -> bool:
    if not _item_is_video(item):
        return True
    return _watch_pct(item) >= WATCH_COMPLETE_PCT


def _should_hide_media(plan: TrainingPlan) -> bool:
    return bool(getattr(plan, "media_exhausted", 0))


def _item_to_dict(item: TrainingItem, *, hide_media: bool = False, content: ContentItem | None = None) -> dict:
    meta = parse_item_instruction(
        item.instructions if item.instructions and item.instructions.strip().startswith("{") else None
    )
    wp = item.watch_progress if isinstance(item.watch_progress, dict) else {}
    audio_url = None if hide_media else resolve_play_url(item.audio_url)
    video_url = None if hide_media else item.video_url
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
    pending_main_line_to = None
    if db is not None:
        ids = [i.content_item_id for i in plan.items if i.content_item_id]
        if ids:
            for row in db.scalars(select(ContentItem).where(ContentItem.id.in_(ids))):
                content_map[row.id] = row
        from app.db.models import ChildUser
        from app.services.child_training_state import get_training_progress, overall_tier

        child = db.get(ChildUser, plan.child_user_id)
        tp = get_training_progress(child) if child else {}
        main_line_key = f"T{tp.get('training_days', 0)}"  # v2.0: tier-based, not main_line
        main_line_name = f"整体 Tier {overall_tier(tp)}"
        progress_main_line = main_line_key
        progress_main_line_name = main_line_name
        pending_main_line_to = None  # v2.0: Tier晋级实时判定，无pending
    training_day = _training_day_for_child(db, plan.child_user_id) if db is not None else 1
    optional_offers: list[dict] = []
    if db is not None and plan.items:
        from app.services.training_optional_service import get_optional_offers_for_child

        optional_offers = get_optional_offers_for_child(db, plan.child_user_id, plan)
    timer_fields = _build_timer_fields(db, plan.child_user_id, plan, now) if db is not None else {
        "timer_phase": "setup",
        "timer_end_at": None,
        "timer_planned_seconds": None,
        "timer_remaining_seconds": None,
    }
    return {
        "plan_id": plan.id,
        "plan_date": plan.plan_date,
        "status": plan.status,
        "report_text": plan.report_text,
        "content_index": plan.content_index,
        "main_line": main_line_key,
        "main_line_name": main_line_name,
        "progress_main_line": progress_main_line,
        "progress_main_line_name": progress_main_line_name,
        "pending_main_line_to": pending_main_line_to,
        "lesson_day": training_day,
        "training_day_number": training_day,
        "planned_minutes": plan.planned_minutes,
        "media_exhausted": hide_media,
        "items": [
            _item_to_dict(item, hide_media=hide_media, content=content_map.get(item.content_item_id))
            for item in sorted(plan.items, key=lambda i: i.sort_order)
        ],
        "overall_tier": overall_tier(tp) if tp else 1,  # 🆕 v2.0
        "optional_offers": optional_offers,
        "day_locked": locked,
        "globally_cutoff": globally_cutoff,
        **meta,
        **timer_fields,
    }


def _has_plan_content(plan: TrainingPlan) -> bool:
    """今日方案已生成训练项"""
    return len(plan.items) > 0


def mark_plan_media_exhausted(db: Session, plan: TrainingPlan) -> bool:
    """设定时长用尽：不再提供音视频，仍可打卡至训练日截止"""
    if not plan or plan.media_exhausted:
        return bool(plan and plan.media_exhausted)
    plan.media_exhausted = 1
    db.commit()
    return True


def mark_today_media_exhausted(
    db: Session, child_user_id: int, plan_date: date | None = None
) -> dict:
    plan_date = plan_date or _today()
    plan = _get_plan_by_date(db, child_user_id, plan_date)
    if not plan:
        raise TrainingError("训练计划不存在", 404)
    if is_plan_globally_cutoff(plan):
        raise TrainingError("训练日已于凌晨4点截止", 403)
    mark_plan_media_exhausted(db, plan)
    db.refresh(plan)
    return _plan_to_response(plan, db=db)


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
    current = now.time()
    if row.start_time <= current <= row.end_time:
        return False
    return mark_plan_media_exhausted(db, plan)


def get_today_plan(db: Session, child_user_id: int, plan_date: date | None = None) -> dict:
    """获取今日方案；无内容时需先 POST /schedule 选时长生成"""
    from app.services.training_schedule_service import ensure_today_plan_shell

    plan_date = plan_date or _today_for(db, child_user_id)
    if not is_new_day_ready(_user_now(db, child_user_id)):
        raise TrainingError("训练日切换中，请约 5 分钟后再试", 503)

    talent = _resolve_effective_talent(db, child_user_id)
    if not talent:
        raise TrainingError("请先完成天赋测评", 403)

    # 获取实际 assessment 行（可能为 None，自选天赋场景）
    assessment = get_latest_assessment(db, child_user_id)
    refresh_today_plan_if_talent_changed(db, child_user_id, plan_date=plan_date, assessment=talent)

    ensure_today_plan_shell(db, child_user_id, plan_date)
    if assessment:
        sync_pending_plan_content(db, child_user_id, assessment, plan_date=plan_date)
    plan = _resolve_today_plan(db, child_user_id, plan_date)
    if plan:
        from app.services.training_catalog_sync import ensure_supplementary_catalogs, repair_plan_media_items
        from app.services.training_child_guide import build_coach_text_for_plan, is_technical_schedule_note

        ensure_supplementary_catalogs(db)
        talent_code = talent.get("talent_code") if talent else None
        if repair_plan_media_items(db, plan, talent_code):
            db.commit()
            plan = _resolve_today_plan(db, child_user_id, plan_date)
        if plan and plan.items and is_technical_schedule_note(plan.report_text):
            plan.report_text = build_coach_text_for_plan(plan)
            db.commit()
        sync_media_exhausted_from_window(db, child_user_id, plan)
        plan = _resolve_today_plan(db, child_user_id, plan_date)
        return _plan_to_response(plan, db=db)

    return empty_today_plan_response(db, child_user_id, plan_date)


def _talent_attr(assessment, key: str, default=None):
    """兼容 dict 和 ORM 对象取天赋属性"""
    if isinstance(assessment, dict):
        return assessment.get(key, default)
    return getattr(assessment, key, default)


def _preview_content_index(db: Session, child_user_id: int, plan_date: date, assessment) -> int:
    tc = _talent_attr(assessment, "talent_code")
    tp = _talent_attr(assessment, "talent_primary")
    if not tc:
        return 0
    series = get_content_series(db, tc, prefer_skill="影像追忆")
    if not series:
        return 0
    return _compute_content_index(
        db, child_user_id, plan_date, len(series), talent_primary=tp
    )


def empty_today_plan_response(
    db: Session,
    child_user_id: int,
    plan_date: date | None = None,
    *,
    now: datetime | None = None,
) -> dict:
    """无今日方案时的占位（如日切窗口）"""
    now = now or _user_now(db, child_user_id)
    plan_date = plan_date or get_training_day(now)
    assessment = get_latest_assessment(db, child_user_id)
    meta = training_day_meta(now, plan_date=plan_date)
    return {
        "plan_id": 0,
        "plan_date": plan_date,
        "status": "none",
        "report_text": "",
        "content_index": _preview_content_index(db, child_user_id, plan_date, assessment),
        "planned_minutes": None,
        "items": [],
        "day_locked": False,
        "globally_cutoff": False,
        "timer_phase": "setup",
        "timer_end_at": None,
        "timer_planned_seconds": None,
        "timer_remaining_seconds": None,
        **meta,
    }


def create_plan_for_schedule(db: Session, child_user_id: int, plan_date: date | None = None) -> TrainingPlan:
    """创建当日方案记录（内容由 ensure_today_plan_content 填充）"""
    plan_date = plan_date or _today_for(db, child_user_id)
    if not is_new_day_ready(_user_now(db, child_user_id)):
        raise TrainingError("训练日切换中，请约 5 分钟后再试", 503)

    assessment = ensure_assessment_for_training(db, child_user_id)
    refresh_today_plan_if_talent_changed(db, child_user_id, plan_date=plan_date, assessment=assessment)

    plan = _resolve_today_plan(db, child_user_id, plan_date)
    if plan:
        return plan

    content_index = _preview_content_index(db, child_user_id, plan_date, assessment)
    talent_primary = _talent_attr(assessment, "talent_primary") or ""
    plan = TrainingPlan(
        child_user_id=child_user_id,
        plan_date=plan_date,
        level=talent_primary,
        report_text="",
        content_index=content_index,
        status="pending",
        generated_at=datetime.now(timezone.utc),
    )
    db.add(plan)
    _sync_training_day_counter(db, child_user_id, plan_date)
    db.commit()
    db.refresh(plan)
    return _get_plan_by_date(db, child_user_id, plan_date)


def get_or_create_today_plan(db: Session, child_user_id: int, plan_date: date | None = None) -> dict:
    plan_date = plan_date or _today_for(db, child_user_id)
    if not is_new_day_ready(_user_now(db, child_user_id)):
        raise TrainingError("训练日切换中，请约 5 分钟后再试", 503)
    assessment = ensure_assessment_for_training(db, child_user_id)

    refresh_today_plan_if_talent_changed(db, child_user_id, plan_date=plan_date, assessment=assessment)

    existing = _resolve_today_plan(db, child_user_id, plan_date)
    if existing:
        sync_pending_plan_content(db, child_user_id, assessment, plan_date=plan_date)
        existing = _resolve_today_plan(db, child_user_id, plan_date)
        return _plan_to_response(existing, db=db)

    talent_code = _talent_attr(assessment, "talent_code")
    talent_primary = _talent_attr(assessment, "talent_primary") or ""
    series = get_content_series(db, talent_code, prefer_skill="影像追忆")
    if not series:
        raise TrainingError("暂无可用训练音频，请联系管理员导入资源", 503)

    content_index = _compute_content_index(
        db, child_user_id, plan_date, len(series), talent_primary=talent_primary
    )
    content = series[content_index]

    plan = TrainingPlan(
        child_user_id=child_user_id,
        plan_date=plan_date,
        level=talent_primary,
        report_text=f"今日音频：{content.lesson_title}",
        content_index=content_index,
        status="pending",
        generated_at=datetime.now(timezone.utc),
    )
    db.add(plan)
    _sync_training_day_counter(db, child_user_id, plan_date)
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
    return _plan_to_response(plan, db=db)


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
    now = _user_now(db, child_user_id)
    if is_plan_globally_cutoff(plan, now=now):
        raise TrainingError("训练日已于凌晨4点截止", 403)

    sorted_items = sorted(plan.items, key=lambda x: x.sort_order)

    # 顺序打卡：必须按 sort_order 完成
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

    target_block = parse_item_instruction(target_item.instructions).get("block")

    ability_type, time_spent, content, result, note = _apply_card_fields_to_record(
        cards=cards,
        ability_type=ability_type,
        time_spent=time_spent,
        content=content,
        result=result,
        note=note,
    )

    record = TrainingRecord(
        child_user_id=child_user_id,
        plan_id=plan.id,
        item_id=target_item.id,
        train_date=plan.plan_date,
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

    # 同 block 内所有 pending 项一并标记完成（前端一次打卡覆盖整个 block）
    if target_block:
        for it in plan.items:
            it_block = parse_item_instruction(it.instructions).get("block")
            if it_block == target_block and it.checkin_status == "pending":
                it.checkin_status = "done"

    from app.services.training_carryover import auto_complete_skipped_checkin_items

    auto_complete_skipped_checkin_items(plan)

    pending = [it for it in plan.items if it.checkin_status != "done"]
    plan.status = "pending" if pending else "completed"

    progress_delta = None
    if cards:
        from app.db.models import ChildUser

        child = db.get(ChildUser, child_user_id)
        talent = _resolve_effective_talent(db, child_user_id)
        talent_code = talent.get("talent_code") if talent else None
        if child and talent_code:
            from app.services.training_mastery import process_checkin_progress
            from app.services.child_training_state import child_grade

            progress_delta = process_checkin_progress(
                db,
                child,
                plan,
                cards,
                talent_code=talent_code,
                grade=child_grade(child),
            )
            if progress_delta and not progress_delta.get("main_line_advanced"):
                plan.content_index = progress_delta.get("content_index", plan.content_index)

    db.commit()
    db.refresh(record)
    out = {"record_id": record.id, "plan_status": plan.status}
    if progress_delta:
        out["training_progress"] = progress_delta
    return out


def _card_summary(c: dict) -> str:
    name = c.get("name") or ""
    if name == "极速运算":
        return (
            f"{name}({c.get('tag') or '运算'},{c.get('time') or '?'}分钟,"
            f"{c.get('count') or '?'}题,{c.get('accuracy') or '?'}%)"
        )
    if name == "扫描速记":
        material = c.get("materialName") or c.get("bookName") or "?"
        return (
            f"扫描速记：用时{c.get('time') or '?'}分钟，记住{c.get('wordCount') or '?'}字"
            f"《{material}》"
        )
    if name == "超脑阅读":
        words = c.get("wordCount") or c.get("content") or "?"
        return f"超脑阅读({c.get('time') or '?'}分钟,{words}字)"
    if name == "影像追忆":
        words = c.get("wordCount") or c.get("content") or "?"
        return f"影像追忆({c.get('time') or '?'}分钟,{words}字)"
    return f"{name}({c.get('time') or '?'}分钟)"


def _summarize_time_spent(cards: list[dict]) -> str | None:
    parts: list[str] = []
    total = 0.0
    for c in cards or []:
        t = c.get("time")
        if t is None or t == "":
            continue
        try:
            mins = float(t)
        except (TypeError, ValueError):
            continue
        if mins <= 0:
            continue
        total += mins
        name = c.get("name") or "训练"
        parts.append(f"{name}{mins:g}分钟")
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return f"合计{total:g}分钟（{'、'.join(parts)}）"


def _summarize_results(cards: list[dict]) -> str | None:
    parts = [str(c.get("result")).strip() for c in cards or [] if c.get("result")]
    return "；".join(parts) if parts else None


def _summarize_notes(cards: list[dict]) -> str | None:
    parts = [str(c.get("note")).strip() for c in cards or [] if c.get("note")]
    return "；".join(parts) if parts else None


def _apply_card_fields_to_record(
    *,
    cards: list[dict] | None,
    ability_type: str | None,
    time_spent: str | None,
    content: str | None,
    result: str | None,
    note: str | None,
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    if not cards:
        return ability_type, time_spent, content, result, note
    auto_ability, auto_content = _summarize_cards(cards)
    return (
        ability_type or auto_ability,
        time_spent or _summarize_time_spent(cards),
        content or auto_content,
        result or _summarize_results(cards),
        note or _summarize_notes(cards),
    )


def _summarize_cards(cards: list[dict]) -> tuple[str, str]:
    names = [c.get("name") for c in cards if c.get("name")]
    ability_type = "、".join(names)
    content = "；".join(_card_summary(c) for c in cards if c.get("name"))
    return ability_type, content


def _record_to_dict(record: TrainingRecord, *, plan: TrainingPlan | None = None) -> dict:
    created = record.created_at
    train_date = None
    if record.train_date:
        train_date = record.train_date.isoformat()
    elif plan and plan.plan_date:
        train_date = plan.plan_date.isoformat()
    elif created:
        train_date = created.date().isoformat()
    checkin_at = created.isoformat() if created else None
    cards = record.files_json if isinstance(record.files_json, list) else []
    phase_blocks = sorted({c.get("phaseBlock") for c in cards if c.get("phaseBlock")})
    return {
        "id": record.id,
        "plan_id": record.plan_id,
        "item_id": record.item_id,
        "train_date": train_date,
        "checkin_at": checkin_at,
        "checkin_time": created.strftime("%H:%M") if created else None,
        "ability_type": record.ability_type,
        "time_spent": record.time_spent,
        "content": record.content,
        "result": record.result,
        "note": record.note,
        "attitude_pct": record.attitude_pct,
        "phase_blocks": phase_blocks,
        "cards": cards,
        "created_at": checkin_at,
    }


def group_checkin_history_by_day(items: list[dict]) -> list[dict]:
    buckets: dict[str, list[dict]] = {}
    for item in items:
        day = item.get("train_date") or (item.get("checkin_at") or "")[:10] or "unknown"
        buckets.setdefault(day, []).append(item)
    out = []
    for d in sorted(buckets.keys(), reverse=True):
        recs = sorted(
            buckets[d],
            key=lambda x: x.get("checkin_at") or "",
            reverse=True,
        )
        out.append({"date": d, "records": recs})
    return out


def _item_block(item: TrainingItem) -> str | None:
    return parse_item_instruction(item.instructions).get("block")


def _revert_block_checkin(db: Session, plan: TrainingPlan, block: str) -> None:
    for it in plan.items:
        if _item_block(it) == block:
            it.checkin_status = "pending"


def _sync_plan_after_record_change(
    db: Session,
    plan: TrainingPlan | None,
    *,
    deleted_record: TrainingRecord | None = None,
) -> str | None:
    if not plan:
        return None
    plan = db.scalar(
        select(TrainingPlan)
        .options(joinedload(TrainingPlan.items))
        .where(TrainingPlan.id == plan.id)
    )
    if not plan:
        return None

    if deleted_record and deleted_record.item_id:
        item = db.get(TrainingItem, deleted_record.item_id)
        if item:
            block = _item_block(item)
            if block:
                _revert_block_checkin(db, plan, block)
            else:
                # 简单推送计划无 block，直接回退该 item
                item.checkin_status = "pending"

    pending = [it for it in plan.items if it.checkin_status != "done"]
    plan.status = "pending" if pending else "completed"
    return plan.status


def get_checkin_record(db: Session, child_user_id: int, record_id: int) -> dict:
    record = db.get(TrainingRecord, record_id)
    if not record or record.child_user_id != child_user_id:
        raise TrainingError("打卡记录不存在", 404)
    plan = db.get(TrainingPlan, record.plan_id) if record.plan_id else None
    return _record_to_dict(record, plan=plan)


def get_today_checkins(db: Session, child_user_id: int, plan_date: date | None = None) -> list[dict]:
    plan_date = plan_date or _today_for(db, child_user_id)
    plan = _get_plan_by_date(db, child_user_id, plan_date)
    if not plan:
        return []
    rows = db.scalars(
        select(TrainingRecord)
        .where(
            TrainingRecord.child_user_id == child_user_id,
            TrainingRecord.plan_id == plan.id,
        )
        .order_by(TrainingRecord.id.desc())
    ).all()
    return [_record_to_dict(r, plan=plan) for r in rows]


def update_checkin_record(
    db: Session,
    child_user_id: int,
    record_id: int,
    *,
    ability_type: str | None = None,
    time_spent: str | None = None,
    content: str | None = None,
    result: str | None = None,
    note: str | None = None,
    attitude_pct: int | None = None,
    cards: list[dict] | None = None,
) -> dict:
    record = db.get(TrainingRecord, record_id)
    if not record or record.child_user_id != child_user_id:
        raise TrainingError("打卡记录不存在", 404)

    plan = db.get(TrainingPlan, record.plan_id) if record.plan_id else None
    if plan and is_plan_globally_cutoff(plan):
        raise TrainingError("训练日已于凌晨4点截止，无法修改打卡", 403)

    if cards is not None:
        if not cards:
            return delete_checkin_record(db, child_user_id, record_id)
        record.files_json = cards
        auto_ability, auto_time, auto_content, auto_result, auto_note = _apply_card_fields_to_record(
            cards=cards,
            ability_type=ability_type,
            time_spent=time_spent,
            content=content,
            result=result,
            note=note,
        )
        record.ability_type = auto_ability
        record.time_spent = auto_time
        record.content = auto_content
        record.result = auto_result
        record.note = auto_note
    else:
        if ability_type is not None:
            record.ability_type = ability_type
        if content is not None:
            record.content = content

    if time_spent is not None and cards is None:
        record.time_spent = time_spent
    if result is not None and cards is None:
        record.result = result
    if note is not None and cards is None:
        record.note = note
    if attitude_pct is not None:
        record.attitude_pct = attitude_pct

    plan = db.get(TrainingPlan, record.plan_id) if record.plan_id else None
    plan_status = _sync_plan_after_record_change(db, plan)
    progress_delta = None
    if plan and cards is not None:
        from app.db.models import ChildUser
        from app.services.training_mastery import reassess_main_line_from_plan

        child = db.get(ChildUser, child_user_id)
        talent = _resolve_effective_talent(db, child_user_id)
        talent_code = talent.get("talent_code") if talent else None
        if child and talent_code:
            db.flush()
            from app.services.child_training_state import child_grade

            progress_delta = reassess_main_line_from_plan(
                db,
                child,
                plan,
                talent_code=talent_code,
                grade=child_grade(child),
            )
    db.commit()
    db.refresh(record)
    out = {"record": _record_to_dict(record, plan=plan), "plan_status": plan_status}
    if progress_delta:
        out["training_progress"] = progress_delta
    return out


def delete_checkin_record(db: Session, child_user_id: int, record_id: int) -> dict:
    record = db.get(TrainingRecord, record_id)
    if not record or record.child_user_id != child_user_id:
        raise TrainingError("打卡记录不存在", 404)

    plan = db.get(TrainingPlan, record.plan_id) if record.plan_id else None
    if plan and is_plan_globally_cutoff(plan):
        raise TrainingError("训练日已于凌晨4点截止，无法修改打卡", 403)
    db.delete(record)
    db.flush()
    plan_status = _sync_plan_after_record_change(db, plan, deleted_record=record)
    progress_delta = None
    if plan:
        from app.db.models import ChildUser
        from app.services.training_mastery import reassess_main_line_from_plan

        child = db.get(ChildUser, child_user_id)
        talent = _resolve_effective_talent(db, child_user_id)
        talent_code = talent.get("talent_code") if talent else None
        if child and talent_code:
            from app.services.child_training_state import child_grade

            progress_delta = reassess_main_line_from_plan(
                db,
                child,
                plan,
                talent_code=talent_code,
                grade=child_grade(child),
            )
    db.commit()
    out = {"deleted": True, "plan_status": plan_status}
    if progress_delta:
        out["training_progress"] = progress_delta
    return out


def get_progress(db: Session, child_user_id: int) -> dict:
    talent = _resolve_effective_talent(db, child_user_id)
    total = db.scalar(
        select(func.count())
        .select_from(TrainingRecord)
        .where(TrainingRecord.child_user_id == child_user_id)
    ) or 0
    today_plan = _resolve_today_plan(db, child_user_id, _today_for(db, child_user_id))
    return {
        "total_checkins": total,
        "content_index": today_plan.content_index if today_plan else 0,
        "talent_code": talent.get("talent_code") if talent else None,
        "talent_tag": talent.get("talent_tag") if talent else None,
        "talent_primary": talent.get("talent_primary") if talent else None,
        "assessment_id": talent.get("assessment_id") if talent else None,
        "today_completed": bool(today_plan and today_plan.status == "completed"),
    }


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
    in_window = row.start_time <= current <= row.end_time
    result = {
        "in_window": in_window,
        "train_date": train_date,
        "start_time": _format_time(row.start_time),
        "end_time": _format_time(row.end_time),
    }
    if not in_window:
        plan = _get_plan_by_date(db, child_user_id, train_date)
        if plan:
            sync_media_exhausted_from_window(db, child_user_id, plan)
    return result


def get_plan_by_date(db: Session, child_user_id: int, plan_date: date) -> dict | None:
    plan = _get_plan_by_date(db, child_user_id, plan_date)
    if not plan:
        return None
    return _plan_to_response(plan, db=db)


def get_yesterday_training_context(db: Session, child_user_id: int, plan_date: date | None = None) -> str | None:
    """汇总昨日训练与打卡，供 AI 生成今日方案参考"""
    plan_date = plan_date or _today()
    yesterday = plan_date - timedelta(days=1)
    y_plan = _get_plan_by_date(db, child_user_id, yesterday)
    if not y_plan:
        return None

    audio_title = y_plan.items[0].title if y_plan.items else "训练音频"
    if y_plan.status != "completed":
        return f"昨日未完成打卡，系统续推「{audio_title}」"

    record = db.scalar(
        select(TrainingRecord)
        .where(
            TrainingRecord.child_user_id == child_user_id,
            TrainingRecord.plan_id == y_plan.id,
        )
        .order_by(TrainingRecord.id.desc())
        .limit(1)
    )
    parts = [f"昨日已完成音频「{audio_title}」"]
    if record:
        if record.ability_type:
            parts.append(f"能力打卡：{record.ability_type}")
        if record.content:
            parts.append(f"训练记录：{record.content}")
        if record.result:
            parts.append(f"训练效果：{record.result}")
        if record.note:
            parts.append(f"备注：{record.note}")
        if record.attitude_pct is not None:
            parts.append(f"配合度 {record.attitude_pct}%")
        cards = record.files_json if isinstance(record.files_json, list) else []
        if cards:
            names = [c.get("name") for c in cards if c.get("name")]
            if names:
                parts.append(f"训练项：{'、'.join(names)}")
            card_details: list[str] = []
            for c in cards:
                name = c.get("name")
                if not name:
                    continue
                sub: list[str] = []
                if c.get("result"):
                    sub.append(f"效果「{c['result']}」")
                if c.get("note"):
                    sub.append(f"备注「{c['note']}」")
                if sub:
                    card_details.append(f"{name}（{'；'.join(sub)}）")
            if card_details:
                parts.append("分项反馈：" + "；".join(card_details))
    return "；".join(parts)


def get_checkin_history(
    db: Session,
    child_user_id: int,
    limit: int = 60,
    *,
    exclude_today: bool = False,
) -> list[dict]:
    fetch_limit = min(limit * 5, 500) if exclude_today else limit
    rows = db.scalars(
        select(TrainingRecord)
        .where(TrainingRecord.child_user_id == child_user_id)
        .order_by(TrainingRecord.created_at.desc(), TrainingRecord.id.desc())
        .limit(fetch_limit)
    ).all()
    plan_ids = {r.plan_id for r in rows if r.plan_id}
    plans: dict[int, TrainingPlan] = {}
    if plan_ids:
        for plan in db.scalars(select(TrainingPlan).where(TrainingPlan.id.in_(plan_ids))).all():
            plans[plan.id] = plan
    changed = False
    for rec in rows:
        if not rec.train_date and rec.plan_id and plans.get(rec.plan_id):
            rec.train_date = plans[rec.plan_id].plan_date
            changed = True
        elif not rec.train_date and rec.created_at:
            rec.train_date = rec.created_at.date()
            changed = True
    if changed:
        db.commit()

    items = [_record_to_dict(r, plan=plans.get(r.plan_id) if r.plan_id else None) for r in rows]

    if exclude_today:
        today = _today_for(db, child_user_id)
        today_plan = _get_plan_by_date(db, child_user_id, today)

        def _is_active_today_record(item: dict) -> bool:
            pid = item.get("plan_id")
            plan = plans.get(pid) if pid else None
            if today_plan and pid == today_plan.id:
                return True
            if plan and plan.plan_date == today:
                return True
            train_date = item.get("train_date")
            if train_date == today.isoformat():
                return True
            return False

        items = [item for item in items if not _is_active_today_record(item)]

    return items[:limit]


def record_watch_progress(
    db: Session,
    child_user_id: int,
    item_id: int,
    *,
    watched_sec: float,
    duration_sec: float | None = None,
) -> dict:
    item = db.get(TrainingItem, item_id)
    if not item:
        raise TrainingError("训练项不存在", 404)
    plan = db.get(TrainingPlan, item.plan_id)
    if not plan or plan.child_user_id != child_user_id:
        raise TrainingError("训练项不存在", 404)
    if is_plan_globally_cutoff(plan):
        raise TrainingError("训练日已于凌晨4点截止", 403)

    watched = max(0.0, float(watched_sec))
    duration = max(0.0, float(duration_sec or 0))
    prev = item.watch_progress if isinstance(item.watch_progress, dict) else {}
    peak_watched = max(float(prev.get("watched_sec") or 0), watched)
    if duration > 0:
        pct = min(100.0, round(peak_watched / duration * 100, 1))
    else:
        pct = float(prev.get("pct") or 0)

    item.watch_progress = {
        "watched_sec": round(peak_watched, 1),
        "duration_sec": round(duration, 1) if duration > 0 else prev.get("duration_sec"),
        "pct": pct,
    }
    db.commit()
    db.refresh(item)
    return {
        "item_id": item.id,
        "watch_progress": item.watch_progress,
        "video_complete": is_item_video_complete(item),
    }
