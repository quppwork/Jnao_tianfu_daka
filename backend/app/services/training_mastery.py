"""v2.0 打卡量化 → 达标判定 → Tier 晋级 → OSS 推进

核心规则：
- 连续3次达标 → 技能 Tier += 1，consecutive_pass 重置
- 不达标 → consecutive_pass 重置为 0（严格连续）
- 各技能独立判定
- OSS stage/part 随达标推进（有则取、无则跳）
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from app.services.child_training_state import (
    advance_skill_tier,
    bump_consecutive_pass,
    get_consecutive_pass,
    get_skill_oss_position,
    get_skill_tier,
    overall_tier,
    reset_consecutive_pass,
    set_skill_oss_position,
    state_summary,
)
from app.services.content_meta import parse_item_meta
from app.services.talent_content_pool import get_talent_content_pool
from config.loader import load_training_tier_thresholds

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.db.models import ChildUser, TrainingPlan


# ── 辅助 ──────────────────────────────────────────

def _parse_num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        m = re.search(r"[\d.]+", str(value))
        return float(m.group()) if m else None


def _grade_band(grade: str | None) -> str | None:
    th = load_training_tier_thresholds()
    bands = th.get("grade_bands") or {}
    g = (grade or "").strip()
    if not g:
        return None
    for band, grades in bands.items():
        if g in grades:
            return band
    return None


def _cards_for_skill(cards: list[dict], skill: str) -> list[dict]:
    return [c for c in cards or [] if (c.get("name") or "").strip() == skill]


def _card_field_num(card: dict, *fields: str) -> float | None:
    for key in fields:
        val = _parse_num(card.get(key))
        if val is not None:
            return val
    return None


# ── 查找阈值 ──────────────────────────────────────

def get_skill_threshold(skill: str, tier: int, grade_band: str | None) -> dict | None:
    """查找指定技能在指定 Tier×学段下的达标阈值。

    Returns:
        None 表示该技能此 Tier 无需考核（如扫描速记 Tier 1）
        dict 包含 type + 具体阈值字段
    """
    th = load_training_tier_thresholds()
    skill_thresholds = (th.get("tier_thresholds") or {}).get(skill) or {}
    tier_thresholds = skill_thresholds.get(tier)
    if not tier_thresholds:
        return None

    # 优先按学段查
    band = grade_band or "primary_low"
    entry = tier_thresholds.get(band)
    if entry is not None:
        return entry

    # fallback: "all" key
    entry = tier_thresholds.get("all")
    return entry


# ── 单卡判定 ──────────────────────────────────────

def evaluate_card(
    skill: str,
    tier: int,
    grade_band: str | None,
    card: dict,
) -> dict:
    """判定单张打卡卡片是否达标。

    Returns:
        { passed: bool, threshold: dict|null, detail: str, skill, tier, rule_type }
    """
    threshold = get_skill_threshold(skill, tier, grade_band)
    base: dict[str, Any] = {
        "skill": skill,
        "tier": tier,
        "grade_band": grade_band,
        "threshold": threshold,
        "passed": False,
        "rule_type": None,
        "detail": "",
    }

    if threshold is None:
        base["passed"] = True  # 无需考核 → 视为通过（推进 OSS）
        base["detail"] = f"「{skill}」Tier {tier} 无需考核"
        return base

    rtype = threshold.get("type")
    base["rule_type"] = rtype

    if rtype == "wpm":
        words = _card_field_num(card, "wordCount", "words")
        minutes = _card_field_num(card, "time", "minutes") or 0.0
        required_words = int(threshold.get("words") or 0)
        required_minutes = int(threshold.get("minutes") or 1)

        if not words or minutes <= 0:
            base["detail"] = "请填写用时（分钟）和完成字数"
            return base

        wpm = words / minutes
        required_wpm = required_words / required_minutes
        base["wpm"] = round(wpm, 1)
        base["required_wpm"] = round(required_wpm, 1)
        base["passed"] = wpm >= required_wpm
        base["detail"] = (
            f"达标：{minutes:g}分钟{words:g}字（{base['wpm']}字/分 ≥ {base['required_wpm']}字/分）"
            if base["passed"]
            else f"未达标：需≥{base['required_wpm']}字/分（当前{base['wpm']}字/分）"
        )
        return base

    if rtype == "recall":
        words = _card_field_num(card, "wordCount", "words")
        acc = _card_field_num(card, "accuracy", "accuracy_pct") or 0
        required_words = int(threshold.get("words") or 0)
        required_acc = int(threshold.get("accuracy_pct") or 0)

        base["words"] = words
        base["required_words"] = required_words
        base["accuracy_pct"] = acc
        base["required_accuracy_pct"] = required_acc
        words_ok = words is not None and words >= required_words
        acc_ok = acc >= required_acc
        base["passed"] = words_ok and acc_ok
        base["detail"] = (
            f"达标：{words:g}字/{acc:g}%准确度"
            if base["passed"]
            else f"未达标：需≥{required_words}字 + ≥{required_acc}%准确度（当前{words or 0:g}字/{acc:g}%）"
        )
        return base

    if rtype == "memory":
        words = _card_field_num(card, "wordCount", "words") or 0
        minutes = _card_field_num(card, "time", "minutes") or 1
        reverse = card.get("reverseRecite", False)
        required_wpm = int(threshold.get("words_per_min") or 0)
        require_reverse = bool(threshold.get("reverse_recite", False))

        actual_wpm = words / max(minutes, 0.01)
        base["words_per_min"] = round(actual_wpm, 1)
        base["required_words_per_min"] = required_wpm
        wpm_ok = actual_wpm >= required_wpm
        reverse_ok = not require_reverse or reverse is True
        base["passed"] = wpm_ok and reverse_ok
        base["detail"] = (
            f"达标：{actual_wpm:.0f}字/分 + 倒背{'✓' if reverse else '✗'}"
            if base["passed"]
            else f"未达标：需≥{required_wpm}字/分{' + 可倒背' if require_reverse else ''}"
        )
        return base

    if rtype == "speed_calc":
        # 极速运算：判定"完成"即可
        completed = card.get("completed", card.get("correctCount") is not None)
        base["passed"] = bool(completed)
        base["detail"] = "已完成" if completed else "未完成"
        return base

    if rtype == "program":
        # 极速学习：项目完成判定
        completed = card.get("completed", False)
        base["passed"] = bool(completed)
        base["detail"] = "项目已完成" if completed else "项目未完成"
        return base

    # 未知题型 → 默认通过
    base["passed"] = True
    base["detail"] = f"未知题型 {rtype}，默认通过"
    return base


# ── 多卡取优 ──────────────────────────────────────

def evaluate_skill_any_card(
    skill: str,
    tier: int,
    grade_band: str | None,
    cards: list[dict],
) -> dict:
    """同技能多轮打卡：任一轮达标即为达标，返回最优明细。"""
    matching = _cards_for_skill(cards, skill)
    if not matching:
        return {
            "skill": skill,
            "tier": tier,
            "passed": False,
            "threshold": None,
            "detail": f"打卡中未找到「{skill}」记录",
        }
    best: dict | None = None
    for card in matching:
        result = evaluate_card(skill, tier, grade_band, card)
        if result.get("passed"):
            return result
        if best is None:
            best = result
    return best or {"skill": skill, "tier": tier, "passed": False, "detail": "未达标"}


# ── OSS 推进 ──────────────────────────────────────

def _next_lesson_in_pool(
    pool: list,
    skill: str | None,
    current_stage: int,
    current_part: int,
) -> tuple[int, int] | None:
    """在内容池中查找指定技能的下一个 (stage, part)"""
    from app.services.training_curriculum import _find_lesson

    if not skill:
        return None

    # 找同 stage 下一个 part
    found = _find_lesson(pool, skill, current_stage, current_part + 1)
    if found:
        return current_stage, current_part + 1

    # 找下一个 stage 第一个 part
    found = _find_lesson(pool, skill, current_stage + 1, 1)
    if found:
        return current_stage + 1, 1

    return None


def bump_oss_after_pass(
    db: Session,
    talent_code: int,
    state: dict,
    skill: str,
) -> bool:
    """达标后推进 OSS stage/part。返回 True 表示推进成功，False 表示 OSS 池已耗尽。"""
    pool = get_talent_content_pool(db, talent_code)
    stage, part = get_skill_oss_position(state, skill)
    nxt = _next_lesson_in_pool(pool, skill, stage, part)
    if nxt:
        set_skill_oss_position(state, skill, nxt[0], nxt[1])
        return True
    return False


# ── 主线：打卡处理 ────────────────────────────────

def process_checkin_progress(
    db: Session,
    child: ChildUser,
    plan: TrainingPlan,
    cards: list[dict],
    *,
    talent_code: int,
    grade: str | None,
) -> dict:
    """打卡提交后：遍历所有技能 → 判定达标 → 更新连续计数 → 处理晋级。

    Returns:
        {
            overall_tier: int,
            skill_results: { skill_name: { tier_before, tier_after, passed, tier_advanced, oss_advanced, ... } },
        }
    """
    from app.services.child_training_state import get_training_progress, save_training_progress

    state = get_training_progress(child)
    grade_band = _grade_band(grade)

    # 收集本方案所有打卡卡片（含即将写入的 cards）
    all_cards = _collect_plan_checkin_cards(db, child.id, plan.id, extra_cards=cards)

    # 汇总今天涉及的所有技能
    skills_today = _extract_skills_from_plan(plan, db)

    skill_results: dict[str, dict] = {}

    for skill in sorted(skills_today):
        if not skill or skill == "训练":
            continue

        tier_before = get_skill_tier(state, skill)
        eval_result = evaluate_skill_any_card(skill, tier_before, grade_band, all_cards)

        passed = bool(eval_result.get("passed"))
        tier_advanced = False
        oss_advanced = False
        tier_after = tier_before

        if passed:
            # 达标 → 连续计数 +1
            bump_consecutive_pass(state, skill)
            # 尝试推进 OSS
            oss_advanced = bump_oss_after_pass(db, talent_code, state, skill)
            # 检查是否达到晋级条件
            if get_consecutive_pass(state, skill) >= 3:
                tier_after = advance_skill_tier(state, skill)
                tier_advanced = True
        else:
            # 不达标 → 计数重置
            reset_consecutive_pass(state, skill)

        skill_results[skill] = {
            "tier_before": tier_before,
            "tier_after": tier_after,
            "passed": passed,
            "consecutive_pass": get_consecutive_pass(state, skill),
            "tier_advanced": tier_advanced,
            "oss_advanced": oss_advanced,
            "threshold_detail": eval_result,
        }

    # 保存
    save_training_progress(db, child, state)

    return {
        "overall_tier": overall_tier(state),
        "skill_results": skill_results,
        "summary": state_summary(state),
    }


def _collect_plan_checkin_cards(
    db: Session,
    child_user_id: int,
    plan_id: int,
    *,
    extra_cards: list[dict] | None = None,
) -> list[dict]:
    """汇总本方案当日全部打卡卡片"""
    from sqlalchemy import select
    from app.db.models import TrainingRecord

    merged: list[dict] = []
    rows = db.scalars(
        select(TrainingRecord).where(
            TrainingRecord.child_user_id == child_user_id,
            TrainingRecord.plan_id == plan_id,
        )
    ).all()
    for rec in rows:
        fj = rec.files_json if isinstance(rec.files_json, list) else []
        merged.extend(fj)
    if extra_cards:
        merged.extend(extra_cards)
    return merged


def _extract_skills_from_plan(plan: TrainingPlan, db: Session) -> set[str]:
    """从 plan.items 中提取涉及的技能名"""
    skills: set[str] = set()
    for item in plan.items:
        if item.instructions and item.instructions.strip().startswith("{"):
            import json
            try:
                payload = json.loads(item.instructions)
                sk = payload.get("skill")
                if sk:
                    skills.add(sk)
            except json.JSONDecodeError:
                pass
        if item.content_item_id:
            from app.db.models import ContentItem
            ci = db.get(ContentItem, item.content_item_id)
            if ci:
                meta = parse_item_meta(ci)
                sk = meta.get("skill")
                if sk:
                    skills.add(sk)
    return skills
