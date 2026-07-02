"""按天赋聚合全部 OSS 系列 — 排课只认 talent_code，不按 chaonaoaomi/xuekeaomi 分池"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.content_meta import parse_item_meta
from config.loader import load_training_curriculum

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.db.models import ContentItem

# OSS 系列仅作元数据；查询时按天赋合并
TALENT_SERIES_ORDER = ("suzhiaomi", "chaonaoaomi", "xuekeaomi", "chaonengli", "duoyuanganzhi")

TALENT_CODE_TO_NAME = {
    1: "学者",
    2: "思者",
    3: "行者",
    4: "德者",
    5: "赢者",
}


def get_talent_content_pool(
    db: Session,
    talent_code: int,
    *,
    skill: str | None = None,
    start_index: int = 0,
    limit: int | None = None,
    skip_intro: bool = True,
) -> list[ContentItem]:
    """该天赋下全部系列课程（混合池），供排课 / LLM / 规则路由使用"""
    from app.services.training_service import get_content_series

    seen: set[int] = set()
    merged: list[ContentItem] = []
    for series in TALENT_SERIES_ORDER:
        rows = get_content_series(
            db,
            talent_code,
            series=series,
            prefer_skill=skill,
            skip_intro=skip_intro,
        )
        for item in rows:
            if item.id not in seen:
                seen.add(item.id)
                merged.append(item)

    if skill:
        preferred = [i for i in merged if parse_item_meta(i).get("skill") == skill]
        others = [i for i in merged if parse_item_meta(i).get("skill") != skill]
        merged = preferred + others

    if start_index and merged:
        idx = start_index % len(merged)
        merged = merged[idx:] + merged[:idx]

    if limit is not None and limit > 0:
        merged = merged[:limit]
    return merged


def _main_line_skills(main_line_key: str) -> tuple[set[str], set[str]]:
    cur = load_training_curriculum()
    line = (cur.get("main_lines") or {}).get(main_line_key) or {}
    primary = set(line.get("primary_skills") or [])
    auxiliary = set(line.get("auxiliary_skills") or [])
    auxiliary.update(line.get("optional_skills") or [])
    for opt in line.get("optional") or []:
        if isinstance(opt, dict) and opt.get("skill"):
            auxiliary.add(opt["skill"])
    return primary, auxiliary


def split_pool_for_training_blocks(
    pool: list[ContentItem],
    main_line_key: str,
) -> tuple[list[ContentItem], list[ContentItem]]:
    """混合池按主线主练/辅练拆成训练块 A / B（不按 OSS 系列拆）"""
    primary, auxiliary = _main_line_skills(main_line_key)
    block_a: list[ContentItem] = []
    block_b: list[ContentItem] = []
    rest: list[ContentItem] = []
    for item in pool:
        skill = parse_item_meta(item).get("skill") or ""
        if skill in primary:
            block_a.append(item)
        elif skill in auxiliary:
            block_b.append(item)
        else:
            rest.append(item)
    if not block_b and rest:
        block_b = rest
    return block_a, block_b


def summarize_pool_by_skill(pool: list[ContentItem]) -> dict[str, dict]:
    """按技能汇总：第一课 + 课数 + 来源系列"""
    by_skill: dict[str, list[ContentItem]] = {}
    for item in pool:
        skill = parse_item_meta(item).get("skill") or "训练"
        by_skill.setdefault(skill, []).append(item)

    summary: dict[str, dict] = {}
    for skill, items in sorted(by_skill.items()):
        items.sort(
            key=lambda x: (
                parse_item_meta(x).get("stage") or 0,
                parse_item_meta(x).get("part") or 0,
                x.lesson_sort or 0,
                x.id,
            )
        )
        first = items[0]
        meta = parse_item_meta(first)
        sources = sorted({parse_item_meta(i).get("series") or "?" for i in items})
        summary[skill] = {
            "skill": skill,
            "total": len(items),
            "sources": sources,
            "first_stage": meta.get("stage"),
            "first_part": meta.get("part"),
            "first_title": first.lesson_title,
            "first_oss_key": meta.get("oss_key"),
        }
    return summary
