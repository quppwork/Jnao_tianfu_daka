"""训练排程 — 先选时长再生成；框架内 LLM 路由 + plan_item 续推"""

from __future__ import annotations

import json
from datetime import date

from sqlalchemy import desc, select
from sqlalchemy.orm import selectinload, Session

from app.db.models import ChildUser, ContentItem, TrainingItem, TrainingPlan, TrainingRecord
from app.services.assessment_service import resolve_effective_talent
from app.services.child_training_state import (
    filter_active_skills,
    get_skill_oss_position,
    get_skills_with_records,
    get_training_progress,
    overall_tier,
)
from app.services.content_meta import estimate_duration_min, item_instruction, parse_item_meta, content_display_title
from app.services.talent_content_pool import get_talent_content_pool
from app.services.training_catalog_sync import ensure_supplementary_catalogs, repair_plan_media_items
from app.services.training_child_guide import build_coach_text_for_plan
from app.services.training_formula_engine import (
    duration_slot,
    expand_formula,
    HistoryEntry,
)
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
    expected = get_training_day(now)
    resolved = plan_date or expected
    if resolved != expected:
        raise TrainingError("只能操作当日训练方案", 400)
    return resolved

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
    """项数超出公式上界，或旧版 v1 同 block 重复 → 需重生成"""
    from app.services.content_meta import parse_item_instruction

    max_items = int(duration_slot(planned_minutes).get("items") or 1)
    if len(plan.items) > max_items:
        return True
    block_counts: dict[str, int] = {}
    for item in plan.items:
        meta = parse_item_instruction(
            item.instructions if item.instructions and item.instructions.strip().startswith("{") else None
        )
        if meta.get("skill"):
            continue  # v2 公式排课项均带 skill，不按 block 字母判重复
        block = meta.get("block") or "A"
        block_counts[block] = block_counts.get(block, 0) + 1
        if block_counts[block] > 1:
            return True
    return False


def _attach_videos_to_items(db: Session, plan: TrainingPlan) -> None:
    """为训练项匹配对应技能的视频（如极速运算 → _1.5极速运算的原理及过程.mp4）"""
    from app.services.content_meta import parse_item_instruction, skill_from_title

    video_items = db.scalars(
        select(ContentItem).where(
            ContentItem.content_type == "video",
            ContentItem.status == 1,
        )
    ).all()
    if not video_items:
        return

    video_map: dict[str, ContentItem] = {}
    sorted_videos = sorted(
        video_items,
        key=lambda v: (skill_from_title(v.lesson_title), v.lesson_sort or 0),
    )
    for v in sorted_videos:
        skill = skill_from_title(v.lesson_title)
        if skill and skill != "训练" and skill not in video_map:
            video_map[skill] = v

    if not video_map:
        return

    for item in plan.items:
        inst = parse_item_instruction(
            item.instructions
            if item.instructions and item.instructions.strip().startswith("{")
            else None
        )
        skill = inst.get("skill", "")
        if skill in video_map:
            item.video_url = video_map[skill].play_url


async def populate_plan_items(
    db: Session,
    plan: TrainingPlan,
    child_user_id: int,
    planned_minutes: int,
    *,
    plan_date: date | None = None,
) -> dict:
    """v3.0: Decision Tree 选策略 → 权重引擎展开 → OSS 音频 → plan_items"""
    ensure_supplementary_catalogs(db)
    plan_date = plan_date or plan.plan_date
    talent = resolve_effective_talent(db, child_user_id)
    if not talent or not talent.get("talent_code"):
        raise TrainingError("请先完成天赋测评", 403)

    talent_code = talent["talent_code"]
    child = db.get(ChildUser, child_user_id)
    state = get_training_progress(child) if child else {}

    # v3.0: overall_tier 替代 content_index — 只算有打卡记录的技能
    skills_with_records = get_skills_with_records(db, child_user_id)
    active_state = filter_active_skills(state, skills_with_records)
    o_tier = overall_tier(active_state)
    plan.content_index = o_tier

    # 获取年级 → 学段
    from app.services.child_training_state import child_grade
    child = db.get(ChildUser, child_user_id)
    grade = child_grade(child) if child else ""
    from app.services.training_mastery import _grade_band
    grade_band = _grade_band(grade) or "primary_low"

    # 提取每个技能的个体 Tier
    skill_tiers: dict[str, int] = {}
    skills_state = state.get("skills", {})
    for skill_name, skill_info in skills_state.items():
        if isinstance(skill_info, dict) and "tier" in skill_info:
            skill_tiers[skill_name] = int(skill_info["tier"])

    # 构建近 30 天训练历史（供 Decision Tree 条件判断）
    recent_plans = db.scalars(
        select(TrainingPlan)
        .where(TrainingPlan.child_user_id == child_user_id)
        .where(TrainingPlan.status.in_(["completed", "pending"]))
        .order_by(desc(TrainingPlan.plan_date))
        .limit(30)
    ).all()
    history: tuple[HistoryEntry, ...] = tuple(
        HistoryEntry(
            plan_date=p.plan_date,
            planned_minutes=p.planned_minutes or 0,
            skills=tuple(
                it.title or "" for it in (p.items or [])
            ),
        )
        for p in reversed(recent_plans)  # 时间升序
    )

    # 公式引擎展开技能组合
    formula_result = expand_formula(
        planned_minutes,
        overall_tier=o_tier,
        grade_band=grade_band,
        skill_tiers=skill_tiers,
        history=history,
    )
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
                payload = json.loads(inst)
                payload["skill"] = meta.get("skill") or skill_name
                payload["item_type"] = "elective" if is_elective else "required"
                payload["blocks_next"] = blocks_next
                inst = json.dumps(payload, ensure_ascii=False)
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

    # v3.0: 精力恢复已由引擎在 _ctx_to_result 中追加，此处不再重复
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

    # 匹配视频：为有对应视频的技能附加 video_url
    _attach_videos_to_items(db, plan)

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
        "mode": f"v3_{formula_result.get('strategy', 'unknown')}",
        "strategy": formula_result.get("strategy"),
        "bundle_id": formula_result.get("bundle_id"),
        "bundle_note": formula_result.get("bundle_note"),
        "grade_notes": formula_result.get("grade_notes", []),
        "reason": formula_result.get("reason"),
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
    # 方案变更后清除缓存，确保 GET /today 返回最新数据
    from app.services.training_service import invalidate_plan_cache
    from app.core.cache import invalidate_user_training

    invalidate_plan_cache(child_user_id, plan_date)
    invalidate_user_training(child_user_id, plan_date=plan_date)
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
