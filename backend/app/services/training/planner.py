"""今日修炼排课门面：分群 → 方案模式 → 槽位配方。"""

from __future__ import annotations

from typing import Any, Mapping

from sqlalchemy.orm import Session

from app.db.models import ChildUser
from app.services.training.cohort import build_cohort_context, cohort_to_dict
from app.services.training_formula_engine import HistoryEntry, expand_formula
from config.loader import load_training_recipes


def _pick_fixed_row(table: list, planned_minutes: int) -> dict | None:
    m = max(0, int(planned_minutes))
    for row in table or []:
        if not isinstance(row, dict):
            continue
        if m <= int(row.get("minutes_max") or 0):
            return row
    return None


def _fixed_table(key: str) -> list:
    recipes = load_training_recipes()
    table = recipes.get(key)
    if isinstance(table, dict) and table.get("use"):
        return recipes.get(str(table["use"])) or []
    return table if isinstance(table, list) else []


def _academic_subject_slots(subject_ratio: float) -> list[str]:
    recipes = load_training_recipes()
    cfg = recipes.get("academic_subject_slots") or {}
    if subject_ratio >= 0.7:
        return list(cfg.get("heavy") or ["学科方案", "三错一讲", "学科复盘"])
    if subject_ratio >= 0.4:
        return list(cfg.get("standard") or ["学科方案", "三错一讲"])
    if subject_ratio > 0:
        return list(cfg.get("light") or ["学科方案"])
    return []


def _weight_expand(
    planned_minutes: int,
    *,
    overall_tier: int,
    grade_band: str,
    skill_tiers: Mapping[str, int] | None,
    history: tuple[HistoryEntry, ...] | None,
) -> dict[str, Any]:
    return expand_formula(
        planned_minutes,
        overall_tier=overall_tier,
        grade_band=grade_band,
        skill_tiers=dict(skill_tiers or {}),
        history=history or (),
    )


def _from_fixed_row(
    *,
    meta: dict,
    row: dict,
    strategy: str,
    reason: str,
) -> dict[str, Any]:
    slots = [str(s) for s in (row.get("slots") or []) if s]
    offers = [str(s) for s in (row.get("elective_offers") or []) if s]
    return {
        **meta,
        "recipe_id": str(row.get("recipe_id") or "fixed"),
        "strategy": strategy,
        "schedule_engine": "fixed",
        "slots": slots,
        "extras": [],
        "bundle_skills": [],
        "annotations": [],
        "elective_offers": offers,
        "c_note": None,
        "exam_note": None,
        "elective_notes": [],
        "bundle_id": None,
        "bundle_note": "",
        "grade_notes": [],
        "reason": reason,
    }


def _append_academic_slots(result: dict[str, Any], subject_ratio: float) -> dict[str, Any]:
    subjects = _academic_subject_slots(subject_ratio)
    if not subjects:
        return result
    slots = list(result.get("slots") or [])
    for sk in subjects:
        if sk not in slots:
            slots.append(sk)
    annotations = list(result.get("annotations") or [])
    annotations.append(f"学业学科占比{int(subject_ratio * 100)}%")
    out = dict(result)
    out["slots"] = slots
    out["annotations"] = annotations
    out["subject_slots"] = subjects
    return out


def plan_today_slots(
    child: ChildUser | None,
    planned_minutes: int,
    *,
    overall_tier: int,
    grade_band: str,
    skill_tiers: Mapping[str, int] | None = None,
    history: tuple[HistoryEntry, ...] | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    ctx = build_cohort_context(child, planned_minutes=planned_minutes, db=db)
    meta = cohort_to_dict(ctx)
    meta["overall_grade_used"] = overall_tier
    variant = ctx.recipe_variant

    # ── 体验（30–90 固定表；超时落新学员固定表）──
    if ctx.cohort == "experience" and ctx.plan_mode in ("standard", "custom", "academic"):
        table_key = (
            "experience_advanced"
            if variant in ("advanced", "adult", "custom")
            else "experience_standard"
        )
        row = _pick_fixed_row(_fixed_table(table_key), planned_minutes)
        if row:
            out = _from_fixed_row(
                meta=meta,
                row=row,
                strategy="experience_fixed",
                reason=f"体验学员 · {row.get('recipe_id')}",
            )
            if ctx.plan_mode == "academic":
                out = _append_academic_slots(out, ctx.subject_ratio)
            return out
        # >90 分钟：按新学员日表继续（仍改变默认清单，不回旧权重）
        row = _pick_fixed_row(_fixed_table("new_student_fixed"), planned_minutes)
        if row:
            out = _from_fixed_row(
                meta={**meta, "cohort": "new_student"},
                row=row,
                strategy="new_student_fixed",
                reason=f"体验超时 → 新学员固定表 · {row.get('recipe_id')}",
            )
            if ctx.plan_mode == "academic":
                out = _append_academic_slots(out, ctx.subject_ratio)
            return out

    # ── 新学员：默认固定日表（开发设定第二部分）──
    if ctx.cohort == "new_student" and variant in ("fixed", "standard", "advanced"):
        table_key = (
            "regular_advanced"
            if variant == "advanced"
            else "new_student_fixed"
        )
        row = _pick_fixed_row(_fixed_table(table_key), planned_minutes)
        if row:
            out = _from_fixed_row(
                meta=meta,
                row=row,
                strategy="new_student_fixed",
                reason=f"新学员固定表 · {row.get('recipe_id')}",
            )
            if ctx.plan_mode == "academic":
                out = _append_academic_slots(out, ctx.subject_ratio)
            return out

    # ── 老学员强化固定表 ──
    if ctx.cohort == "regular" and variant == "advanced" and ctx.plan_mode == "standard":
        row = _pick_fixed_row(_fixed_table("regular_advanced"), planned_minutes)
        if row:
            return _from_fixed_row(
                meta=meta,
                row=row,
                strategy="regular_advanced_fixed",
                reason=f"老学员强化 · {row.get('recipe_id')}",
            )

    # ── 火箭 / 会场 / 黑马 ──
    if ctx.plan_mode in ("rocket", "blackhorse") or ctx.cohort in (
        "rocket",
        "blackhorse",
        "venue_new",
    ):
        table_key = (
            "blackhorse_standard"
            if ctx.plan_mode == "blackhorse" or ctx.cohort == "blackhorse"
            else "rocket_standard"
        )
        if planned_minutes >= 180:
            row = _pick_fixed_row(_fixed_table(table_key), planned_minutes)
            if row:
                out = _from_fixed_row(
                    meta=meta,
                    row=row,
                    strategy=f"{table_key}_fixed",
                    reason=f"营期方案 · {row.get('recipe_id')}",
                )
                if ctx.plan_mode == "academic" or ctx.subject_ratio > 0:
                    out = _append_academic_slots(out, max(ctx.subject_ratio, 0.5))
                return out

    # ── 默认权重引擎 ──
    formula = _weight_expand(
        planned_minutes,
        overall_tier=overall_tier,
        grade_band=grade_band,
        skill_tiers=skill_tiers,
        history=history,
    )
    recipe_id = "weight_v3"
    reason = formula.get("reason") or "权重排课"
    if ctx.plan_mode == "academic":
        recipe_id = "academic_brain_weight_v3"
        reason = (
            f"学业规划：脑力{int(ctx.brain_ratio * 100)}%/"
            f"学科{int(ctx.subject_ratio * 100)}%"
        )

    result = {
        **meta,
        "recipe_id": recipe_id,
        "strategy": formula.get("strategy") or "weight_based",
        "schedule_engine": formula.get("schedule_engine")
        or ("bundle" if formula.get("bundle_id") else "weight"),
        "slots": list(formula.get("slots") or []),
        "extras": list(formula.get("extras") or []),
        "bundle_skills": list(formula.get("bundle_skills") or []),
        "annotations": list(formula.get("annotations") or []),
        "elective_offers": [],
        "c_note": formula.get("c_note"),
        "exam_note": formula.get("exam_note"),
        "elective_notes": formula.get("elective_notes", []),
        "bundle_id": formula.get("bundle_id"),
        "bundle_note": formula.get("bundle_note"),
        "grade_notes": formula.get("grade_notes", []),
        "reason": reason,
        "overall_grade_used": overall_tier,
    }
    if ctx.plan_mode == "academic" or ctx.subject_ratio > 0:
        result = _append_academic_slots(result, ctx.subject_ratio)
    return result
