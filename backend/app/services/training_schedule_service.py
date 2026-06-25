"""训练排程 — 按时长匹配音频、豆包路由 A/B 训练块"""

from __future__ import annotations

import json
import re
from datetime import date

from sqlalchemy.orm import Session

from app.db.models import ContentItem, TrainingItem, TrainingPlan
from app.services.assessment_service import get_latest_assessment
from app.services.content_meta import estimate_duration_min, item_instruction
from app.services.doubao_client import chat_completion, is_configured
from app.services.training_service import (
    TrainingError,
    _get_plan_by_date,
    _item_to_dict,
    _plan_to_response,
    get_content_series,
    get_or_create_today_plan,
)
from app.services.training_curriculum import route_training_blocks
from app.services.video_push_service import get_talent_training_video

ROUTE_SYSTEM = """你是 JNAO 训练排课教练。根据学员今日可用训练总时长、天赋类型，安排「训练A」和「训练B」的音频组合。
规则：
1. 训练A 只能从「脑力奥秘 training_a_candidates」中选 1-3 条（热身/基础）
2. 训练B 只能从「学科奥秘 training_b_candidates」中选 0-4 条（强化/学科）
3. 总音频时长尽量接近目标时长（可略少 5 分钟内），A/B 的 id 不可重复
4. 只输出 JSON：{"training_a_ids":[1,2],"training_b_ids":[3],"note":"一句话说明"}"""


def _candidate_dict(item: ContentItem) -> dict:
    from app.services.content_meta import parse_item_meta

    meta = parse_item_meta(item)
    return {
        "id": item.id,
        "title": item.lesson_title or "",
        "skill": meta.get("skill", "训练"),
        "series": meta.get("series", "chaonaoaomi"),
        "duration_min": estimate_duration_min(item),
        "lesson_sort": item.lesson_sort,
    }


def _build_candidates(
    db: Session,
    talent_code: int,
    start_index: int,
    *,
    series: str = "chaonaoaomi",
    limit: int = 24,
) -> list[ContentItem]:
    items = get_content_series(db, talent_code, series=series)
    if not items:
        return []
    ordered = items[start_index:] + items[:start_index]
    return ordered[:limit]


def _pick_by_duration(items: list[ContentItem], budget_min: int) -> list[ContentItem]:
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


def _fallback_route(
    candidates_a: list[ContentItem],
    candidates_b: list[ContentItem],
    planned_minutes: int,
) -> dict:
    """无豆包时的规则路由：A=脑力奥秘，B=学科奥秘"""
    video_reserve = 5
    audio_budget = max(10, planned_minutes - video_reserve)
    a_budget = max(10, int(audio_budget * 0.45))
    b_budget = audio_budget - a_budget

    block_a = _pick_by_duration(candidates_a, a_budget)
    block_b = _pick_by_duration(candidates_b, b_budget)

    return {
        "training_a_ids": [c.id for c in block_a],
        "training_b_ids": [c.id for c in block_b],
        "note": f"已按 {planned_minutes} 分钟安排脑力奥秘(A)+学科奥秘(B)（规则模式）",
    }


async def llm_route_training_blocks(
    planned_minutes: int,
    talent_primary: str | None,
    candidates_a: list[ContentItem],
    candidates_b: list[ContentItem],
    yesterday_summary: str | None = None,
) -> dict:
    if not candidates_a and not candidates_b:
        return {"training_a_ids": [], "training_b_ids": [], "note": "暂无候选音频"}

    if not candidates_a:
        return _fallback_route(candidates_a, candidates_b, planned_minutes)
    if not is_configured():
        return _fallback_route(candidates_a, candidates_b, planned_minutes)

    ctx = (
        f"学员天赋：{talent_primary or '未知'}\n"
        f"今日训练总时长：{planned_minutes} 分钟\n"
        f"training_a_candidates（脑力奥秘）：{json.dumps([_candidate_dict(c) for c in candidates_a], ensure_ascii=False)}\n"
        f"training_b_candidates（学科奥秘）：{json.dumps([_candidate_dict(c) for c in candidates_b], ensure_ascii=False)}\n"
    )
    if yesterday_summary:
        ctx += f"昨日打卡：{yesterday_summary}\n"

    try:
        raw = await chat_completion(
            system_prompt=ROUTE_SYSTEM, user_message=ctx, timeout=10
        )
    except Exception:
        return _fallback_route(candidates_a, candidates_b, planned_minutes)
    if not raw:
        return _fallback_route(candidates_a, candidates_b, planned_minutes)

    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        return _fallback_route(candidates_a, candidates_b, planned_minutes)

    valid_a = {c.id for c in candidates_a}
    valid_b = {c.id for c in candidates_b}
    try:
        data = json.loads(match.group())
        a_ids = [int(x) for x in data.get("training_a_ids", []) if int(x) in valid_a]
        b_ids = [int(x) for x in data.get("training_b_ids", []) if int(x) in valid_b]
        b_ids = [i for i in b_ids if i not in a_ids]
        if not a_ids:
            raise ValueError("empty a")
        return {
            "training_a_ids": a_ids,
            "training_b_ids": b_ids,
            "note": data.get("note") or "豆包已安排今日训练",
        }
    except (json.JSONDecodeError, ValueError, TypeError):
        return _fallback_route(candidates_a, candidates_b, planned_minutes)


def _plan_to_schedule_response(plan: TrainingPlan, *, schedule_mode: str | None = None) -> dict:
    base = _plan_to_response(plan)
    base["items"] = [_item_to_dict(i) for i in sorted(plan.items, key=lambda x: x.sort_order)]
    base["training_day"] = plan.content_index + 1
    if schedule_mode:
        base["schedule_mode"] = schedule_mode
    return base


async def schedule_training_by_duration(
    db: Session,
    child_user_id: int,
    planned_minutes: int,
    *,
    plan_date: date | None = None,
) -> dict:
    if planned_minutes < 5:
        raise TrainingError("训练时长至少 5 分钟")

    plan_date = plan_date or date.today()
    get_or_create_today_plan(db, child_user_id, plan_date)
    plan = _get_plan_by_date(db, child_user_id, plan_date)
    if not plan:
        raise TrainingError("无法创建训练计划", 500)

    assessment = get_latest_assessment(db, child_user_id)
    if not assessment or not assessment.talent_code:
        raise TrainingError("请先完成天赋测评", 403)

    talent_code = assessment.talent_code
    pool_limit = 80 if plan.content_index <= 0 else 24
    candidates_a = _build_candidates(
        db, talent_code, plan.content_index, series="chaonaoaomi", limit=pool_limit
    )
    candidates_b = _build_candidates(
        db, talent_code, plan.content_index, series="xuekeaomi", limit=pool_limit
    )
    if not candidates_a:
        raise TrainingError("暂无可用脑力奥秘音频", 503)

    route = route_training_blocks(
        plan.content_index,
        candidates_a,
        candidates_b,
        planned_minutes,
        seed_key=f"{child_user_id}:{plan_date.isoformat()}",
    )
    schedule_mode = route.get("mode", "unknown")

    id_map = {c.id: c for c in candidates_a + candidates_b}
    for old in list(plan.items):
        db.delete(old)
    db.flush()

    sort_order = 1
    video = get_talent_training_video(talent_code)
    db.add(
        TrainingItem(
            plan_id=plan.id,
            sort_order=sort_order,
            ability_type="video",
            title=video["title"],
            duration_min=5,
            video_url=video["url"],
            instructions=item_instruction("A", "video"),
            checkin_status="pending",
        )
    )
    sort_order += 1

    def _add_audios(ids: list[int], block: str) -> None:
        nonlocal sort_order
        for cid in ids:
            content = id_map.get(cid) or db.get(ContentItem, cid)
            if not content:
                continue
            db.add(
                TrainingItem(
                    plan_id=plan.id,
                    sort_order=sort_order,
                    ability_type="audio",
                    title=content.lesson_title,
                    duration_min=estimate_duration_min(content),
                    audio_url=content.play_url,
                    content_item_id=content.id,
                    instructions=item_instruction(block, "audio"),
                    checkin_status="pending",
                )
            )
            sort_order += 1

    _add_audios(route["training_a_ids"], "A")
    _add_audios(route["training_b_ids"], "B")

    plan.planned_minutes = planned_minutes
    if route.get("note"):
        plan.report_text = f"{route['note']}（计划 {planned_minutes} 分钟）"

    db.commit()
    plan = _get_plan_by_date(db, child_user_id, plan_date)
    return _plan_to_schedule_response(plan, schedule_mode=schedule_mode)
