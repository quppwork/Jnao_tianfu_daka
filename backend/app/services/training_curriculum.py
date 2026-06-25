"""训练课表路由 — 首日固定、次日随机，课序推进规则不变"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from config.loader import load_settings

if TYPE_CHECKING:
    from app.db.models import ContentItem

DEFAULT_DAY_ONE = {
    "a_lessons": [
        {"skill": "影像追忆", "stage": 1, "part": 1},
        {"skill": "影像追忆", "stage": 1, "part": 2},
    ],
    "b_lessons": [{"skill": "数学奥秘", "stage": 1, "part": 1}],
}


def _training_cfg() -> dict:
    return load_settings().get("training", {})


def day_one_config() -> dict:
    cfg = _training_cfg().get("day_one") or {}
    return {
        "a_lessons": cfg.get("a_lessons") or DEFAULT_DAY_ONE["a_lessons"],
        "b_lessons": cfg.get("b_lessons") or DEFAULT_DAY_ONE["b_lessons"],
    }


def after_day_one_strategy() -> str:
    return (_training_cfg().get("after_day_one") or {}).get("strategy") or "random"


def is_first_training_day(content_index: int) -> bool:
    """content_index==0 表示首日或昨日未完成需续学"""
    return content_index <= 0


def _item_meta(item: ContentItem) -> dict:
    from app.services.content_meta import parse_item_meta

    return parse_item_meta(item)


def _match_lesson(item: ContentItem, skill: str, stage: int, part: int) -> bool:
    meta = _item_meta(item)
    if meta.get("skill") == skill and meta.get("stage") == stage and meta.get("part") == part:
        return True
    title = item.lesson_title or ""
    return skill in title and f"{stage}阶段{part}" in title


def _find_lesson(pool: list[ContentItem], skill: str, stage: int, part: int) -> ContentItem | None:
    for item in pool:
        if _match_lesson(item, skill, stage, part):
            return item
    return None


def _pick_fixed_ids(pool: list[ContentItem], lessons: list[dict]) -> list[int]:
    ids: list[int] = []
    for spec in lessons:
        item = _find_lesson(pool, spec["skill"], int(spec["stage"]), int(spec["part"]))
        if item and item.id not in ids:
            ids.append(item.id)
    return ids


def route_day_one(
    candidates_a: list[ContentItem],
    candidates_b: list[ContentItem],
) -> dict:
    """首日固定课：脑力奥秘入门 + 学科奥秘首课"""
    cfg = day_one_config()
    a_ids = _pick_fixed_ids(candidates_a, cfg["a_lessons"])
    b_ids = _pick_fixed_ids(candidates_b, cfg["b_lessons"])

    if not a_ids and candidates_a:
        a_ids = [candidates_a[0].id]
    if not b_ids and candidates_b:
        b_ids = [candidates_b[0].id]

    titles_a = [c.lesson_title for c in candidates_a if c.id in a_ids]
    note = "首日固定体验课"
    if titles_a:
        note += f"：{titles_a[0]}"
    return {
        "training_a_ids": a_ids,
        "training_b_ids": b_ids,
        "note": note,
        "mode": "day_one_fixed",
    }


def _pick_by_duration(items: list[ContentItem], budget_min: int) -> list[ContentItem]:
    from app.services.content_meta import estimate_duration_min

    picked: list[ContentItem] = []
    total = 0
    for item in items:
        dur = estimate_duration_min(item)
        if picked and total + dur > budget_min:
            continue
        if not picked or total + dur <= budget_min:
            picked.append(item)
            total += dur
        if total >= budget_min * 0.85:
            break
    if not picked and items:
        picked.append(items[0])
    return picked


def route_random(
    candidates_a: list[ContentItem],
    candidates_b: list[ContentItem],
    planned_minutes: int,
    *,
    content_index: int,
    seed_key: str,
) -> dict:
    """次日及以后：在课序窗口内随机抽课（同用户同日结果稳定）"""
    rng = random.Random(seed_key)
    video_reserve = 5
    audio_budget = max(10, planned_minutes - video_reserve)
    a_budget = max(10, int(audio_budget * 0.45))
    b_budget = audio_budget - a_budget

    pool_a = candidates_a[:]
    pool_b = candidates_b[:]
    rng.shuffle(pool_a)
    rng.shuffle(pool_b)

    block_a = _pick_by_duration(pool_a, a_budget)
    used = {c.id for c in block_a}
    block_b = _pick_by_duration([c for c in pool_b if c.id not in used], b_budget)

    lesson_no = content_index + 1
    return {
        "training_a_ids": [c.id for c in block_a],
        "training_b_ids": [c.id for c in block_b],
        "note": f"第 {lesson_no} 课随机排课（脑力 A + 学科 B）",
        "mode": "random",
    }


def route_training_blocks(
    content_index: int,
    candidates_a: list[ContentItem],
    candidates_b: list[ContentItem],
    planned_minutes: int,
    *,
    seed_key: str,
) -> dict:
    if is_first_training_day(content_index):
        return route_day_one(candidates_a, candidates_b)
    return route_random(
        candidates_a,
        candidates_b,
        planned_minutes,
        content_index=content_index,
        seed_key=f"{seed_key}:{content_index}",
    )
