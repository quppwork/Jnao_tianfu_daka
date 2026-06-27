"""训练块排课 — 训练块 A/B/C ≠ 主线 A/B；每块仅一项；可选需孩子确认"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.child_training_state import get_skill_position
from app.services.content_meta import parse_item_meta
from app.services.training_duration_pack import _append_skill_rows, _optional_ranked
from app.services.training_route_context import duration_slot
from config.loader import load_training_curriculum

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

PERCEPTION_SKILL = "感知力"
READING_SKILL = "超脑阅读"


def _find_perception_item(pool: list) -> object | None:
    for item in pool:
        meta = parse_item_meta(item)
        if meta.get("series") == "duoyuanganzhi" or meta.get("skill") == PERCEPTION_SKILL:
            return item
        title = (item.lesson_title or "") + (meta.get("oss_key") or "")
        if "多元感知" in title:
            return item
    return None


def _append_perception(
    plan_items: list[dict],
    pool: list,
    *,
    training_slot: int,
    role: str,
) -> None:
    found = _find_perception_item(pool)
    if found:
        plan_items.append(
            {
                "content_item_id": found.id,
                "round": 1,
                "role": role,
                "training_slot": training_slot,
                "item_type": "perception",
                "skill": PERCEPTION_SKILL,
            }
        )
    else:
        plan_items.append(
            {
                "placeholder_skill": PERCEPTION_SKILL,
                "round": 1,
                "role": role,
                "training_slot": training_slot,
                "item_type": "perception",
            }
        )


def _append_single_skill(
    plan_items: list[dict],
    pool: list,
    state: dict,
    skill: str,
    *,
    training_slot: int,
    role: str,
    rounds: int = 1,
    force_placeholder: bool = False,
) -> None:
    if skill == PERCEPTION_SKILL:
        _append_perception(plan_items, pool, training_slot=training_slot, role=role)
        return
    stage, part = get_skill_position(state, skill)
    _append_skill_rows(
        plan_items,
        pool,
        skill,
        stage,
        part,
        training_slot=training_slot,
        role=role,
        rounds=max(1, rounds),
        force_placeholder=force_placeholder,
    )


def _line_blocks(line_spec: dict) -> list[dict]:
    blocks = line_spec.get("training_blocks")
    if isinstance(blocks, list) and blocks:
        return blocks
    primary = [s for s in (line_spec.get("primary_skills") or []) if s != PERCEPTION_SKILL]
    aux = list(line_spec.get("auxiliary_skills") or line_spec.get("optional_skills") or [])
    out: list[dict] = []
    if primary:
        out.append(
            {
                "slot": 1,
                "role": "primary",
                "skills": primary,
                "after_skills": [PERCEPTION_SKILL] if READING_SKILL in primary else [],
            }
        )
    if aux:
        out.append(
            {
                "slot": 2,
                "role": "synergy",
                "skills": aux,
                "after_skills": [PERCEPTION_SKILL] if READING_SKILL in aux else [],
            }
        )
    return out


def _flatten_mandatory_blocks(blocks: list[dict]) -> tuple[list[dict], list[dict]]:
    """将 YAML 块展开为「每块一项」；可选块单独返回"""
    mandatory: list[dict] = []
    optional_markers: list[dict] = []
    for blk in blocks:
        if blk.get("pick") == "optional_weighted":
            optional_markers.append(blk)
            continue
        skills = list(blk.get("skills") or [])
        after = list(blk.get("after_skills") or [])
        base = {
            "role": blk.get("role") or "primary",
            "synergy_label": blk.get("synergy_label"),
        }
        for sk in skills:
            mandatory.append({**base, "skill": sk})
        for sk in after:
            role = "perception" if sk == PERCEPTION_SKILL else base.get("role") or "primary"
            mandatory.append({**base, "role": role, "skill": sk})
    return mandatory, optional_markers


def build_optional_offers(
    line_spec: dict,
    talent_primary: str | None,
    optional_markers: list[dict] | None = None,
) -> list[dict]:
    markers = optional_markers or [
        b for b in _line_blocks(line_spec) if b.get("pick") == "optional_weighted"
    ]
    if not markers:
        return []
    ranked = _optional_ranked(line_spec, talent_primary)
    if not ranked:
        return []
    top_weight = max(o["weight"] for o in ranked)
    requires = bool(markers[0].get("requires_child_confirm", True))
    offers: list[dict] = []
    for opt in ranked:
        w = opt["weight"]
        offers.append(
            {
                "skill": opt["skill"],
                "weight": w,
                "suggested": w >= top_weight * 0.85,
                "content_type": opt["content_type"],
                "requires_confirm": requires,
                "status": "pending",
            }
        )
    return offers


def normalize_plan_items_by_duration(
    plan_items: list[dict],
    planned_minutes: int,
) -> list[dict]:
    """按时长表限制训练块数，且每个 training_slot 仅保留一项（兼容旧 LLM/规则叠项）"""
    slot_cfg = duration_slot(planned_minutes)
    max_blocks = int(slot_cfg.get("items") or 1)

    carryover = [r for r in plan_items if r.get("carryover")]
    rest = [r for r in plan_items if not r.get("carryover")]

    by_slot: dict[int, dict] = {}
    for row in rest:
        slot = int(row.get("training_slot") or 1)
        if slot not in by_slot:
            by_slot[slot] = dict(row)

    ordered_rest = [by_slot[k] for k in sorted(by_slot.keys())]

    combined: list[dict] = []
    for c in carryover[:max_blocks]:
        combined.append(dict(c))
    remaining = max_blocks - len(combined)
    if remaining > 0:
        combined.extend(ordered_rest[:remaining])

    out: list[dict] = []
    for idx, row in enumerate(combined, start=1):
        item = dict(row)
        item["training_slot"] = idx
        item["round"] = 1
        out.append(item)
    return out


def build_main_line_block_plan(
    line_key: str,
    line_spec: dict,
    pool: list,
    state: dict,
    planned_minutes: int,
    talent_primary: str | None,
    carryover: list[dict] | None = None,
) -> dict:
    """按 YAML training_blocks + 时长表生成 plan_items（每 training_slot 仅一项）"""
    carryover = carryover or []
    slot_cfg = duration_slot(planned_minutes)
    num_blocks = int(slot_cfg.get("items") or 1)

    plan_items: list[dict] = []
    carryover_slots = 0
    for c in carryover:
        cid = c.get("content_item_id")
        if cid and carryover_slots < num_blocks:
            plan_items.append(
                {
                    "content_item_id": int(cid),
                    "round": 1,
                    "role": "carryover",
                    "training_slot": carryover_slots + 1,
                    "carryover": True,
                }
            )
            carryover_slots += 1

    blocks = _line_blocks(line_spec)
    mandatory, optional_markers = _flatten_mandatory_blocks(blocks)
    optional_offers = build_optional_offers(line_spec, talent_primary, optional_markers)

    slots_left = num_blocks - carryover_slots
    for i in range(slots_left):
        slot_idx = carryover_slots + i + 1
        if i < len(mandatory):
            blk = mandatory[i]
            skill = blk["skill"]
            role = blk.get("role") or "primary"
            _append_single_skill(
                plan_items,
                pool,
                state,
                skill,
                training_slot=slot_idx,
                role=role,
                rounds=1,
            )
            continue

        if mandatory:
            first = mandatory[0]
            skill = first["skill"]
            if skill != PERCEPTION_SKILL:
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

    plan_items = normalize_plan_items_by_duration(plan_items, planned_minutes)

    return {
        "plan_items": plan_items,
        "optional_offers": optional_offers,
    }


def build_schedule_note_for_blocks(
    line_key: str,
    line_spec: dict,
    planned_minutes: int,
    plan_items: list[dict],
    talent_primary: str | None,
) -> str:
    slot_cfg = duration_slot(planned_minutes)
    num_blocks = int(slot_cfg.get("items") or 1)
    rounds = int(slot_cfg.get("rounds_per_item") or 1)
    blocks = _line_blocks(line_spec)
    mandatory, _ = _flatten_mandatory_blocks(blocks)
    block_desc = []
    for i, blk in enumerate(mandatory[:num_blocks], start=1):
        label = blk.get("synergy_label") or blk.get("role") or ""
        skill = blk.get("skill") or ""
        if skill:
            block_desc.append(f"块{i}{'(' + label + ')' if label else ''}:{skill}")
    opt_skills = [o["skill"] for o in build_optional_offers(line_spec, talent_primary)]
    parts = [
        f"主线{line_key}（{line_spec.get('name') or ''}）",
        f"时长 {planned_minutes} 分钟 → {num_blocks} 个训练块 × 主项最多 {rounds} 轮",
    ]
    if block_desc:
        parts.append("；".join(block_desc))
    if opt_skills:
        parts.append(f"可选（需确认）:{'、'.join(opt_skills)}")
    return "；".join(parts)
