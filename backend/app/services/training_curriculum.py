"""训练课表 — OSS 音频匹配工具（v3.0 保留）

排课公式逻辑已迁移到 training_formula_engine.py。
此文件仅保留 OSS 内容匹配函数，供 child_training_state、
training_catalog_sync、training_mastery 等模块使用。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models import ContentItem


SINGLE_FILE_SKILLS = frozenset({"高效作业", "精力恢复"})


def _item_meta(item: ContentItem) -> dict:
    from app.services.content_meta import parse_item_meta
    return parse_item_meta(item)


def _match_lesson(item: ContentItem, skill: str, stage: int,
                  part: int) -> bool:
    meta = _item_meta(item)
    item_skill = meta.get("skill")
    if (item_skill == skill and meta.get("stage") == stage
            and meta.get("part") == part):
        return True
    title = item.lesson_title or ""
    # 单文件技能（高效作业 / 精力恢复）
    if skill in SINGLE_FILE_SKILLS:
        if item_skill == skill:
            return True
        if skill in title and "阶段" not in title:
            return True
    # OSS「超脑速读」= 系统「超脑阅读」1阶段1
    if skill == "超脑阅读" and stage == 1 and part == 1:
        if "超脑速读" in title or "超脑阅读" in title:
            s = meta.get("stage")
            p = meta.get("part") or 1
            if s in (None, 0, 1) and p == 1:
                return True
    if skill in title and f"{stage}阶段{part}" in title:
        return True
    return False


def _find_lesson(pool: list[ContentItem], skill: str, stage: int,
                 part: int) -> ContentItem | None:
    for item in pool:
        if _match_lesson(item, skill, stage, part):
            return item
    # 回退：同技能任意课（优先 stage/part 最小）
    fallback: list[ContentItem] = []
    for item in pool:
        meta = _item_meta(item)
        title = item.lesson_title or ""
        if meta.get("skill") == skill or (
            skill in title and "阶段" in title
        ):
            fallback.append(item)
    if not fallback:
        return None
    fallback.sort(key=lambda x: (
        _item_meta(x).get("stage") or 99,
        _item_meta(x).get("part") or 99,
        x.lesson_sort or 0,
        x.id,
    ))
    return fallback[0]
