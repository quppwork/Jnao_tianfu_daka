"""昨日未完成续推 — 感知力等辅练不阻断主线；达标进阶优先于续推"""

from __future__ import annotations

from app.db.models import TrainingItem
from app.services.content_meta import parse_item_instruction, parse_item_meta
from app.services.child_training_state import MAIN_LINES, main_line_index
from config.loader import load_training_curriculum

PERCEPTION_SKILL = "感知力"
AUXILIARY_SKIP_CARRYOVER = frozenset({PERCEPTION_SKILL})


def skill_from_training_item(item: TrainingItem) -> str | None:
    if item.instructions and str(item.instructions).strip().startswith("{"):
        try:
            import json

            payload = json.loads(item.instructions)
            sk = (payload.get("skill") or "").strip()
            if sk:
                return sk
        except json.JSONDecodeError:
            pass
    title = (item.title or "")
    if "多元感知" in title or PERCEPTION_SKILL in title:
        return PERCEPTION_SKILL
    return None


def item_skips_checkin(item: TrainingItem) -> bool:
    """多元感知等辅练：辅助主练，不要求单独打卡"""
    meta = parse_item_instruction(
        item.instructions if item.instructions and item.instructions.strip().startswith("{") else None
    )
    if meta.get("item_type") == "perception" or item.ability_type == "perception":
        return True
    sk = skill_from_training_item(item)
    if sk in AUXILIARY_SKIP_CARRYOVER:
        return True
    if "多元感知" in (item.title or ""):
        return True
    return False


def main_line_key_from_plan_index(content_index: int) -> str:
    try:
        return MAIN_LINES[int(content_index)]
    except (IndexError, ValueError, TypeError):
        return "A"


def primary_skills_for_line(line_key: str) -> list[str]:
    line = (load_training_curriculum().get("main_lines") or {}).get(line_key) or {}
    return list(line.get("primary_skills") or [])


def yesterday_primary_checkin_complete(items: list[TrainingItem], line_key: str) -> bool:
    primary = primary_skills_for_line(line_key)
    if not primary:
        return False
    for sk in primary:
        has_done = any(
            skill_from_training_item(it) == sk and it.checkin_status == "done" for it in items
        )
        if not has_done:
            return False
    return True


def should_carryover_item(
    item: TrainingItem,
    *,
    yesterday_line_key: str,
    current_line_index: int,
    yesterday_items: list[TrainingItem],
) -> bool:
    if item_skips_checkin(item):
        return False
    y_idx = main_line_index(yesterday_line_key)
    if current_line_index > y_idx:
        return False
    skill = skill_from_training_item(item)
    if yesterday_primary_checkin_complete(yesterday_items, yesterday_line_key):
        primary = set(primary_skills_for_line(yesterday_line_key))
        if skill and skill not in primary:
            return False
    return True


def auto_complete_skipped_checkin_items(plan) -> int:
    """主练达标进阶或辅练免打卡项：标记完成，避免阻塞次日排课"""
    n = 0
    for it in plan.items:
        if it.checkin_status == "done":
            continue
        if item_skips_checkin(it):
            it.checkin_status = "done"
            n += 1
    pending = [it for it in plan.items if it.checkin_status != "done"]
    if not pending and plan.status != "completed":
        plan.status = "completed"
    return n
