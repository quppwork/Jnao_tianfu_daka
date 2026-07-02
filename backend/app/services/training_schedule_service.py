"""训练排程 — 先选时长再生成；框架内 LLM 路由 + plan_item 续推"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import selectinload, Session

from app.db.models import ChildUser, ContentItem, TrainingItem, TrainingPlan, TrainingRecord
from app.services.assessment_service import resolve_effective_talent
from app.services.child_training_state import get_training_progress, overall_tier, get_skill_oss_position
from app.services.content_meta import estimate_duration_min, item_instruction, parse_item_meta, content_display_title
from app.services.talent_content_pool import get_talent_content_pool
from app.services.training_catalog_sync import ensure_supplementary_catalogs, repair_plan_media_items
from app.services.training_child_guide import build_coach_text_for_plan
from app.services.training_formula_engine import expand_formula
from app.services.training_service import (
    TrainingError,
    _get_plan_by_date,
    _plan_to_response,
    create_plan_for_schedule,
)
from app.services.training_day import get_training_day, is_new_day_ready


def _resolve_plan_date(db: Session, child_user_id: int, plan_date: date | None = None) -> date:
    from app.services.dev_clock import resolve_training_now

    now = resolve_training_now(db, child_user_id)
    return plan_date or get_training_day(now)

DEFAULT_DAILY_PLAN_MINUTES = 45


def _candidate_dict(item: ContentItem) -> dict:
    meta = parse_item_meta(item)
    return {
        "id": item.id,
        "title": item.lesson_title or "",
        "skill": meta.get("skill", "训练"),
        "series": meta.get("series", "chaonaoaomi"),
        "duration_min": estimate_duration_min(item),
        "lesson_sort": item.lesson_sort,
    }


def _build_full_candidate_pool(
    db: Session,
    talent_code: int,
    content_index: int,
) -> list[ContentItem]:
    """该天赋全部系列混合候选池（不按 OSS 系列拆分）"""
    pool_limit = 80 if content_index <= 0 else 48
    return get_talent_content_pool(
        db,
        talent_code,
        start_index=content_index,
        limit=pool_limit,
    )


def _plan_has_started(db: Session, plan: TrainingPlan) -> bool:
    if plan.status == "completed":
        return True
    rec = db.scalar(
        select(TrainingRecord.id).where(TrainingRecord.plan_id == plan.id).limit(1)
    )
    if rec:
        return True
    for it in plan.items:
        wp = it.watch_progress if isinstance(it.watch_progress, dict) else {}
        if float(wp.get("pct") or 0) > 0:
            return True
    return False


def _plan_to_schedule_response(
    db: Session, plan: TrainingPlan, *, schedule_mode: str | None = None
) -> dict:
    base = _plan_to_response(plan, db=db)
    if schedule_mode:
        base["schedule_mode"] = schedule_mode
    return base


def _has_plan_content(plan: TrainingPlan) -> bool:
    return len(plan.items) > 0


def _plan_structure_invalid(plan: TrainingPlan, planned_minutes: int) -> bool:
    """同一训练块多项、或超出时长表块数 → 旧排课结构，需重生成"""
    from app.services.content_meta import parse_item_instruction

    slot_cfg = duration_slot(planned_minutes)
    max_blocks = int(slot_cfg.get("items") or 1)
    if len(plan.items) > max_blocks:
        return True
    block_counts: dict[str, int] = {}
    for item in plan.items:
        meta = parse_item_instruction(
            item.instructions if item.instructions and item.instructions.strip().startswith("{") else None
        )
        block = meta.get("block") or "A"
        block_counts[block] = block_counts.get(block, 0) + 1
        if block_counts[block] > 1:
            return True
    return False


async def populate_plan_items(
    db: Session,
    plan: TrainingPlan,
    child_user_id: int,
    planned_minutes: int,
    *,
    plan_date: date | None = None,
) -> dict:
    """v2.0: 公式引擎展开 → 取各技能 OSS 音频 → 生成 plan_items"""
    ensure_supplementary_catalogs(db)
    plan_date = plan_date or plan.plan_date
    talent = resolve_effective_talent(db, child_user_id)
    if not talent or not talent.get("talent_code"):
        raise TrainingError("请先完成天赋测评", 403)

    talent_code = talent["talent_code"]
    child = db.get(ChildUser, child_user_id)
    state = get_training_progress(child) if child else {}

    # v2.0: overall_tier 替代 content_index
    o_tier = overall_tier(state)
    plan.content_index = o_tier

    # 获取年级 → 学段
    from app.services.child_training_state import child_grade
    child = db.get(ChildUser, child_user_id)
    grade = child_grade(child) if child else ""
    from app.services.training_mastery import _grade_band
    grade_band = _grade_band(grade) or "primary_low"

    # 公式引擎展开技能组合
    formula_result = expand_formula(planned_minutes, overall_tier=o_tier, grade_band=grade_band)
    slots = formula_result["slots"]

    # OSS 音频池
    talent_pool = get_talent_content_pool(db, talent_code)
    id_map = {c.id: c for c in talent_pool}

    # 清除旧 items
    for old in list(plan.items):
        db.delete(old)
    db.flush()

    sort_order = 1

    def _find_content_for_skill(skill_name: str) -> ContentItem | None:
        """在 OSS 池中查找该技能当前 stage/part 对应的音频"""
        stage, part = get_skill_oss_position(state, skill_name)
        for item in talent_pool:
            meta = parse_item_meta(item)
            if meta.get("skill") == skill_name:
                s = meta.get("stage", 0)
                p = meta.get("part", 0)
                if s == stage and p == part:
                    return item
        # fallback: 找该技能任意第一个可用音频
        for item in talent_pool:
            meta = parse_item_meta(item)
            if meta.get("skill") == skill_name:
                return item
        return None

    def _add_item(
        *,
        content: ContentItem | None = None,
        skill_name: str = "",
        is_elective: bool = False,
        blocks_next: bool = True,
    ) -> None:
        nonlocal sort_order
        if content:
            meta = parse_item_meta(content)
            inst = item_instruction("A", meta.get("content_type") or "audio")
            try:
                payload = __import__("json").loads(inst)
                payload["skill"] = meta.get("skill") or skill_name
                payload["item_type"] = "elective" if is_elective else "required"
                payload["blocks_next"] = blocks_next
                inst = __import__("json").dumps(payload, ensure_ascii=False)
            except Exception:
                pass
            title = content_display_title(content)
            db.add(
                TrainingItem(
                    plan_id=plan.id,
                    sort_order=sort_order,
                    ability_type="audio",
                    title=title,
                    duration_min=estimate_duration_min(content),
                    audio_url=content.play_url,
                    video_url=content.video_url,
                    content_item_id=content.id,
                    instructions=inst,
                    checkin_status="pending",
                )
            )
        else:
            # 占位：OSS 中找不到该技能的音频
            db.add(
                TrainingItem(
                    plan_id=plan.id,
                    sort_order=sort_order,
                    ability_type="placeholder",
                    title=f"{skill_name}（待同步）",
                    duration_min=0,
                    instructions=item_instruction("A", "placeholder"),
                    checkin_status="pending",
                )
            )
        sort_order += 1

    # 遍历公式槽位，为每个技能取对应 OSS 音频
    elective_rules = __import__("config.loader", fromlist=["load_training_curriculum"]).load_training_curriculum().get("elective_rules") or {}
    for skill_name in slots:
        is_elective = skill_name in elective_rules
        er = elective_rules.get(skill_name, {})
        blocks_next = not is_elective  # 选修不阻塞
        if is_elective:
            blocks_next = er.get("blocks_next", False)

        content = _find_content_for_skill(skill_name)
        _add_item(content=content, skill_name=skill_name, is_elective=is_elective, blocks_next=blocks_next)

    plan.planned_minutes = planned_minutes
    plan.media_exhausted = 0
    db.flush()
    plan = db.scalar(
        select(TrainingPlan).options(selectinload(TrainingPlan.items)).where(TrainingPlan.id == plan.id)
    )
    repair_plan_media_items(db, plan, talent_code)
    plan.report_text = build_coach_text_for_plan(plan)

    db.flush()
    return {
        "formula_slots": slots,
        "c_note": formula_result.get("c_note"),
        "exam_note": formula_result.get("exam_note"),
        "elective_notes": formula_result.get("elective_notes", []),
        "mode": "formula_v2",
    }


def ensure_today_plan_shell(
    db: Session,
    child_user_id: int,
    plan_date: date | None = None,
) -> TrainingPlan:
    """仅创建当日空方案壳，不自动生成内容（等内容在选时长后生成）"""
    from app.services.dev_clock import resolve_training_now

    now = resolve_training_now(db, child_user_id)
    if not is_new_day_ready(now):
        raise TrainingError("训练日切换中，请约 5 分钟后再试", 503)

    plan_date = _resolve_plan_date(db, child_user_id, plan_date)
    plan = create_plan_for_schedule(db, child_user_id, plan_date)
    if not plan:
        raise TrainingError("无法创建训练计划", 500)
    return plan


async def schedule_training_by_duration(
    db: Session,
    child_user_id: int,
    planned_minutes: int,
    *,
    plan_date: date | None = None,
) -> dict:
    """用户选定时长 → 生成今日 plan_item（LLM 框架内路由）"""
    if planned_minutes < 5:
        raise TrainingError("训练时长至少 5 分钟")

    from app.services.dev_clock import resolve_training_now

    now = resolve_training_now(db, child_user_id)
    if not is_new_day_ready(now):
        raise TrainingError("训练日切换中，请约 5 分钟后再试", 503)

    plan_date = _resolve_plan_date(db, child_user_id, plan_date)
    plan = ensure_today_plan_shell(db, child_user_id, plan_date)
    if plan.status == "completed":
        raise TrainingError("今日训练已完成，次日凌晨4点解锁", 403)

    if not _plan_has_started(db, plan) or _plan_structure_invalid(plan, planned_minutes):
        route = await populate_plan_items(
            db, plan, child_user_id, planned_minutes, plan_date=plan_date
        )
        schedule_mode = route.get("mode", "rule")
    elif not _has_plan_content(plan) or plan.planned_minutes != planned_minutes:
        raise TrainingError("训练已开始，无法更改今日设定时长", 403)
    else:
        schedule_mode = "existing"

    db.commit()
    plan = _get_plan_by_date(db, child_user_id, plan_date)
    if not plan or not _has_plan_content(plan):
        raise TrainingError("今日方案生成失败", 500)
    if plan.items:
        plan.report_text = build_coach_text_for_plan(plan)
        db.commit()
    return _plan_to_schedule_response(db, plan, schedule_mode=schedule_mode)


# 兼容旧调用
def ensure_today_plan_content(
    db: Session,
    child_user_id: int,
    plan_date: date | None = None,
    *,
    content_minutes: int = DEFAULT_DAILY_PLAN_MINUTES,
) -> TrainingPlan:
    """兼容：仅确保方案壳存在，不自动填充（需 POST /schedule）"""
    return ensure_today_plan_shell(db, child_user_id, plan_date)
