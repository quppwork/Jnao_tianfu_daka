"""按用户选定时长装箱 — 独立训练项数量 × 每项轮次"""

from __future__ import annotations

from app.services.child_training_state import get_skill_position
from app.services.content_meta import estimate_duration_min
from app.services.training_curriculum import _find_lesson
from app.services.training_route_context import duration_slot
from config.loader import load_training_curriculum


def _optional_ranked(line_spec: dict, talent_primary: str | None) -> list[dict]:
    """主线 optional 列表按天赋权重排序（含占位项）"""
    ranked: list[dict] = []
    for opt in line_spec.get("optional") or []:
        if not isinstance(opt, dict) or not opt.get("skill"):
            continue
        weights = opt.get("weight_by_talent") or {}
        w = float(weights.get(talent_primary or "") or 0)
        if w <= 0:
            w = 0.25
        ranked.append(
            {
                "skill": opt["skill"],
                "weight": w,
                "push_empty_placeholder": bool(opt.get("push_empty_placeholder")),
                "content_type": opt.get("content_type") or "audio",
            }
        )
    ranked.sort(key=lambda x: -x["weight"])
    return ranked


def _append_skill_rows(
    plan_items: list[dict],
    pool: list,
    skill: str,
    stage: int,
    part: int,
    *,
    training_slot: int,
    role: str,
    rounds: int,
    force_placeholder: bool = False,
) -> None:
    found = None if force_placeholder else _find_lesson(pool, skill, stage, part)
    for round_no in range(1, max(1, rounds) + 1):
        if found:
            plan_items.append(
                {
                    "content_item_id": found.id,
                    "round": round_no,
                    "role": role,
                    "training_slot": training_slot,
                }
            )
        else:
            plan_items.append(
                {
                    "placeholder_skill": skill,
                    "round": round_no,
                    "role": role,
                    "training_slot": training_slot,
                }
            )
            break  # 占位项不重复多轮


def pack_main_line_plan_items(
    line_key: str,
    line_spec: dict,
    pool: list,
    state: dict,
    planned_minutes: int,
    talent_primary: str | None,
    carryover: list[dict] | None = None,
) -> list[dict]:
    """
    按 duration_schedule 生成 plan_items：
    - 训练项 1：主练（如超脑阅读）可多轮
    - 训练项 2..N：辅练/可选（开口窍占位、高效作业等，按天赋权重）
    """
    carryover = carryover or []
    slot_cfg = duration_slot(planned_minutes)
    num_items = int(slot_cfg.get("items") or 1)
    rounds_per_item = int(slot_cfg.get("rounds_per_item") or 1)

    plan_items: list[dict] = []
    for c in carryover:
        cid = c.get("content_item_id")
        if cid:
            plan_items.append(
                {
                    "content_item_id": int(cid),
                    "round": 1,
                    "role": "carryover",
                    "training_slot": 1,
                    "carryover": True,
                }
            )

    primary_skills = [s for s in (line_spec.get("primary_skills") or []) if s != "感知力"]
    optionals = _optional_ranked(line_spec, talent_primary)

    for slot_idx in range(1, num_items + 1):
        if slot_idx == 1 and primary_skills:
            skill = primary_skills[0]
            stage, part = get_skill_position(state, skill)
            _append_skill_rows(
                plan_items,
                pool,
                skill,
                stage,
                part,
                training_slot=slot_idx,
                role="primary",
                rounds=rounds_per_item,
            )
            continue

        opt_idx = slot_idx - 2 if primary_skills else slot_idx - 1
        if opt_idx < 0 or opt_idx >= len(optionals):
            # 时长槽位有余：重复主练下一轮（同一课多轮阅读）
            if primary_skills and slot_idx > 1:
                skill = primary_skills[0]
                stage, part = get_skill_position(state, skill)
                _append_skill_rows(
                    plan_items,
                    pool,
                    skill,
                    stage,
                    part,
                    training_slot=slot_idx,
                    role="auxiliary",
                    rounds=1,
                )
            continue

        opt = optionals[opt_idx]
        skill = opt["skill"]
        stage, part = get_skill_position(state, skill)
        force_ph = opt["push_empty_placeholder"] or opt["content_type"] == "video"
        rounds = 1 if force_ph else rounds_per_item
        _append_skill_rows(
            plan_items,
            pool,
            skill,
            stage,
            part,
            training_slot=slot_idx,
            role="auxiliary",
            rounds=rounds,
            force_placeholder=force_ph,
        )

    return plan_items


def build_schedule_note(
    line_key: str,
    line_spec: dict,
    planned_minutes: int,
    plan_items: list[dict],
    talent_primary: str | None,
) -> str:
    slot_cfg = duration_slot(planned_minutes)
    num_items = int(slot_cfg.get("items") or 1)
    rounds = int(slot_cfg.get("rounds_per_item") or 1)
    prim = [s for s in (line_spec.get("primary_skills") or []) if s != "感知力"]
    opts = [o["skill"] for o in _optional_ranked(line_spec, talent_primary)]
    parts = [
        f"主线{line_key}（{line_spec.get('name') or ''}）",
        f"时长 {planned_minutes} 分钟 → {num_items} 项训练 × 每项最多 {rounds} 轮",
    ]
    if prim:
        parts.append(f"主练 {'、'.join(prim)}")
    if opts:
        parts.append(f"辅练/可选 {'、'.join(opts)}")
    if not any(i.get("content_item_id") for i in plan_items):
        parts.append("部分内容为占位展示，待 OSS 同步后自动替换音频")
    return "；".join(parts)
