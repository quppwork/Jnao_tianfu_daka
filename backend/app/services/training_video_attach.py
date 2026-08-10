"""训练项 ↔ OSS 技能视频匹配与挂载"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ContentItem, TrainingPlan
from app.services.content_meta import parse_item_instruction, parse_item_meta, skill_from_title


def _skill_from_video_item(item: ContentItem) -> str:
    meta = parse_item_meta(item)
    skill = meta.get("skill")
    if skill and skill != "训练":
        return str(skill)
    return skill_from_title(item.lesson_title)


def build_skill_video_map(db: Session) -> dict[str, ContentItem]:
    """技能 → 默认配套视频（同技能取 lesson_sort 最小的一条）"""
    video_items = db.scalars(
        select(ContentItem)
        .where(
            ContentItem.content_type == "video",
            ContentItem.status == 1,
        )
        .order_by(ContentItem.lesson_sort, ContentItem.id)
    ).all()
    video_map: dict[str, ContentItem] = {}
    for item in video_items:
        skill = _skill_from_video_item(item)
        if skill and skill != "训练" and skill not in video_map:
            video_map[skill] = item
    return video_map


def _item_skill_name(item) -> str:
    inst = parse_item_instruction(
        item.instructions
        if item.instructions and item.instructions.strip().startswith("{")
        else None
    )
    skill = inst.get("skill", "")
    if skill:
        return str(skill)
    return skill_from_title(item.title or "")


def attach_videos_to_plan_items(
    db: Session,
    plan: TrainingPlan,
    *,
    only_missing: bool = False,
) -> int:
    """为方案内训练项挂载 OSS 技能视频；only_missing 仅补空 video_url"""
    video_map = build_skill_video_map(db)
    if not video_map:
        return 0

    changed = 0
    for item in plan.items:
        skill = _item_skill_name(item)
        if not skill or skill not in video_map:
            # 无配套视频的技能：清掉历史误挂的 video_url，前端才不显示空视频卡
            if item.video_url:
                item.video_url = None
                changed += 1
            continue
        if only_missing and item.video_url:
            continue
        play_url = video_map[skill].play_url
        if not play_url:
            if item.video_url:
                item.video_url = None
                changed += 1
            continue
        if item.video_url != play_url:
            item.video_url = play_url
            changed += 1
    if changed:
        db.flush()
    return changed
