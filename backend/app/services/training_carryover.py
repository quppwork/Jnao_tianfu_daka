"""v2.0 训练续推 — 选修/辅练不阻断；按技能维度处理"""

from __future__ import annotations

from app.db.models import TrainingItem
from app.services.content_meta import parse_item_instruction, parse_item_meta

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
    """选修/辅练项：不要求单独打卡，直接标记完成"""
    meta = parse_item_instruction(
        item.instructions if item.instructions and item.instructions.strip().startswith("{") else None
    )
    # elective items that don't block
    if meta.get("blocks_next") is False:
        return True
    if meta.get("item_type") == "elective":
        return True
    if meta.get("item_type") == "perception" or item.ability_type == "perception":
        return True
    sk = skill_from_training_item(item)
    if sk in AUXILIARY_SKIP_CARRYOVER:
        return True
    if "多元感知" in (item.title or ""):
        return True
    return False


def auto_complete_skipped_checkin_items(plan) -> int:
    """标记选修/免打卡项为完成，避免阻塞"""
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
