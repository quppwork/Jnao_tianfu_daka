"""v2.0 公式引擎 — 时长 + overall_tier → 技能组合 slots

纯函数，不依赖 DB/HTTP。

用法:
    from app.services.training_formula_engine import expand_formula
    slots = expand_formula(planned_minutes=120, overall_tier=1, grade_band="primary_low")
    # → ["超脑阅读", "影像追忆", "影像追忆", "扫描速记", "高效作业"]
"""

from __future__ import annotations

from config.loader import load_training_curriculum


def _resolve_slot(slot_symbol: str, slot_mapping: dict) -> str:
    """A/B/C/D/E → 技能名；已为中文名则直接返回"""
    if slot_symbol in slot_mapping:
        return slot_mapping[slot_symbol]
    return slot_symbol  # already resolved or elective name


def _choose_slots(
    entry: dict,
    grade_band: str,
    overall_tier: int,
) -> list[str]:
    """根据学段选择对应的 slot 列表"""
    # 检查是否有学段分叉
    if "primary_school" in entry and grade_band in ("primary_low", "primary_high"):
        slots = list(entry["primary_school"])
    elif "junior_high" in entry and grade_band in ("junior", "senior"):
        slots = list(entry["junior_high"])
    elif "slots" in entry:
        slots = list(entry["slots"])
    else:
        # fallback: try primary_school
        slots = list(entry.get("primary_school", entry.get("slots", [])))

    # Apply tier_replace if overall_tier >= 3
    tier_replace = entry.get("tier_replace")
    if tier_replace and overall_tier >= 3:
        slots = _apply_tier_replace(slots, tier_replace)

    return slots


def _apply_tier_replace(slots: list[str], replace_map: dict) -> list[str]:
    """≥3阶替换：如 高效作业 → 极速学习"""
    result = []
    for s in slots:
        if s in replace_map:
            replacement = replace_map[s]
            if isinstance(replacement, list):
                result.extend(replacement)
            else:
                result.append(replacement)
        else:
            result.append(s)
    return result


def expand_formula(
    planned_minutes: int,
    overall_tier: int = 1,
    grade_band: str = "primary_low",
) -> dict:
    """将训练时长展开为技能组合列表。

    Args:
        planned_minutes: 用户选择的训练时长（分钟）
        overall_tier: 整体 Tier（默认为 1）
        grade_band: 学段（primary_low/primary_high/junior/senior）

    Returns:
        {
            "slots": ["超脑阅读", "影像追忆", ...],   # 技能名列表（有序）
            "elective_notes": [...],                 # 选修提示
            "c_note": None | "不建议",                # C 标记
            "exam_note": None | str,                 # 试卷提示
            "minutes": int,                          # 匹配的时长档位
        }
    """
    cur = load_training_curriculum()
    formulas = cur.get("duration_formula") or []
    slot_mapping = cur.get("slot_mapping") or {}
    grade_behavior = cur.get("grade_behavior") or {}

    if not formulas:
        return {"slots": [], "elective_notes": [], "c_note": None, "exam_note": None, "minutes": planned_minutes}

    # 1. 匹配时长档位
    matched = None
    for entry in formulas:
        mins = entry.get("minutes")
        if isinstance(mins, int) and planned_minutes == mins:
            matched = entry
            break
        if isinstance(mins, list) and len(mins) == 2:
            if mins[0] <= planned_minutes <= mins[1]:
                matched = entry
                break

    if matched is None:
        # fallback: closest higher bracket
        for entry in formulas:
            mins = entry.get("minutes")
            max_mins = mins if isinstance(mins, int) else (mins[1] if isinstance(mins, list) else 0)
            if isinstance(max_mins, int) and planned_minutes <= max_mins:
                matched = entry
                break

    if matched is None:
        matched = formulas[-1]  # last resort: longest formula

    # 2. 解析 slot 列表
    raw_slots = _choose_slots(matched, grade_band, overall_tier)

    # 3. 映射为技能名
    resolved = [_resolve_slot(s, slot_mapping) for s in raw_slots]

    # 4. 学段提示
    c_note = None
    if grade_band in ("junior", "senior"):
        if grade_behavior.get("junior_high_c") == "not_recommended":
            c_note = "不建议"

    # 5. 选修备注
    elective_rules = cur.get("elective_rules") or {}
    elective_notes = []
    for s in resolved:
        if s in elective_rules:
            er = elective_rules[s]
            elective_notes.append({
                "skill": s,
                "has_checkin": er.get("has_checkin", False),
                "blocks_next": er.get("blocks_next", True),
            })

    return {
        "slots": resolved,
        "elective_notes": elective_notes,
        "c_note": c_note,
        "exam_note": matched.get("exam_note"),
        "minutes": (
            matched["minutes"] if isinstance(matched["minutes"], int)
            else matched["minutes"][0]
        ),
    }
