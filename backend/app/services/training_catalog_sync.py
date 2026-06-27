"""补全 OSS 目录（多元感知等）并修复计划里缺媒体的训练项"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ContentItem, TrainingItem, TrainingPlan
from app.services.catalog_import import import_catalog
from app.services.content_meta import content_display_title, parse_item_meta
from app.services.talent_content_pool import get_talent_content_pool
from app.services.training_block_builder import _find_perception_item

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
    if total:
        db.commit()
    return total


def repair_plan_media_items(db: Session, plan: TrainingPlan, talent_code: int) -> int:
    """把占位/无媒体的感知力项替换为 OSS 多元感知音频"""
    pool = get_talent_content_pool(db, talent_code)
    perception = _find_perception_item(pool)
    if not perception:
        return 0

    changed = 0
    for item in plan.items:
        is_perception = item.ability_type == "perception"
        is_ph = item.ability_type == "placeholder" and "感知" in (item.title or "")
        if not is_perception and not is_ph:
            continue
        if item.audio_url and item.content_item_id:
            continue
        item.ability_type = "perception"
        item.title = content_display_title(perception)
        item.audio_url = perception.play_url
        item.content_item_id = perception.id
        item.duration_min = item.duration_min or perception.duration_min
        meta = parse_item_meta(perception)
        import json

        try:
            inst = json.loads(item.instructions or "{}")
        except json.JSONDecodeError:
            inst = {}
        inst["item_type"] = "perception"
        inst["skill"] = meta.get("skill") or "感知力"
        item.instructions = json.dumps(inst, ensure_ascii=False)
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
