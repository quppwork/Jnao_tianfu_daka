"""今日训练业务逻辑 — 推送、打卡、时段"""

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

# ── Plan 响应短期缓存（Redis，无 REDIS_URL 时直读 DB）──
from app.core.cache import (
    cache_delete,
    cache_get_json,
    cache_set_json,
    key_train_today,
    ttl_env,
)

_PLAN_CACHE_TTL = ttl_env("CACHE_TTL_TRAINING_TODAY", 30)


def invalidate_plan_cache(child_user_id: int, plan_date: date):
    """打卡、修改方案后立即清除该用户当日缓存"""
    cache_delete(key_train_today(child_user_id, plan_date))


def _cache_get(child_user_id: int, plan_date: date) -> dict | None:
    data = cache_get_json(key_train_today(child_user_id, plan_date))
    return data if isinstance(data, dict) else None


def _cache_set(child_user_id: int, plan_date: date, data: dict) -> None:
    cache_set_json(key_train_today(child_user_id, plan_date), data, _PLAN_CACHE_TTL)


def _invalidate_after_checkin_change(child_user_id: int, plan_date: date) -> None:
    from app.core.cache import invalidate_user_growth, invalidate_user_training

    invalidate_plan_cache(child_user_id, plan_date)
    invalidate_user_growth(child_user_id)
    invalidate_user_training(child_user_id, plan_date=plan_date)


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


class TrainingError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _parse_time(value: str) -> time:
    parts = value.strip().split(":")
    if len(parts) < 2:
        raise TrainingError("时间格式应为 HH:MM")
    sec = int(parts[2]) if len(parts) > 2 else 0
    return time(int(parts[0]), int(parts[1]), sec)


def _format_time(value: time) -> str:
    return value.strftime("%H:%M:%S") if value.second else value.strftime("%H:%M")


def _refresh_volatile_plan_fields(
    db: Session, child_user_id: int, plan_date: date, cached: dict
) -> dict:
    """缓存命中时仍刷新计时/时钟字段，避免倒计时冻结在旧快照。"""
    now = _user_now(db, child_user_id)
    out = dict(cached)
    out.update(training_day_meta(now, plan_date=plan_date))
    plan = _resolve_today_plan(db, child_user_id, plan_date)
    if plan:
        out.update(_build_timer_fields(db, child_user_id, plan, now))
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
            "agent_schedule_enabled": False,
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
    from app.services.training_agent_assist import is_schedule_assist_enabled

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
        "agent_schedule_enabled": is_schedule_assist_enabled(),
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
    """有可播放音/视频且非多元感知/占位时，打卡前须听完/看完。"""
    t = _item_meta_type(item)
    if t in ("perception", "placeholder"):
        return False
    return bool(item.video_url or item.audio_url)


def _watch_pct(item: TrainingItem) -> float:
    wp = item.watch_progress if isinstance(item.watch_progress, dict) else {}
    return float(wp.get("pct") or 0)


def is_item_media_complete(item: TrainingItem) -> bool:
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
        from app.services.child_training_state import get_training_progress, overall_tier

        child = db.get(ChildUser, plan.child_user_id)
        tp = get_training_progress(child) if child else {}
        o_tier = overall_tier(tp) if tp else 1
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
        # DEV：Agent 排课理由；正式 UI 勿展示
        "schedule_assist": getattr(plan, "schedule_assist_json", None) or None,
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
    """统一开关选修项：action="add" 追加，action="remove" 按技能名移除"""
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
    return mark_plan_media_exhausted(db, plan)


def _time_in_training_window(start: time, end: time, current: time) -> bool:
    """训练窗口内判断，支持跨日（如 22:00→06:00）。"""
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end


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
        if repair_plan_media_items(db, plan, talent_code):
            db.commit()
            plan = _resolve_today_plan(db, child_user_id, plan_date)
        if plan and plan.items and is_technical_schedule_note(plan.report_text):
            plan.report_text = build_coach_text_for_plan(plan)
            db.commit()
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

    if not is_item_media_complete(target_item):
        raise TrainingError(
            f"请先听完/看完本项音视频后再打卡（需达到 {int(WATCH_COMPLETE_PCT)}%）",
            403,
        )

    if cards:
        cards = [_sanitize_card(c) for c in cards]

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
    # 原子抢占：仅在未打卡时标记 done，防止并发重复提交
    from sqlalchemy import update as sql_update
    claimed = db.execute(
        sql_update(TrainingItem)
        .where(TrainingItem.id == target_item.id, TrainingItem.checkin_status != "done")
        .values(checkin_status="done")
    )
    if claimed.rowcount == 0:
        db.rollback()
        raise TrainingError("该项已完成打卡，请勿重复提交", 409)

    # v2.0: 各技能独立打卡，不再按 block 批量标记完成。
    # pre-v2.0 的 block 批量逻辑已移除。

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

            # Part 轮换：仅对本次打卡涉及的必修技能计数（一天一次训练前提下按项/卡片计）
            _try_rotate_part_after_checkin(
                db, child, talent_code, cards=cards, target_item=target_item
            )

    db.commit()
    db.refresh(record)

    # 累计打卡 >= 30 次的新学员 -> 自动转为老学员
    _auto_promote_to_returning(db, child_user_id)

    # 打卡后清除当日方案缓存，下次 GET /today 拉取最新状态
    invalidate_plan_cache(child_user_id, plan.plan_date)
    _invalidate_after_checkin_change(child_user_id, plan.plan_date)
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


def _sanitize_card(card: dict) -> dict:
    """清洗单张打卡卡片，防止脏数据入库"""
    c = dict(card)
    # 数值字段：转 float 并 clamp 到合理范围
    for field, lo, hi in [
        ("time", 0.5, 480), ("wordCount", 1, 1000000),
        ("accuracy", 0, 100), ("count", 1, 100000),
    ]:
        raw = c.get(field)
        if raw is not None and raw != "":
            try:
                v = float(str(raw))
                c[field] = max(lo, min(hi, v))
            except (ValueError, TypeError):
                c.pop(field, None)
    # 文本字段：截断
    for field, limit in [
        ("note", 2000), ("content", 2000), ("result", 2000),
        ("materialName", 200), ("tag", 50), ("tool", 50),
        ("materialType", 50), ("forwardAcc", 50), ("backwardAcc", 50),
        ("forwardTime", 20), ("backwardTime", 20),
    ]:
        val = c.get(field)
        if isinstance(val, str) and len(val) > limit:
            c[field] = val[:limit]
    return c


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
    checkin_at = format_cst(created) if created else None
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


def append_elective_item(
    db: Session,
    child_user_id: int,
    plan_id: int,
    skill: str,
) -> dict:
    """在现有方案末尾追加一个选修训练项（如多元感知），有 OSS 音频则带音频"""
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
    next_sort = (items[-1].sort_order + 1) if items else 1

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
        from app.services.training_mastery import process_checkin_progress

        child = db.get(ChildUser, child_user_id)
        talent = _resolve_effective_talent(db, child_user_id)
        talent_code = talent.get("talent_code") if talent else None
        if child and talent_code:
            db.flush()
            from app.services.child_training_state import child_grade

            progress_delta = process_checkin_progress(
                db,
                child,
                plan,
                [],
                talent_code=talent_code,
                grade=child_grade(child),
            )
    db.commit()
    db.refresh(record)
    if plan:
        _invalidate_after_checkin_change(child_user_id, plan.plan_date)
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
        from app.services.training_mastery import process_checkin_progress

        child = db.get(ChildUser, child_user_id)
        talent = _resolve_effective_talent(db, child_user_id)
        talent_code = talent.get("talent_code") if talent else None
        if child and talent_code:
            from app.services.child_training_state import child_grade

            progress_delta = process_checkin_progress(
                db,
                child,
                plan,
                [],
                talent_code=talent_code,
                grade=child_grade(child),
            )
    db.commit()
    if plan:
        _invalidate_after_checkin_change(child_user_id, plan.plan_date)
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
