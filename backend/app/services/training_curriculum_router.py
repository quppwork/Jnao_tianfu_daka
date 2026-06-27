"""按 training_curriculum.yaml 主线 A→E 排课"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.child_training_state import _default_state
from app.services.talent_content_pool import get_talent_content_pool
from app.services.training_block_builder import build_main_line_block_plan, build_schedule_note_for_blocks
from config.loader import load_training_curriculum

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _all_talent_content(db: Session, talent_code: int) -> list:
    return get_talent_content_pool(db, talent_code)


def route_curriculum_day_one(
    db: Session,
    talent_code: int,
    *,
    planned_minutes: int,
    talent_primary: str | None = None,
    carryover: list[dict] | None = None,
    state: dict | None = None,
) -> dict:
    """主线 A：按时长装箱 — 主练超脑阅读（可多轮）+ 辅练/可选（开口窍占位、高效作业等）"""
    cur = load_training_curriculum()
    line = (cur.get("main_lines") or {}).get("A") or {}
    pool = _all_talent_content(db, talent_code)
    if state is None:
        state = _default_state()

    packed = build_main_line_block_plan(
        "A",
        line,
        pool,
        state,
        planned_minutes,
        talent_primary,
        carryover=carryover or [],
    )
    plan_items = packed["plan_items"]
    note = build_schedule_note_for_blocks("A", line, planned_minutes, plan_items, talent_primary)
    return {
        "plan_items": plan_items,
        "optional_offers": packed.get("optional_offers") or [],
        "note": note,
        "mode": "curriculum_day_one",
        "main_line": "A",
    }


def filter_candidates_for_main_line(
    candidates: list,
    main_line_key: str,
) -> list:
    """缩小 LLM 候选池：仅主线声明的技能"""
    cur = load_training_curriculum()
    line = (cur.get("main_lines") or {}).get(main_line_key) or {}
    allowed: set[str] = set(line.get("primary_skills") or [])
    allowed.update(line.get("auxiliary_skills") or [])
    allowed.update(line.get("optional_skills") or [])
    for opt in line.get("optional") or []:
        if isinstance(opt, dict) and opt.get("skill"):
            allowed.add(opt["skill"])
    if not allowed:
        return candidates

    from app.services.content_meta import parse_item_meta

    filtered = []
    for item in candidates:
        meta = parse_item_meta(item)
        skill = meta.get("skill") or ""
        if skill in allowed:
            filtered.append(item)
    return filtered if filtered else candidates
