"""为 LLM 排课构建上下文 — 框架约束 + 学员状态 + 昨日未完成 plan_item"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ChildUser, ContentItem, TrainingItem, TrainingPlan, TrainingRecord
from app.services.assessment_service import get_latest_assessment
from app.services.child_training_state import get_training_progress, main_line_index
from app.services.content_meta import estimate_duration_min, parse_item_meta
from app.services.training_carryover import (
    item_skips_checkin,
    main_line_key_from_plan_index,
    should_carryover_item,
    skill_from_training_item,
)
from app.services.training_day import get_training_day, training_now
from app.services.training_service import WATCH_COMPLETE_PCT, get_yesterday_training_context
from config.loader import load_training_curriculum

if TYPE_CHECKING:
    from app.db.models import Assessment


def _grade_band(grade: str | None) -> str | None:
    cfg = load_training_curriculum().get("grade_bands") or {}
    g = (grade or "").strip()
    if not g:
        return None
    for band, grades in cfg.items():
        if g in grades:
            return band
    return None


def _child_grade(db: Session, child_user_id: int) -> str | None:
    child = db.get(ChildUser, child_user_id)
    if not child or not child.profile_json:
        return None
    pj = child.profile_json if isinstance(child.profile_json, dict) else {}
    return pj.get("grade")


def duration_slot(planned_minutes: int) -> dict:
    cfg = load_training_curriculum().get("duration_schedule") or {}
    max_rounds = int(cfg.get("max_rounds_per_skill") or 3)
    slots = cfg.get("slots") if isinstance(cfg, dict) else cfg
    if not isinstance(slots, list):
        slots = []
    for row in slots:
        if row.get("min") <= planned_minutes <= row.get("max"):
            out = dict(row)
            out["rounds_per_item"] = min(int(out.get("rounds_per_item") or 1), max_rounds)
            out["max_rounds_per_skill"] = max_rounds
            return out
    return {"items": 1, "rounds_per_item": 1, "max_rounds_per_skill": max_rounds}


def _item_incomplete(item: TrainingItem) -> bool:
    if item_skips_checkin(item):
        return False
    if item.checkin_status != "done":
        return True
    wp = item.watch_progress if isinstance(item.watch_progress, dict) else {}
    if item.audio_url and float(wp.get("pct") or 0) < WATCH_COMPLETE_PCT:
        return True
    if item.video_url and float(wp.get("pct") or 0) < WATCH_COMPLETE_PCT:
        return True
    return False


def get_carryover_plan_items(
    db: Session,
    child_user_id: int,
    plan_date: date | None = None,
) -> list[dict]:
    """昨日未完成 plan_item（未听完或未打卡）→ 今日优先重推"""
    plan_date = plan_date or get_training_day()
    yesterday = plan_date - timedelta(days=1)
    y_plan = db.scalar(
        select(TrainingPlan).where(
            TrainingPlan.child_user_id == child_user_id,
            TrainingPlan.plan_date == yesterday,
        )
    )
    if not y_plan:
        return []

    child = db.get(ChildUser, child_user_id)
    state = get_training_progress(child) if child else {}
    current_line_index = main_line_index(state.get("main_line") or "A")
    yesterday_line_key = main_line_key_from_plan_index(y_plan.content_index)

    items = db.scalars(
        select(TrainingItem)
        .where(TrainingItem.plan_id == y_plan.id)
        .order_by(TrainingItem.sort_order)
    ).all()

    out: list[dict] = []
    for it in items:
        if not _item_incomplete(it):
            continue
        if not should_carryover_item(
            it,
            yesterday_line_key=yesterday_line_key,
            current_line_index=current_line_index,
            yesterday_items=items,
        ):
            continue
        if not it.content_item_id:
            meta = {}
        else:
            ci = db.get(ContentItem, it.content_item_id)
            meta = parse_item_meta(ci) if ci else {}
        skill = skill_from_training_item(it) or meta.get("skill")
        out.append(
            {
                "source_item_id": it.id,
                "content_item_id": it.content_item_id,
                "title": it.title,
                "skill": skill,
                "stage": meta.get("stage"),
                "part": meta.get("part"),
                "duration_min": it.duration_min or estimate_duration_min(
                    db.get(ContentItem, it.content_item_id)
                ),
                "reason": "昨日主练未完成",
            }
        )
    return out


def build_framework_summary() -> str:
    cur = load_training_curriculum()
    lines = [
        "主线 A→E 按学员能力推进；OSS stage/part 与主线数字不一一对应。",
        "主练/辅练时间约 7:3；推送内容总时长可少于用户设定时长。",
        "六～九阶段本期不纳入；预警本期关闭。",
        f"时长装箱: {(cur.get('duration_schedule') or {}).get('slots')}",
        f"主练辅练比例: {cur.get('mix_ratio')}",
    ]
    main_lines = cur.get("main_lines") or {}
    for key, spec in main_lines.items():
        prim = spec.get("primary_skills") or []
        aux = spec.get("auxiliary_skills") or spec.get("optional_skills") or []
        lines.append(f"主线{key}: 主练 {prim}, 辅/可选 {aux}")
    return "\n".join(lines)


def candidate_to_dict(item: ContentItem) -> dict:
    meta = parse_item_meta(item)
    return {
        "id": item.id,
        "title": item.lesson_title or "",
        "skill": meta.get("skill", ""),
        "stage": meta.get("stage"),
        "part": meta.get("part"),
        "series": meta.get("series", ""),
        "duration_min": estimate_duration_min(item),
    }


def build_route_context(
    db: Session,
    child_user_id: int,
    planned_minutes: int,
    candidates: list[ContentItem],
    *,
    plan_date: date | None = None,
    assessment: Assessment | None = None,
    talent_primary: str | None = None,
) -> dict:
    plan_date = plan_date or get_training_day()
    if not talent_primary:
        if assessment:
            talent_primary = assessment.talent_primary
        else:
            from app.services.assessment_service import resolve_effective_talent

            eff = resolve_effective_talent(db, child_user_id)
            talent_primary = eff.get("talent_primary") if eff else None
    grade = _child_grade(db, child_user_id)
    slot = duration_slot(planned_minutes)
    carryover = get_carryover_plan_items(db, child_user_id, plan_date)
    yesterday_summary = get_yesterday_training_context(db, child_user_id, plan_date)
    cur = load_training_curriculum()
    llm_cfg = cur.get("llm_routing") or {}

    return {
        "framework_summary": build_framework_summary(),
        "talent_primary": talent_primary,
        "grade": grade,
        "grade_band": _grade_band(grade),
        "planned_minutes": planned_minutes,
        "duration_slot": slot,
        "carryover_items": carryover,
        "yesterday_summary": yesterday_summary,
        "candidates": [candidate_to_dict(c) for c in candidates],
        "candidate_ids": {c.id for c in candidates},
        "llm_enabled": bool(llm_cfg.get("enabled")),
        "now_iso": training_now().isoformat(),
        "plan_date": plan_date.isoformat(),
    }
