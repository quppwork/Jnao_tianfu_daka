"""打卡量化 → 达标判定 → 技能课序 / 主线进阶"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from app.services.child_training_state import (
    bump_main_line_session,
    get_skill_position,
    main_line_index,
    set_pending_main_line_advance,
    set_skill_position,
)
from app.services.content_meta import parse_item_meta
from app.services.talent_content_pool import get_talent_content_pool
from app.services.training_carryover import auto_complete_skipped_checkin_items
from app.services.training_curriculum import _find_lesson
from config.loader import load_training_advance_rules, load_training_curriculum

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.db.models import ChildUser, TrainingPlan


def _parse_num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        m = re.search(r"[\d.]+", str(value))
        return float(m.group()) if m else None


def _grade_band(grade: str | None) -> str | None:
    cfg = load_training_curriculum().get("grade_bands") or {}
    g = (grade or "").strip()
    if not g:
        return None
    for band, grades in cfg.items():
        if g in grades:
            return band
    return None


def _cards_for_skill(cards: list[dict], skill: str) -> list[dict]:
    return [c for c in cards or [] if (c.get("name") or "").strip() == skill]


def _card_for_skill(cards: list[dict], skill: str) -> dict | None:
    matched = _cards_for_skill(cards, skill)
    return matched[0] if matched else None


def _evaluate_advance_rule_any(
    rule_key: str, cards: list[dict], skill: str, grade_band: str | None
) -> dict | None:
    """多轮打卡：同技能任一轮达标即视为达标，返回最优明细"""
    matching = _cards_for_skill(cards, skill)
    if not matching:
        return None
    last_detail: dict | None = None
    for card in matching:
        detail = evaluate_advance_rule(rule_key, card, grade_band)
        last_detail = detail
        if detail.get("met"):
            return detail
    return last_detail


def _card_field_num(card: dict, *fields: str) -> float | None:
    for key in fields:
        val = _parse_num(card.get(key))
        if val is not None:
            return val
    return None


def evaluate_advance_rule(rule_key: str, card: dict, grade_band: str | None) -> dict:
    """根据打卡卡片的用时/字数等字段，返回是否达标及明细（供 API 回传）。"""
    rules = (load_training_advance_rules().get("rules") or {})
    spec = rules.get(rule_key) or {}
    rtype = spec.get("type")
    skill = spec.get("skill") or ""
    base: dict[str, Any] = {
        "rule_key": rule_key,
        "skill": skill,
        "rule_type": rtype,
        "met": False,
    }
    if rtype == "words_per_minute":
        words = _card_field_num(card, "wordCount", "content", "words")
        minutes = _card_field_num(card, "time", "minutes") or 0.0
        required_wpm = float(spec.get("min_words") or 1000)
        base["minutes"] = minutes
        base["words"] = words
        if not words or minutes <= 0:
            base["message"] = "请填写用时（分钟）和完成字数"
            return base
        wpm = words / minutes
        base["words_per_minute"] = round(wpm, 1)
        base["required_wpm"] = required_wpm
        base["met"] = wpm >= required_wpm
        base["message"] = (
            f"达标：{minutes:g}分钟{words:g}字（{base['words_per_minute']}字/分）"
            if base["met"]
            else f"未达标：需≥{required_wpm:g}字/分（当前{base['words_per_minute']}字/分）"
        )
        return base
    if rtype == "grade_min_words":
        targets = load_training_advance_rules().get("grade_word_targets") or {}
        band = grade_band or "primary_low"
        need = int(targets.get(band) or targets.get("primary_low") or 300)
        field = spec.get("field") or "content"
        words = _card_field_num(card, field, "wordCount", "content", "words")
        base["grade_band"] = band
        base["required_words"] = need
        base["words"] = words
        base["met"] = words is not None and words >= need
        base["message"] = (
            f"达标：完成{words:g}字（{band}段要求≥{need}字）"
            if base["met"]
            else f"未达标：{band}段需≥{need}字（当前{words or 0:g}字）"
        )
        return base
    if rtype == "accuracy_pct":
        field = spec.get("field") or "accuracy"
        acc = _card_field_num(card, field)
        min_pct = float(spec.get("min_pct") or 70)
        base["accuracy_pct"] = acc
        base["required_pct"] = min_pct
        base["met"] = acc is not None and acc >= min_pct
        base["message"] = (
            f"达标：正确率{acc:g}%"
            if base["met"]
            else f"未达标：需正确率≥{min_pct:g}%（当前{acc or 0:g}%）"
        )
        return base
    base["message"] = "未知进阶规则"
    return base


def _rule_met(rule_key: str, card: dict, grade_band: str | None) -> bool:
    return bool(evaluate_advance_rule(rule_key, card, grade_band).get("met"))


def _next_lesson_in_pool(pool: list, skill: str, stage: int, part: int) -> tuple[int, int] | None:
    if _find_lesson(pool, skill, stage, part + 1):
        return stage, part + 1
    if _find_lesson(pool, skill, stage + 1, 1):
        return stage + 1, 1
    return None


def evaluate_main_line_advance(state: dict, cards: list[dict], grade_band: str | None) -> bool:
    return build_main_line_advance_eval(state, cards, grade_band).get("advance_met", False)


def build_main_line_advance_eval(state: dict, cards: list[dict], grade_band: str | None) -> dict:
    """当前主线进阶判定（含规则明细，未改 state）。"""
    cur = load_training_curriculum()
    adv_cfg = cur.get("main_line_advance") or {}
    main_line = state.get("main_line") or "A"
    out: dict[str, Any] = {
        "main_line_from": main_line,
        "main_line_to": None,
        "advance_rule_key": None,
        "advance_met": False,
        "advance_detail": None,
    }
    if not adv_cfg.get("enabled", True):
        out["message"] = "主线自动进阶已关闭"
        return out
    min_sessions = int(adv_cfg.get("min_sessions_on_line") or 0)
    if min_sessions > 0 and int(state.get("main_line_sessions") or 0) < min_sessions:
        out["message"] = f"主线 {main_line} 需累计训练 {min_sessions} 次后再判定进阶"
        return out
    spec = (cur.get("main_lines") or {}).get(main_line) or {}
    rule_key = spec.get("advance_rule")
    if not rule_key:
        out["message"] = f"主线 {main_line} 无进阶规则"
        return out
    out["advance_rule_key"] = rule_key
    out["main_line_to"] = spec.get("advance_to")
    rules = (load_training_advance_rules().get("rules") or {})
    skill = (rules.get(rule_key) or {}).get("skill")
    if not skill:
        out["message"] = f"进阶规则 {rule_key} 未配置技能"
        return out
    detail = _evaluate_advance_rule_any(rule_key, cards, skill, grade_band)
    if not detail:
        out["message"] = f"打卡中未找到「{skill}」训练记录"
        return out
    out["advance_detail"] = detail
    out["advance_met"] = bool(detail.get("met"))
    out["message"] = detail.get("message") or ""
    return out


def collect_plan_checkin_cards(
    db: Session,
    child_user_id: int,
    plan_id: int,
    *,
    extra_cards: list[dict] | None = None,
) -> list[dict]:
    """汇总本方案当日全部打卡卡片（含多轮训练）；extra_cards 用于尚未 flush 的新记录"""
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


def _apply_advance_eval_to_state(state: dict, plan: TrainingPlan, advance_eval: dict) -> None:
    if advance_eval.get("advance_met"):
        to_line = advance_eval.get("main_line_to")
        if to_line:
            set_pending_main_line_advance(state, str(to_line))
        auto_complete_skipped_checkin_items(plan)
    else:
        state["pending_main_line_to"] = None


def bump_skill_after_checkin(db: Session, talent_code: int, state: dict, skill: str) -> None:
    pool = get_talent_content_pool(db, talent_code)
    stage, part = get_skill_position(state, skill)
    nxt = _next_lesson_in_pool(pool, skill, stage, part)
    if nxt:
        set_skill_position(state, skill, nxt[0], nxt[1])
    else:
        set_skill_position(state, skill, stage, part)


def process_checkin_progress(
    db: Session,
    child: ChildUser,
    plan: TrainingPlan,
    cards: list[dict],
    *,
    talent_code: int,
    grade: str | None,
) -> dict:
    from app.services.child_training_state import get_training_progress, save_training_progress

    state = get_training_progress(child)
    grade_band = _grade_band(grade)
    bumped_skills: list[str] = []
    main_line_before = state.get("main_line") or "A"
    advance_cards = collect_plan_checkin_cards(db, child.id, plan.id, extra_cards=cards)
    advance_eval = build_main_line_advance_eval(state, advance_cards, grade_band)

    _apply_advance_eval_to_state(state, plan, advance_eval)

    skills_today: set[str] = set()
    for item in plan.items:
        if item.instructions and item.instructions.strip().startswith("{"):
            import json

            try:
                payload = json.loads(item.instructions)
                sk = payload.get("skill")
                if sk:
                    skills_today.add(sk)
            except json.JSONDecodeError:
                pass
        if item.content_item_id:
            from app.db.models import ContentItem

            ci = db.get(ContentItem, item.content_item_id)
            if ci:
                skills_today.add(parse_item_meta(ci).get("skill") or "")

    for skill in sorted(skills_today):
        if not skill or skill == "训练":
            continue
        if not _card_for_skill(cards, skill):
            continue
        bump_skill_after_checkin(db, talent_code, state, skill)
        bumped_skills.append(skill)

    bump_main_line_session(state)

    save_training_progress(db, child, state)
    main_line_after = state.get("main_line") or "A"
    pending_to = state.get("pending_main_line_to")
    return {
        "main_line": main_line_after,
        "main_line_from": main_line_before,
        "main_line_to": pending_to if advance_eval.get("advance_met") else None,
        "main_line_advanced": False,
        "advance_pending": bool(advance_eval.get("advance_met") and pending_to),
        "pending_main_line_to": pending_to,
        "advance_met": bool(advance_eval.get("advance_met")),
        "advance_rule_key": advance_eval.get("advance_rule_key"),
        "advance_detail": advance_eval.get("advance_detail"),
        "advance_message": advance_eval.get("message"),
        "skills_bumped": bumped_skills,
        "content_index": main_line_index(main_line_after),
    }


def reassess_main_line_from_plan(
    db: Session,
    child: ChildUser,
    plan: TrainingPlan,
    *,
    talent_code: int,
    grade: str | None,
) -> dict:
    """修改/删除打卡后，按本方案全部轮次重新判定进阶"""
    from app.services.child_training_state import get_training_progress, save_training_progress

    state = get_training_progress(child)
    grade_band = _grade_band(grade)
    main_line_before = state.get("main_line") or "A"
    advance_cards = collect_plan_checkin_cards(db, child.id, plan.id)
    advance_eval = build_main_line_advance_eval(state, advance_cards, grade_band)
    _apply_advance_eval_to_state(state, plan, advance_eval)
    save_training_progress(db, child, state)
    main_line_after = state.get("main_line") or "A"
    pending_to = state.get("pending_main_line_to")
    return {
        "main_line": main_line_after,
        "main_line_from": main_line_before,
        "main_line_to": pending_to if advance_eval.get("advance_met") else None,
        "main_line_advanced": False,
        "advance_pending": bool(advance_eval.get("advance_met") and pending_to),
        "pending_main_line_to": pending_to,
        "advance_met": bool(advance_eval.get("advance_met")),
        "advance_rule_key": advance_eval.get("advance_rule_key"),
        "advance_detail": advance_eval.get("advance_detail"),
        "advance_message": advance_eval.get("message"),
        "content_index": main_line_index(main_line_after),
    }
