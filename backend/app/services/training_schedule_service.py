"""训练排程 — 先选时长再生成；框架内 LLM 路由 + plan_item 续推"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import selectinload, Session

from app.db.models import ChildUser, ContentItem, TrainingItem, TrainingPlan, TrainingRecord
from app.services.assessment_service import effective_talent_code, get_latest_assessment, has_valid_talent
from app.services.child_training_state import get_training_progress, main_line_index
from app.services.content_meta import estimate_duration_min, item_instruction, parse_item_meta, content_display_title
from app.services.talent_content_pool import (
    get_talent_content_pool,
    split_pool_for_training_blocks,
)
from app.services.training_block_builder import normalize_plan_items_by_duration
from app.services.training_catalog_sync import ensure_supplementary_catalogs, repair_plan_media_items
from app.services.training_child_guide import build_coach_text_for_plan
from app.services.training_curriculum_router import filter_candidates_for_main_line
from app.services.training_curriculum_scheduler import build_curriculum_schedule
from app.services.training_route_context import build_route_context, duration_slot
from app.services.training_route_llm import llm_route_training_plan
from app.services.training_service import (
    TrainingError,
    _get_plan_by_date,
    _item_to_dict,
    _plan_to_response,
    create_plan_for_schedule,
)
from app.services.training_day import get_training_day, is_new_day_ready

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
    """按用户选定时长生成 plan_item（LLM 框架内路由 + 昨日未完成续推）"""
    ensure_supplementary_catalogs(db)
    plan_date = plan_date or plan.plan_date
    assessment = get_latest_assessment(db, child_user_id)
    if not has_valid_talent(assessment):
        raise TrainingError("请先完成天赋测评", 403)

    talent_code = effective_talent_code(assessment)
    child = db.get(ChildUser, child_user_id)
    state = get_training_progress(child) if child else {}
    plan.content_index = main_line_index(state.get("main_line") or "A")

    talent_pool = get_talent_content_pool(db, talent_code)
    candidates = _build_full_candidate_pool(db, talent_code, plan.content_index)
    if not candidates:
        raise TrainingError("暂无可用训练音频", 503)

    main_key = state.get("main_line") or "A"
    candidates_a, candidates_b = split_pool_for_training_blocks(talent_pool, main_key)
    if not candidates_a:
        candidates_a = get_talent_content_pool(db, talent_code, skill="超脑阅读", limit=48)

    ctx = build_route_context(
        db,
        child_user_id,
        planned_minutes,
        candidates,
        plan_date=plan_date,
        assessment=assessment,
    )

    carryover = ctx.get("carryover_items") or []
    route = build_curriculum_schedule(
        db,
        child_user_id,
        talent_code,
        planned_minutes,
        content_index=plan.content_index,
        carryover=carryover,
        talent_primary=assessment.talent_primary,
    )

    cur = __import__("config.loader", fromlist=["load_training_curriculum"]).load_training_curriculum()
    llm_cfg = cur.get("llm_routing") or {}
    if not route.get("plan_items") and llm_cfg.get("enabled"):
        filtered = filter_candidates_for_main_line(candidates, main_key)
        filtered_ids = {x.id for x in filtered}
        ctx["candidates"] = [c for c in (ctx.get("candidates") or []) if c.get("id") in filtered_ids]
        ctx["candidate_ids"] = filtered_ids
        route = await llm_route_training_plan(
            ctx,
            content_index=plan.content_index,
            candidates_a=filter_candidates_for_main_line(candidates_a, main_key),
            candidates_b=filter_candidates_for_main_line(candidates_b or [], main_key),
            seed_key=f"{child_user_id}:{plan_date.isoformat()}",
        )

    route["plan_items"] = normalize_plan_items_by_duration(
        route.get("plan_items") or [], planned_minutes
    )

    id_map = {c.id: c for c in talent_pool}
    for old in list(plan.items):
        db.delete(old)
    db.flush()

    sort_order = 1

    def _add_item(
        *,
        content: ContentItem | None = None,
        placeholder_skill: str | None = None,
        block: str,
        role: str,
        round_no: int,
        item_type: str = "audio",
    ) -> None:
        nonlocal sort_order
        if placeholder_skill:
            title = (
                f"{placeholder_skill}（占位）"
                if placeholder_skill == "开口窍"
                else "多元感知（待同步）"
                if placeholder_skill == "感知力"
                else f"{placeholder_skill}（待同步）"
            )
            ability = "perception" if placeholder_skill == "感知力" else "placeholder"
            inst_type = "perception" if placeholder_skill == "感知力" else "placeholder"
            db.add(
                TrainingItem(
                    plan_id=plan.id,
                    sort_order=sort_order,
                    ability_type=ability,
                    title=title,
                    duration_min=0,
                    instructions=item_instruction(block, inst_type),
                    checkin_status="pending",
                )
            )
            sort_order += 1
            return
        if not content:
            return
        meta = parse_item_meta(content)
        resolved_type = item_type or meta.get("content_type") or "audio"
        if resolved_type == "perception" or meta.get("skill") == "感知力":
            resolved_type = "perception"
        inst = item_instruction(block, resolved_type)
        try:
            payload = __import__("json").loads(inst)
            payload["skill"] = meta.get("skill") or payload.get("skill")
            payload["role"] = role
            payload["round"] = round_no
            inst = __import__("json").dumps(payload, ensure_ascii=False)
        except Exception:
            pass
        title = content_display_title(content)
        if meta.get("skill") == "感知力" or "多元感知" in title:
            title = title if "多元感知" in title else f"{title}多元感知"
        db.add(
            TrainingItem(
                plan_id=plan.id,
                sort_order=sort_order,
                ability_type="perception" if resolved_type == "perception" else "audio",
                title=title,
                duration_min=estimate_duration_min(content),
                audio_url=content.play_url,
                video_url=content.video_url,
                content_item_id=content.id,
                instructions=inst,
                checkin_status="pending",
            )
        )
        sort_order += 1

    for row in route.get("plan_items") or []:
        slot = int(row.get("training_slot") or 1)
        block = "A" if slot == 1 else "B" if slot == 2 else f"T{slot}"
        role = row.get("role") or "primary"
        round_no = int(row.get("round") or 1)
        item_type = row.get("item_type") or "audio"
        ph = row.get("placeholder_skill")
        if ph:
            _add_item(
                placeholder_skill=str(ph),
                block=block,
                role=role,
                round_no=round_no,
                item_type=item_type,
            )
            continue
        cid = row.get("content_item_id")
        content = id_map.get(cid) or db.get(ContentItem, cid)
        _add_item(
            content=content,
            block=block,
            role=role,
            round_no=round_no,
            item_type=item_type,
        )

    plan.planned_minutes = planned_minutes
    plan.media_exhausted = 0
    db.flush()
    plan = db.scalar(
        select(TrainingPlan).options(selectinload(TrainingPlan.items)).where(TrainingPlan.id == plan.id)
    )
    repair_plan_media_items(db, plan, talent_code)
    plan.report_text = build_coach_text_for_plan(plan, main_line=route.get("main_line"))

    db.flush()
    return {**route, "mode": route.get("mode", "rule")}


def ensure_today_plan_shell(
    db: Session,
    child_user_id: int,
    plan_date: date | None = None,
) -> TrainingPlan:
    """仅创建当日空方案壳，不自动生成内容（等内容在选时长后生成）"""
    if not is_new_day_ready():
        raise TrainingError("训练日切换中，请约 5 分钟后再试", 503)

    plan_date = plan_date or get_training_day()
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

    plan_date = plan_date or get_training_day()
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
