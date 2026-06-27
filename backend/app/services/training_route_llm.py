"""框架内 LLM 排课 — 在候选池与 YAML 约束下为孩子选推课，不写死固定课表"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from app.services.doubao_client import chat_completion, is_configured
from app.services.training_curriculum import route_training_blocks

if TYPE_CHECKING:
    from app.db.models import ContentItem

ROUTE_SYSTEM = """你是 JNAO 训练排课教练。在「框架约束」内根据孩子天赋、年级、昨日训练与未完成项，个性化选择今日推送内容。
你必须遵守：
1. content_item_id 只能从 candidates 列表选取，不可编造 id
2. 优先安排 carryover_items（昨日未听完/未打卡的 plan_item），原样保留其 content_item_id
3. 总音频时长 ≤ planned_minutes（可以明显少于设定时长，不可超出）
4. 按 duration_slot 安排独立训练项数量与每项轮次（rounds）；每项可多轮，轮次用相同或不同 content_item_id
5. 结合 framework_summary 中的主线、主练/辅练 7:3、天赋权重倾向选择技能，可灵活搭配，不要机械固定
6. 可输出 placeholder_skills（如感知力、开口窍）仅占位，无 content_item_id
7. 只输出 JSON，格式：
{
  "plan_items": [
    {"content_item_id": 12, "round": 1, "role": "primary", "training_slot": 1},
    {"placeholder_skill": "感知力", "round": 1, "role": "primary", "training_slot": 1},
    {"content_item_id": 34, "round": 1, "role": "auxiliary", "training_slot": 2}
  ],
  "note": "一句话说明今日安排理由"
}
training_slot 为独立训练项编号（1..N）；role 为 primary 或 auxiliary。"""


def _fallback_from_rule_route(
    content_index: int,
    candidates_a: list[ContentItem],
    candidates_b: list[ContentItem],
    planned_minutes: int,
    seed_key: str,
    carryover: list[dict],
) -> dict:
    route = route_training_blocks(
        content_index,
        candidates_a,
        candidates_b,
        planned_minutes,
        seed_key=seed_key,
    )
    plan_items: list[dict] = []
    for cid in route.get("training_a_ids") or []:
        plan_items.append(
            {"content_item_id": cid, "round": 1, "role": "primary", "training_slot": 1}
        )
    for cid in route.get("training_b_ids") or []:
        plan_items.append(
            {"content_item_id": cid, "round": 1, "role": "auxiliary", "training_slot": 2}
        )
    for c in carryover:
        cid = c.get("content_item_id")
        if cid:
            plan_items.insert(
                0,
                {
                    "content_item_id": cid,
                    "round": 1,
                    "role": "carryover",
                    "training_slot": 1,
                    "carryover": True,
                },
            )
    return {
        "plan_items": plan_items,
        "note": route.get("note") or "规则模式排课",
        "mode": route.get("mode", "rule"),
    }


def _validate_plan_items(
    raw_items: list,
    candidate_ids: set[int],
    planned_minutes: int,
    id_duration: dict[int, int],
) -> list[dict]:
    valid: list[dict] = []
    total_min = 0
    for row in raw_items:
        if not isinstance(row, dict):
            continue
        ph = row.get("placeholder_skill")
        if ph:
            valid.append(
                {
                    "placeholder_skill": str(ph),
                    "round": int(row.get("round") or 1),
                    "role": row.get("role") or "primary",
                    "training_slot": int(row.get("training_slot") or 1),
                }
            )
            continue
        cid = row.get("content_item_id")
        try:
            cid = int(cid)
        except (TypeError, ValueError):
            continue
        if cid not in candidate_ids:
            continue
        dur = id_duration.get(cid, 5)
        if total_min + dur > planned_minutes and valid:
            continue
        total_min += dur
        valid.append(
            {
                "content_item_id": cid,
                "round": int(row.get("round") or 1),
                "role": row.get("role") or "primary",
                "training_slot": int(row.get("training_slot") or 1),
                "carryover": bool(row.get("carryover")),
            }
        )
    return valid


async def llm_route_training_plan(
    ctx: dict,
    *,
    content_index: int,
    candidates_a: list[ContentItem],
    candidates_b: list[ContentItem],
    seed_key: str,
) -> dict:
    carryover = ctx.get("carryover_items") or []
    planned = int(ctx.get("planned_minutes") or 45)
    candidate_ids = set(ctx.get("candidate_ids") or [])
    id_duration = {
        c["id"]: c.get("duration_min") or 5 for c in (ctx.get("candidates") or [])
    }

    if not ctx.get("llm_enabled") or not is_configured():
        return _fallback_from_rule_route(
            content_index, candidates_a, candidates_b, planned, seed_key, carryover
        )

    user_msg = json.dumps(
        {
            "framework_summary": ctx.get("framework_summary"),
            "talent_primary": ctx.get("talent_primary"),
            "grade": ctx.get("grade"),
            "grade_band": ctx.get("grade_band"),
            "planned_minutes": planned,
            "duration_slot": ctx.get("duration_slot"),
            "carryover_items": carryover,
            "yesterday_summary": ctx.get("yesterday_summary"),
            "candidates": ctx.get("candidates"),
        },
        ensure_ascii=False,
    )

    try:
        raw = await chat_completion(system_prompt=ROUTE_SYSTEM, user_message=user_msg, timeout=15)
    except Exception:
        return _fallback_from_rule_route(
            content_index, candidates_a, candidates_b, planned, seed_key, carryover
        )

    if not raw:
        return _fallback_from_rule_route(
            content_index, candidates_a, candidates_b, planned, seed_key, carryover
        )

    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        return _fallback_from_rule_route(
            content_index, candidates_a, candidates_b, planned, seed_key, carryover
        )

    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return _fallback_from_rule_route(
            content_index, candidates_a, candidates_b, planned, seed_key, carryover
        )

    # 强制先插入 carryover（校验池内 id）
    plan_items: list[dict] = []
    for c in carryover:
        cid = c.get("content_item_id")
        if cid and int(cid) in candidate_ids:
            plan_items.append(
                {
                    "content_item_id": int(cid),
                    "round": 1,
                    "role": "carryover",
                    "training_slot": 1,
                    "carryover": True,
                }
            )

    llm_items = _validate_plan_items(
        data.get("plan_items") or [],
        candidate_ids,
        planned,
        id_duration,
    )
    used = {p["content_item_id"] for p in plan_items if p.get("content_item_id")}
    for it in llm_items:
        cid = it.get("content_item_id")
        if cid and cid in used:
            continue
        if cid:
            used.add(cid)
        plan_items.append(it)

    if not any(p.get("content_item_id") for p in plan_items):
        return _fallback_from_rule_route(
            content_index, candidates_a, candidates_b, planned, seed_key, carryover
        )

    return {
        "plan_items": plan_items,
        "note": data.get("note") or "豆包已根据孩子情况安排今日训练",
        "mode": "llm",
    }
