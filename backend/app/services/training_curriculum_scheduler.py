"""主线 A→E 规则排课 — 按学员进度从天赋混合池选课（闭环入口）"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.child_training_state import get_training_progress
from app.services.talent_content_pool import get_talent_content_pool
from app.services.training_block_builder import build_main_line_block_plan, build_schedule_note_for_blocks
from app.services.training_curriculum import day_one_config
from app.services.training_curriculum_router import route_curriculum_day_one
from config.loader import load_training_curriculum

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _is_first_schedule(state: dict) -> bool:
    day_one = day_one_config()
    first_line = day_one.get("main_line") or "A"
    if state.get("main_line") != first_line:
        return False
    return int(state.get("main_line_sessions") or 0) == 0 and not (state.get("skills") or {})


def build_curriculum_schedule(
    db: Session,
    child_user_id: int,
    talent_code: int,
    planned_minutes: int,
    *,
    content_index: int = 0,
    carryover: list[dict] | None = None,
    talent_primary: str | None = None,
) -> dict:
    """根据 training_progress + YAML 主线，从天赋混合池生成今日 plan_items"""
    from app.db.models import ChildUser

    child = db.get(ChildUser, child_user_id)
    if not child:
        return {"plan_items": [], "note": "学员不存在", "mode": "error"}

    state = get_training_progress(child)
    pool = get_talent_content_pool(db, talent_code)
    carryover = carryover or []

    if not carryover and _is_first_schedule(state):
        return route_curriculum_day_one(
            db,
            talent_code,
            planned_minutes=planned_minutes,
            talent_primary=talent_primary,
            carryover=carryover,
            state=state,
        )

    cur = load_training_curriculum()
    main_key = state.get("main_line") or "A"
    line = (cur.get("main_lines") or {}).get(main_key) or {}

    packed = build_main_line_block_plan(
        main_key,
        line,
        pool,
        state,
        planned_minutes,
        talent_primary,
        carryover=carryover,
    )
    plan_items = packed["plan_items"]
    note = build_schedule_note_for_blocks(
        main_key, line, planned_minutes, plan_items, talent_primary
    )
    return {
        "plan_items": plan_items,
        "optional_offers": packed.get("optional_offers") or [],
        "note": note,
        "mode": "curriculum_loop",
        "main_line": main_key,
    }
