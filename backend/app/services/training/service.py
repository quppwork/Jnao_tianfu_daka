"""今日训练业务逻辑 — 方案推送、选修、进度（窗口/打卡见同包 window / checkin）"""

import json
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
from app.services.datetime_fmt import format_cst
from app.services.oss_stream_service import training_item_stream_path
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
from app.services.training.common import (
    WATCH_COMPLETE_PCT,
    TrainingError,
    _cache_get,
    _cache_set,
    _format_time,
    _invalidate_after_checkin_change,
    _parse_time,
    _time_in_training_window,
    _today,
    _today_for,
    _user_now,
    invalidate_plan_cache,
)
from app.services.training.window import (
    clear_training_window,
    get_training_window,
    get_window_status,
    set_training_window,
    sync_media_exhausted_from_window,
)
from app.services.training.checkin_cards import (  # noqa: F401
    _apply_card_fields_to_record,
    _card_summary,
    _record_to_dict,
    _sanitize_card,
    _summarize_cards,
    _summarize_notes,
    _summarize_results,
    _summarize_time_spent,
    group_checkin_history_by_day,
)
from app.services.training.checkin import (  # noqa: F401
    delete_checkin_record,
    get_checkin_history,
    get_checkin_record,
    get_today_checkins,
    submit_checkin,
    update_checkin_record,
)

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
    now = _user_now(db, child_user_id)
    plan = _get_plan_by_date(db, child_user_id, plan_date)
    if plan and is_plan_stale(plan, now=now):
        _delete_training_plan(db, plan)
        db.flush()
        return None
    if plan:
        return plan
    cal = now.date()
    if plan_date != cal:
        legacy = _get_plan_by_date(db, child_user_id, cal)
        if legacy and is_plan_stale(legacy, now=now):
            _delete_training_plan(db, legacy)
            db.flush()
        elif legacy and is_plan_day_locked(legacy, now=now):
            return legacy
    return None


def _refresh_volatile_plan_fields(
    db: Session, child_user_id: int, plan_date: date, cached: dict
) -> dict:
    """缓存命中时仍刷新计时/时钟字段，避免倒计时冻结在旧快照。"""
    now = _user_now(db, child_user_id)
    out = dict(cached)
    out.update(training_day_meta(now, plan_date=plan_date))
    plan = _resolve_today_plan(db, child_user_id, plan_date)
    if plan:
        _heal_started_plan_missing_window(db, child_user_id, plan)
        out.update(_build_timer_fields(db, child_user_id, plan, now))
        out["pending_confirm"] = _pending_confirm_flag(db, plan, out.get("timer_phase"))
    return out


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
        .order_by(TrainingPlan.id.desc())
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
    """仅同步「未排课的简单单条推送」；v3 已选时长方案不改 content_index / items。

    v3 排课后 content_index 表示 overall_tier，旧课程序号逻辑不得覆盖。
    """
    tc = _talent_attr(assessment, "talent_code")
    if not assessment or not tc:
        return False
    plan_date = plan_date or _today()
    plan = _get_plan_by_date(db, child_user_id, plan_date)
    if not plan or plan.status == "completed":
        return False
    if not _plan_matches_latest_talent(plan, assessment):
        return False

    # 已按时长排课：只允许校正 level，禁止旧 content_index / 音频覆盖
    if plan.planned_minutes is not None:
        talent_primary = _talent_attr(assessment, "talent_primary") or ""
        if talent_primary and plan.level != talent_primary:
            plan.level = talent_primary
            db.commit()
            return True
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

    # 仅同步「简单推送」单条音频计划
    is_simple = len(plan.items) <= 1
    if not is_simple:
        if changed:
            db.commit()
        return changed

    if not plan.items:
        if changed:
            db.commit()
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

    if plan.items:
        from app.services.training_video_attach import attach_videos_to_plan_items

        if attach_videos_to_plan_items(db, plan, only_missing=True):
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
    if y_plan is None or is_plan_stale(y_plan):
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


def _item_meta_type(item: TrainingItem) -> str:
    meta = parse_item_instruction(
        item.instructions if item.instructions and item.instructions.strip().startswith("{") else None
    )
    return str(meta.get("item_type") or item.ability_type or "")


def item_requires_media_listen(item: TrainingItem) -> bool:
    """有可播放音频且非多元感知/占位时，打卡前须听满。纯视频不限制进度。"""
    t = _item_meta_type(item)
    if t in ("perception", "placeholder"):
        return False
    return bool(item.audio_url)


def _watch_pct(item: TrainingItem) -> float:
    wp = item.watch_progress if isinstance(item.watch_progress, dict) else {}
    audio = wp.get("audio") if isinstance(wp.get("audio"), dict) else None
    if audio is not None:
        return float(audio.get("pct") or 0)
    return float(wp.get("pct") or 0)


def is_item_media_complete(item: TrainingItem) -> bool:
    """打卡门槛：有音频须听满 90%；视频进度不计入、也不拦截。"""
    if not item_requires_media_listen(item):
        return True
    return _watch_pct(item) >= WATCH_COMPLETE_PCT


def is_item_video_complete(item: TrainingItem) -> bool:
    """兼容旧名：音视频统一完成度。"""
    return is_item_media_complete(item)


def _should_hide_media(plan: TrainingPlan) -> bool:
    return bool(getattr(plan, "media_exhausted", 0))


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


def toggle_elective_item(
    db: Session,
    child_user_id: int,
    plan_id: int,
    skill: str,
    action: str,
) -> dict:
    """统一开关选修项：action="add" 插到方案最前，action="remove" 按技能名移除"""
    if action == "add":
        return append_elective_item(db, child_user_id, plan_id, skill)
    elif action == "remove":
        # 按技能名查找 plan 中的选修项
        plan = db.get(TrainingPlan, plan_id)
        if not plan or plan.child_user_id != child_user_id:
            raise TrainingError("训练计划不存在", 404)
        target = None
        for item in plan.items:
            inst = parse_item_instruction(
                item.instructions if item.instructions and str(item.instructions).strip().startswith("{") else None
            )
            if inst.get("skill") == skill:
                target = item
                break
            title = (item.title or "").strip()
            if title == skill or title == f"{skill}（待同步）":
                target = item
                break
        if not target:
            raise TrainingError(f"方案中未找到选修项「{skill}」", 404)
        return remove_plan_item(db, child_user_id, target.id)
    raise TrainingError("action 必须为 add 或 remove", 400)

def get_today_plan(db: Session, child_user_id: int, plan_date: date | None = None) -> dict:
    """获取今日方案；无内容时需先 POST /schedule 选时长生成

    含短期缓存（10s TTL）：消除首页↔训练页来回切换时的重复 DB 查询。
    打卡/排课/选修打卡后自动清除。
    """
    from app.services.training_schedule_service import ensure_today_plan_shell

    plan_date = plan_date or _today_for(db, child_user_id)

    # 短期缓存命中 → 仍刷新计时字段（倒计时不能复用旧快照）
    cached = _cache_get(child_user_id, plan_date)
    if cached is not None:
        return _refresh_volatile_plan_fields(db, child_user_id, plan_date, cached)
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
        started = _plan_session_started(db, plan)
        # 未开练可挂新视频；已开练只补缺音频，避免改掉正在练的方案
        if repair_plan_media_items(db, plan, talent_code, attach_videos=not started):
            db.commit()
            plan = _resolve_today_plan(db, child_user_id, plan_date)
        if plan and plan.items and is_technical_schedule_note(plan.report_text):
            plan.report_text = build_coach_text_for_plan(plan)
            db.commit()
        if plan:
            _heal_started_plan_missing_window(db, child_user_id, plan)
        sync_media_exhausted_from_window(db, child_user_id, plan)
        plan = _resolve_today_plan(db, child_user_id, plan_date)
        result = _plan_to_response(plan, db=db)
        _cache_set(child_user_id, plan_date, result)
        return result

    result = empty_today_plan_response(db, child_user_id, plan_date)
    _cache_set(child_user_id, plan_date, result)
    return result


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
        "pending_confirm": False,
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

    # v3：建壳时 content_index 占位 0，排课后由 populate 写入 overall_tier
    talent_primary = _talent_attr(assessment, "talent_primary") or ""
    plan = TrainingPlan(
        child_user_id=child_user_id,
        plan_date=plan_date,
        level=talent_primary,
        report_text="",
        content_index=0,
        status="pending",
        generated_at=datetime.now(timezone.utc),
    )
    db.add(plan)
    _sync_training_day_counter(db, child_user_id, plan_date)
    db.commit()
    db.refresh(plan)
    return _get_plan_by_date(db, child_user_id, plan_date)


def get_or_create_today_plan(db: Session, child_user_id: int, plan_date: date | None = None) -> dict:
    """[已弃用] 旧「简单推送」自动建单条音频方案。

    主路径请用 get_today_plan + POST /schedule（populate_plan_items）。
    保留仅防外部脚本误调；新代码勿再引用。
    """
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
    db.flush()
    from app.services.training_video_attach import attach_videos_to_plan_items

    attach_videos_to_plan_items(db, plan, only_missing=False)
    db.commit()
    db.refresh(plan)
    plan = _get_plan_by_date(db, child_user_id, plan_date)
    return _plan_to_response(plan, db=db)


def _skills_for_part_rotation(
    cards: list[dict] | None,
    target_item: TrainingItem | None,
) -> list[str]:
    """解析本次打卡应推进 part 计数的必修技能（去重、保序）。

    优先 cards[].name；无卡片时回退到当前训练项 instructions.skill / 标题。
    """
    from app.services.child_training_state import REQUIRED_SKILLS
    from app.services.content_meta import skill_from_title

    required = set(REQUIRED_SKILLS)
    out: list[str] = []
    seen: set[str] = set()

    def _add(name: str | None) -> None:
        sk = (name or "").strip()
        if sk in required and sk not in seen:
            seen.add(sk)
            out.append(sk)

    for card in cards or []:
        if isinstance(card, dict):
            _add(card.get("name"))

    if out:
        return out

    if target_item is None:
        return out

    inst = target_item.instructions
    if inst and str(inst).strip().startswith("{"):
        meta = parse_item_instruction(inst)
        _add(meta.get("skill"))
    if not out:
        _add(skill_from_title(target_item.title or ""))
    return out


def _try_rotate_part_after_checkin(
    db: Session,
    child: ChildUser,
    talent_code: int,
    *,
    cards: list[dict] | None = None,
    target_item: TrainingItem | None = None,
) -> None:
    """打卡后仅对本次涉及的必修技能做 part 轮换判定（计数变化必须落库）。"""
    from app.services.child_training_state import (
        get_training_progress,
        save_training_progress,
        rotate_part_after_checkin,
    )
    from sqlalchemy.orm.attributes import flag_modified

    skills = _skills_for_part_rotation(cards, target_item)
    if not skills:
        return

    pj = child.profile_json if isinstance(child.profile_json, dict) else {}
    onboarding = pj.get("onboarding") or {}
    student_type = str(onboarding.get("student_type", "new"))
    state = get_training_progress(child)

    for skill in skills:
        rotate_part_after_checkin(
            state, skill, student_type=student_type, db=db, talent_code=talent_code
        )

    save_training_progress(db, child, state)
    flag_modified(child, "profile_json")


# 选修项固定优先级：多元感知（感知力）永远第一关，开口窍第二关，其余按原顺序
ELECTIVE_PRIORITY = {"感知力": 0, "开口窍": 1}


def _resort_plan_elective_priority(plan) -> None:
    """重排方案 sort_order：选修项按固定优先级排最前，必修项保持原相对顺序。"""
    items = sorted(plan.items, key=lambda x: x.sort_order or 0)

    def sort_key(it):
        inst = parse_item_instruction(
            it.instructions
            if it.instructions and str(it.instructions).strip().startswith("{")
            else None
        )
        skill = inst.get("skill") if inst else None
        if skill in ELECTIVE_PRIORITY:
            return (0, ELECTIVE_PRIORITY[skill])
        return (1, 0)

    for i, it in enumerate(sorted(items, key=sort_key), start=1):
        it.sort_order = i


def append_elective_item(
    db: Session,
    child_user_id: int,
    plan_id: int,
    skill: str,
) -> dict:
    """在现有方案最前面插入一个选修训练项（如多元感知），有 OSS 音频则带音频"""
    from app.services.content_meta import (
        content_display_title, estimate_duration_min, parse_item_meta,
    )
    from app.services.talent_content_pool import get_talent_content_pool
    from app.services.assessment_service import resolve_effective_talent
    from app.services.training_catalog_sync import ensure_supplementary_catalogs, repair_plan_media_items
    from app.services.training_schedule_service import _attach_videos_to_items
    from app.services.training_child_guide import build_coach_text_for_plan

    plan = db.get(TrainingPlan, plan_id)
    if not plan or plan.child_user_id != child_user_id:
        raise TrainingError("训练计划不存在", 404)
    if is_plan_globally_cutoff(plan):
        raise TrainingError("训练日已于凌晨4点截止", 403)

    # 去重：同一技能已在方案中则跳过（含无 content_item_id 的占位项）
    search_skill = "感知力" if skill == "多元感知" else skill
    for existing in plan.items:
        inst = parse_item_instruction(
            existing.instructions
            if existing.instructions and str(existing.instructions).strip().startswith("{")
            else None
        )
        if inst.get("skill") == skill:
            db.commit()
            plan = _get_plan_by_date(db, child_user_id, plan.plan_date)
            return _plan_to_response(plan, db=db)
        if existing.content_item_id:
            ci = db.get(ContentItem, existing.content_item_id)
            if ci:
                from app.services.content_meta import parse_item_meta as _pim
                if _pim(ci).get("skill") == search_skill:
                    db.commit()
                    plan = _get_plan_by_date(db, child_user_id, plan.plan_date)
                    return _plan_to_response(plan, db=db)

    items = sorted(plan.items, key=lambda x: x.sort_order)
    # 选修项插到最前面：取当前最小 sort_order 再减 1（负值排序正常）
    next_sort = (items[0].sort_order - 1) if items else 1

    talent = resolve_effective_talent(db, child_user_id)
    talent_code = talent.get("talent_code") if talent else None
    pool = get_talent_content_pool(db, talent_code) if talent_code else []

    content = None
    for item in pool:
        meta = parse_item_meta(item)
        if meta.get("skill") == search_skill:
            content = item
            break

    # fallback: talent pool 未命中时，查 content_item 全表（视频等跨天赋内容）
    if not content:
        content = db.scalar(
            select(ContentItem).where(
                ContentItem.status == 1,
                ContentItem.instructions.contains(search_skill),
            ).limit(1)
        )

    if content:
        is_video = (content.content_type == "video")
        inst_data = {"skill": skill, "item_type": "elective", "blocks_next": False}
        if is_video:
            inst_data["content_type"] = "video"
        inst = json.dumps(inst_data, ensure_ascii=False)
        db.add(TrainingItem(
            plan_id=plan.id, sort_order=next_sort, ability_type="elective",
            title=content_display_title(content),
            duration_min=estimate_duration_min(content),
            audio_url=None if is_video else content.play_url,
            video_url=content.play_url if is_video else content.video_url,
            content_item_id=content.id, instructions=inst,
            checkin_status="pending",
        ))
    else:
        db.add(TrainingItem(
            plan_id=plan.id, sort_order=next_sort, ability_type="elective",
            title=f"{skill}（待同步）", duration_min=0,
            instructions=json.dumps(
                {"skill": skill, "item_type": "elective", "blocks_next": False},
                ensure_ascii=False,
            ),
            checkin_status="pending",
        ))

    db.flush()  # 确保新项进入 plan.items，再按固定优先级重排
    _resort_plan_elective_priority(plan)

    if talent_code:
        ensure_supplementary_catalogs(db)
        repair_plan_media_items(db, plan, talent_code)
    else:
        _attach_videos_to_items(db, plan)
    plan.report_text = build_coach_text_for_plan(plan)
    db.commit()
    invalidate_plan_cache(child_user_id, plan.plan_date)
    from app.core.cache import invalidate_user_training
    invalidate_user_training(child_user_id, plan_date=plan.plan_date)

    plan = _get_plan_by_date(db, child_user_id, plan.plan_date)
    return _plan_to_response(plan, db=db)


def remove_plan_item(
    db: Session,
    child_user_id: int,
    item_id: int,
) -> dict:
    """从方案中移除一个训练项（仅限选修项）"""
    item = db.get(TrainingItem, item_id)
    if not item:
        raise TrainingError("训练项不存在", 404)
    plan = db.get(TrainingPlan, item.plan_id)
    if not plan or plan.child_user_id != child_user_id:
        raise TrainingError("训练项不存在", 404)
    if is_plan_globally_cutoff(plan):
        raise TrainingError("训练日已于凌晨4点截止", 403)

    # 仅允许移除选修项
    from app.services.training_carryover import item_skips_checkin
    if not item_skips_checkin(item):
        raise TrainingError("只能移除选修训练项", 403)

    from sqlalchemy import update

    db.execute(update(TrainingRecord).where(TrainingRecord.item_id == item_id).values(item_id=None))
    db.delete(item)
    db.flush()  # 确保被删项从 plan.items 中移除
    # 重排剩余项的 sort_order
    remaining = sorted(plan.items, key=lambda x: x.sort_order or 0)
    for i, it in enumerate(remaining, start=1):
        it.sort_order = i

    from app.services.training_child_guide import build_coach_text_for_plan
    plan.report_text = build_coach_text_for_plan(plan)
    db.commit()
    invalidate_plan_cache(child_user_id, plan.plan_date)
    from app.core.cache import invalidate_user_training
    invalidate_user_training(child_user_id, plan_date=plan.plan_date)

    plan = _get_plan_by_date(db, child_user_id, plan.plan_date)
    return _plan_to_response(plan, db=db)


def _auto_promote_to_returning(db: Session, child_user_id: int) -> None:
    """累计打卡 >= 30 次的新学员 -> 自动转为老学员。

    与是否已完成 onboarding（completed_at）无关；已是 returning 则跳过。
    一天一次训练前提下，TrainingRecord 行数即可代表累计打卡次数。
    """
    from app.db.models import TrainingRecord
    from sqlalchemy import func, select
    from sqlalchemy.orm.attributes import flag_modified

    user = db.get(ChildUser, child_user_id)
    if not user or not isinstance(user.profile_json, dict):
        return
    onboarding = user.profile_json.get("onboarding") or {}
    if not isinstance(onboarding, dict):
        return
    if onboarding.get("student_type") != "new":
        return

    count = db.scalar(
        select(func.count()).select_from(TrainingRecord).where(
            TrainingRecord.child_user_id == child_user_id,
        )
    ) or 0
    if count < 30:
        return

    from datetime import datetime, timezone, timedelta

    ob = dict(onboarding)
    ob["student_type"] = "returning"
    ob["promoted_to_returning_at"] = datetime.now(timezone(timedelta(hours=8))).isoformat()
    pj = dict(user.profile_json)
    pj["onboarding"] = ob
    user.profile_json = pj
    flag_modified(user, "profile_json")
    db.commit()


def _is_elective_item(item: TrainingItem) -> bool:
    """判断是否为选修/不阻塞项"""
    from app.services.training_carryover import item_skips_checkin

    return item_skips_checkin(item)


def _mutable_required_items(plan: TrainingPlan) -> list[TrainingItem]:
    """可替换的必修项（未打卡、非选修）"""
    items = sorted(plan.items, key=lambda x: x.sort_order)
    return [
        it for it in items
        if it.checkin_status != "done" and not _is_elective_item(it)
    ]


def _plan_has_any_checkin(db: Session, plan: TrainingPlan) -> bool:
    """方案下是否已有任意打卡（含选修）"""
    if any(it.checkin_status == "done" for it in plan.items):
        return True
    cnt = db.scalar(
        select(func.count())
        .select_from(TrainingRecord)
        .where(TrainingRecord.plan_id == plan.id)
    )
    return (cnt or 0) > 0


def _can_customize_plan(db: Session, plan: TrainingPlan, *, now: datetime) -> bool:
    if plan.status == "completed":
        return False
    if is_plan_globally_cutoff(plan, now=now):
        return False
    if getattr(plan, "plan_customized", 0):
        return False
    if _plan_has_any_checkin(db, plan):
        return False
    return len(_mutable_required_items(plan)) > 0


def _item_block(item: TrainingItem) -> str | None:
    return parse_item_instruction(item.instructions).get("block")


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
            # v2.0: 只回退当前被删除的 item，不影响同 block 其他 item
            item.checkin_status = "pending"

    pending = [it for it in plan.items if it.checkin_status != "done"]
    plan.status = "pending" if pending else "completed"
    return plan.status


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


def record_watch_progress(
    db: Session,
    child_user_id: int,
    item_id: int,
    *,
    watched_sec: float,
    duration_sec: float | None = None,
    media: str | None = None,
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
    kind = (media or "audio").strip().lower()
    if kind not in ("audio", "video"):
        kind = "audio"

    slot = prev.get(kind) if isinstance(prev.get(kind), dict) else {}
    if kind == "audio":
        peak_watched = max(float(slot.get("watched_sec") or prev.get("watched_sec") or 0), watched)
    else:
        peak_watched = max(float(slot.get("watched_sec") or 0), watched)
    if duration > 0:
        pct = min(100.0, round(peak_watched / duration * 100, 1))
    else:
        pct = float(slot.get("pct") or (prev.get("pct") if kind == "audio" else 0) or 0)

    chunk = {
        "watched_sec": round(peak_watched, 1),
        "duration_sec": round(duration, 1) if duration > 0 else slot.get("duration_sec"),
        "pct": pct,
    }
    next_wp = dict(prev)
    next_wp[kind] = chunk
    if kind == "audio":
        # 顶层 pct 仍表示音频进度，供旧前端/打卡门槛使用
        next_wp["watched_sec"] = chunk["watched_sec"]
        next_wp["duration_sec"] = chunk["duration_sec"]
        next_wp["pct"] = chunk["pct"]
    item.watch_progress = next_wp
    db.commit()
    db.refresh(item)
    if plan:
        invalidate_plan_cache(child_user_id, plan.plan_date)
    return {
        "item_id": item.id,
        "watch_progress": item.watch_progress,
        "video_complete": is_item_video_complete(item),
    }


# ─── 个性化替换 ────────────────────────────────────


def customize_plan_items(
    db: Session,
    child_user_id: int,
    plan_id: int,
    skills: list[str],
) -> dict:
    """整体替换今日训练方案中的项目（不改技能等级进度）

    约束：
    - skills 列表长度必须等于原方案 items 数量
    - 每个技能取用户当前的 oss_stage/oss_part → 从 OSS 池找对应音频
    - 找不到音频 → 占位符
    - 选修项不受影响
    """
    from app.services.content_meta import (
        content_display_title,
        estimate_duration_min,
        item_instruction,
        parse_item_meta,
    )
    from app.services.talent_content_pool import get_talent_content_pool
    from app.services.child_training_state import (
        REQUIRED_SKILLS,
        get_skill_oss_position,
        get_training_progress,
    )
    from app.services.assessment_service import resolve_effective_talent
    from app.services.training_catalog_sync import repair_plan_media_items
    from app.services.training_child_guide import build_coach_text_for_plan

    plan = db.get(TrainingPlan, plan_id)
    if not plan or plan.child_user_id != child_user_id:
        raise TrainingError("训练计划不存在", 404)
    if plan.status == "completed":
        raise TrainingError("今日训练已完成，无法修改", 403)
    now = _user_now(db, child_user_id)
    if is_plan_globally_cutoff(plan, now=now):
        raise TrainingError("训练日已于凌晨4点截止", 403)
    if getattr(plan, "plan_customized", 0):
        raise TrainingError("今日方案已编辑过，每个训练日仅可修改一次", 403)

    mutable = _mutable_required_items(plan)
    if not mutable:
        raise TrainingError("当前没有可编辑的必修项", 400)
    if _plan_has_any_checkin(db, plan):
        raise TrainingError("已有打卡记录，无法编辑方案", 403)

    items = sorted(plan.items, key=lambda x: x.sort_order)
    if len(skills) != len(mutable):
        raise TrainingError(
            f"需要 {len(mutable)} 个技能（当前待打卡项数），实际提交 {len(skills)} 个",
            400,
        )

    # 校验技能名合法
    cur = __import__("config.loader", fromlist=["load_training_curriculum"]).load_training_curriculum()
    elective_rules = cur.get("elective_rules") or {}
    elective_skills = set(elective_rules.keys())
    allowed_skills = set(REQUIRED_SKILLS) | elective_skills
    for sk in skills:
        if sk not in allowed_skills:
            raise TrainingError(f"未知技能：{sk}", 400)

    # 获取用户天赋 + OSS 池
    talent = resolve_effective_talent(db, child_user_id)
    if not talent or not talent.get("talent_code"):
        raise TrainingError("请先完成天赋测评", 403)
    talent_code = talent["talent_code"]

    child = db.get(ChildUser, child_user_id)
    state = get_training_progress(child) if child else {}
    pool = get_talent_content_pool(db, talent_code)

    def _find_content(skill_name: str) -> tuple:
        """从 OSS 池找该技能当前 OSS 位置对应的音频"""
        stage, part = get_skill_oss_position(state, skill_name)
        for item in pool:
            meta = parse_item_meta(item)
            if meta.get("skill") == skill_name:
                s = meta.get("stage", 0)
                p = meta.get("part", 0)
                if s == stage and p == part:
                    return item, stage, part
        # fallback: 任意第一个
        for item in pool:
            meta = parse_item_meta(item)
            if meta.get("skill") == skill_name:
                return item, meta.get("stage", 0), meta.get("part", 0)
        return None, stage, part

    # 逐个替换 mutable 项
    for i, target_item in enumerate(mutable):
        skill_name = skills[i]
        is_elective = skill_name in elective_rules

        content, stage, part = _find_content(skill_name)
        if content:
            meta = parse_item_meta(content)
            inst = item_instruction("A", meta.get("content_type") or "audio")
            try:
                payload = json.loads(inst)
                payload["skill"] = meta.get("skill") or skill_name
                payload["item_type"] = "elective" if is_elective else "required"
                payload["oss_stage"] = stage
                payload["oss_part"] = part
                inst = json.dumps(payload, ensure_ascii=False)
            except Exception:
                pass
            target_item.title = content_display_title(content)
            target_item.audio_url = content.play_url
            target_item.video_url = content.video_url
            target_item.duration_min = estimate_duration_min(content)
            target_item.content_item_id = content.id
            target_item.instructions = inst
            target_item.ability_type = "audio"
        else:
            target_item.title = f"{skill_name}（待同步）"
            target_item.audio_url = None
            target_item.video_url = None
            target_item.duration_min = 0
            target_item.content_item_id = None
            target_item.instructions = item_instruction("A", "placeholder")
            target_item.ability_type = "placeholder"

    # 匹配视频（极速运算等）
    from app.services.training_schedule_service import _attach_videos_to_items
    _attach_videos_to_items(db, plan)

    repair_plan_media_items(db, plan, talent_code)
    plan.report_text = build_coach_text_for_plan(plan)
    plan.plan_customized = 1
    db.commit()

    invalidate_plan_cache(child_user_id, plan.plan_date)
    from app.core.cache import invalidate_user_training
    invalidate_user_training(child_user_id, plan_date=plan.plan_date)

    plan = _get_plan_by_date(db, child_user_id, plan.plan_date)
    return _plan_to_response(plan, db=db)
