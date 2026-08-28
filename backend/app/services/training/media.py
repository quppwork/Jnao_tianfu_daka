"""训练项媒体：听看进度、完成度、媒体用尽"""

from datetime import date

from sqlalchemy.orm import Session

from app.db.models import TrainingItem, TrainingPlan
from app.services.content_meta import parse_item_instruction
from app.services.training.common import WATCH_COMPLETE_PCT, TrainingError, _today, invalidate_plan_cache
from app.services.training_day import is_plan_globally_cutoff

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
    from app.services.training.service import _get_plan_by_date
    plan = _get_plan_by_date(db, child_user_id, plan_date)
    if not plan:
        raise TrainingError("训练计划不存在", 404)
    if is_plan_globally_cutoff(plan):
        raise TrainingError("训练日已于凌晨4点截止", 403)
    mark_plan_media_exhausted(db, plan)
    db.refresh(plan)
    from app.services.training.service import _plan_to_response
    return _plan_to_response(plan, db=db)

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

