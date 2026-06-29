"""补全 OSS 目录（多元感知等）并修复计划里缺媒体的训练项"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ContentItem, TrainingItem, TrainingPlan
from app.services.catalog_import import import_catalog
from app.services.child_training_state import get_skill_position, get_training_progress
from app.services.content_meta import content_display_title, parse_item_instruction, parse_item_meta
from app.services.talent_content_pool import get_talent_content_pool
from app.services.training_block_builder import _find_perception_item
from app.services.training_carryover import skill_from_training_item
from app.services.training_curriculum import _find_lesson

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SUPPLEMENTARY_CATALOGS = (
    "xet_duoyuanganzhi_catalog.json",
)


def ensure_supplementary_catalogs(db: Session) -> int:
    """合并导入多元感知等补充目录（已有库也执行）"""
    total = 0
    for name in SUPPLEMENTARY_CATALOGS:
        path = PROJECT_ROOT / "docs" / "data" / name
        if path.exists():
            total += import_catalog(db, path, replace=False)
    return total


def _attach_content_to_item(item: TrainingItem, content: ContentItem, *, skill: str) -> None:
    meta = parse_item_meta(content)
    item.ability_type = "audio"
    item.title = content_display_title(content)
    item.audio_url = content.play_url
    item.video_url = content.video_url
    item.content_item_id = content.id
    item.duration_min = item.duration_min or content.duration_min
    try:
        inst = json.loads(item.instructions or "{}")
    except json.JSONDecodeError:
        inst = parse_item_instruction(item.instructions) or {}
    if not isinstance(inst, dict):
        inst = {}
    inst["item_type"] = meta.get("content_type") or "audio"
    inst["skill"] = meta.get("skill") or skill
    item.instructions = json.dumps(inst, ensure_ascii=False)


def repair_plan_media_items(db: Session, plan: TrainingPlan, talent_code: int) -> int:
    """修复占位/无音频项：感知力、扫描速记等主辅练"""
    from app.db.models import ChildUser

    pool = get_talent_content_pool(db, talent_code)
    if not pool:
        return 0

    child = db.get(ChildUser, plan.child_user_id)
    state = get_training_progress(child) if child else {}
    perception = _find_perception_item(pool)
    changed = 0

    for item in plan.items:
        if item.audio_url and item.content_item_id:
            continue

        skill = skill_from_training_item(item)
        title = item.title or ""

        if skill == "感知力" or "多元感知" in title or item.ability_type == "perception":
            if perception:
                item.ability_type = "perception"
                item.title = content_display_title(perception)
                item.audio_url = perception.play_url
                item.content_item_id = perception.id
                item.duration_min = item.duration_min or perception.duration_min
                meta = parse_item_meta(perception)
                try:
                    inst = json.loads(item.instructions or "{}")
                except json.JSONDecodeError:
                    inst = {}
                inst["item_type"] = "perception"
                inst["skill"] = meta.get("skill") or "感知力"
                item.instructions = json.dumps(inst, ensure_ascii=False)
                changed += 1
            continue

        if not skill and item.ability_type == "placeholder":
            for hint in ("扫描速记", "影像追忆", "超脑阅读", "极速运算", "极速学习"):
                if hint in title:
                    skill = hint
                    break

        if not skill:
            continue

        stage, part = get_skill_position(state, skill)
        found = _find_lesson(pool, skill, stage, part)
        if found:
            _attach_content_to_item(item, found, skill=skill)
            changed += 1

    if changed:
        db.flush()
    return changed


def count_duoyuanganzhi(db: Session, talent_code: int) -> int:
    rows = list(
        db.scalars(
            select(ContentItem).where(
                ContentItem.talent_code == talent_code,
                ContentItem.status == 1,
            )
        ).all()
    )
    return sum(1 for r in rows if parse_item_meta(r).get("series") == "duoyuanganzhi")
