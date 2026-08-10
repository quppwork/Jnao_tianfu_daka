"""课表地图 — 全技能 + 各阶可用/权重/重点，供排课 Agent 注入与工具返回。"""

from __future__ import annotations

from typing import Any

from app.services.training_formula_engine import CODE_SKILL, ELECTIVE_SKILLS
from config.loader import load_training_curriculum


def _code_to_name(code: str, slot_mapping: dict) -> str:
    return str(slot_mapping.get(code) or CODE_SKILL.get(code) or code)


def _codes_to_names(codes: list, slot_mapping: dict) -> list[str]:
    out: list[str] = []
    for code in codes or []:
        name = _code_to_name(str(code), slot_mapping)
        if name and name not in out:
            out.append(name)
    return out


def _weights_to_names(weights: dict, slot_mapping: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    for code, w in (weights or {}).items():
        name = _code_to_name(str(code), slot_mapping)
        try:
            out[name] = float(w)
        except (TypeError, ValueError):
            continue
    return out


def build_curriculum_overview(*, overall_tier: int = 1) -> dict[str, Any]:
    """全课表 + 各阶重点（不按当前阶裁剪）。"""
    cfg = load_training_curriculum() or {}
    slot_mapping = cfg.get("slot_mapping") or {}
    skills_cfg = cfg.get("skills") or {}
    required = list(skills_cfg.get("required") or [])
    elective = list(skills_cfg.get("elective") or [])
    decay = cfg.get("decay_rules") or {}
    key_by_tier = decay.get("key_skills") or {}
    secondary_by_tier = decay.get("secondary_skills") or {}
    tier_skills = cfg.get("tier_skills") or {}
    tier_weights = cfg.get("tier_weights") or {}

    tiers: dict[str, Any] = {}
    for t in range(1, 7):
        key = f"tier_{t}"
        tiers[key] = {
            "available": _codes_to_names(tier_skills.get(key) or [], slot_mapping),
            "weights": _weights_to_names(tier_weights.get(key) or {}, slot_mapping),
            "key_skills": _codes_to_names(key_by_tier.get(key) or [], slot_mapping),
            "secondary_skills": _codes_to_names(
                secondary_by_tier.get(key) or [], slot_mapping
            ),
        }

    # 技能大致引入阶：首次出现在 tier_skills 中的阶
    introduce_at: dict[str, int] = {}
    for t in range(1, 7):
        for name in tiers[f"tier_{t}"]["available"]:
            if name not in introduce_at:
                introduce_at[name] = t

    grade_notes_raw = cfg.get("grade_notes") or {}
    grade_notes: dict[str, list[dict]] = {}
    for band, entries in grade_notes_raw.items():
        grade_notes[str(band)] = [
            {
                "skill": e.get("skill"),
                "mark": e.get("mark"),
                "reason": e.get("reason"),
            }
            for e in (entries or [])
            if isinstance(e, dict)
        ]

    current_key = f"tier_{overall_tier}"
    current = tiers.get(current_key) or tiers.get("tier_1") or {}
    return {
        "required_skills": required,
        "elective_skills": elective,
        "elective_note": "选修由规则层按时长触发，勿写入 propose_skill_draft",
        "tiers": tiers,
        "skill_introduce_tier": introduce_at,
        "grade_notes": grade_notes,
        "student_overall_tier": overall_tier,
        "current_tier_focus": {
            "tier": overall_tier,
            "key_skills": list(current.get("key_skills") or []),
            "secondary_skills": list(current.get("secondary_skills") or []),
            "weights": dict(current.get("weights") or {}),
            "available": list(current.get("available") or []),
        },
        "hint": (
            f"学生当前 overall_tier={overall_tier}。"
            "请理解全课表各阶重点；今日草案只能从当前阶 available/selectable_now 中选。"
            "优先本阶 key_skills，可选用 secondary_skills。"
        ),
    }


def build_skill_availability(*, overall_tier: int) -> dict[str, Any]:
    """今日可排 + 全表参考 + 本阶重点 + 未解锁预览。"""
    overview = build_curriculum_overview(overall_tier=overall_tier)
    required = list(overview.get("required_skills") or [])
    introduce = overview.get("skill_introduce_tier") or {}
    focus = overview.get("current_tier_focus") or {}
    selectable = list(focus.get("available") or [])
    locked: list[dict[str, Any]] = []
    for name in required:
        intro = int(introduce.get(name) or 1)
        if name not in selectable:
            locked.append({"skill": name, "introduce_tier": intro, "selectable_now": False})

    return {
        "all_required_skills": required,
        "current_tier": overall_tier,
        "selectable_now": selectable,
        "importance_now": {
            "key": list(focus.get("key_skills") or []),
            "secondary": list(focus.get("secondary_skills") or []),
            "weights": dict(focus.get("weights") or {}),
        },
        "locked_preview": locked,
        "hint": (
            "propose_skill_draft 只能使用 selectable_now；"
            "locked_preview 仅作进度理解，不可写入草案。"
        ),
    }


def required_slot_count(rule_slots: list[str]) -> int:
    elective = set(ELECTIVE_SKILLS)
    cfg = load_training_curriculum() or {}
    elective |= set((cfg.get("skills") or {}).get("elective") or [])
    return len([s for s in rule_slots if s not in elective])
