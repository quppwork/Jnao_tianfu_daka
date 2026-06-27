"""打卡量化 → 达标判定 → 技能课序 / 主线进阶"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from app.services.child_training_state import (
    advance_main_line,
    bump_main_line_session,
    get_skill_position,
    main_line_index,
    set_skill_position,
)
from app.services.content_meta import parse_item_meta
from app.services.talent_content_pool import get_talent_content_pool
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


def _card_for_skill(cards: list[dict], skill: str) -> dict | None:
    for c in cards or []:
        if (c.get("name") or "").strip() == skill:
            return c
    return None


def _rule_met(rule_key: str, card: dict, grade_band: str | None) -> bool:
    rules = (load_training_advance_rules().get("rules") or {})
    spec = rules.get(rule_key) or {}
    rtype = spec.get("type")
    if rtype == "words_per_minute":
        words = _parse_num(card.get("content"))
        minutes = _parse_num(card.get("time")) or 1.0
        if not words:
            return False
        wpm = words / max(minutes, 0.1)
        return wpm >= float(spec.get("min_words") or 1000)
    if rtype == "grade_min_words":
        targets = load_training_advance_rules().get("grade_word_targets") or {}
        band = grade_band or "primary_low"
        need = int(targets.get(band) or targets.get("primary_low") or 300)
        words = _parse_num(card.get(spec.get("field") or "content"))
        return words is not None and words >= need
    if rtype == "accuracy_pct":
        acc = _parse_num(card.get(spec.get("field") or "accuracy"))
        return acc is not None and acc >= float(spec.get("min_pct") or 70)
    return False


def _next_lesson_in_pool(pool: list, skill: str, stage: int, part: int) -> tuple[int, int] | None:
    if _find_lesson(pool, skill, stage, part + 1):
        return stage, part + 1
    if _find_lesson(pool, skill, stage + 1, 1):
        return stage + 1, 1
    return None


def evaluate_main_line_advance(state: dict, cards: list[dict], grade_band: str | None) -> bool:
    cur = load_training_curriculum()
    adv_cfg = cur.get("main_line_advance") or {}
    if not adv_cfg.get("enabled", True):
        return False
    min_sessions = int(adv_cfg.get("min_sessions_on_line") or 0)
    if min_sessions > 0 and int(state.get("main_line_sessions") or 0) < min_sessions:
        return False
    key = state.get("main_line") or "A"
    spec = (cur.get("main_lines") or {}).get(key) or {}
    rule_key = spec.get("advance_rule")
    if not rule_key:
        return False
    rules = (load_training_advance_rules().get("rules") or {})
    skill = (rules.get(rule_key) or {}).get("skill")
    if not skill:
        return False
    card = _card_for_skill(cards, skill)
    if not card:
        return False
    return _rule_met(rule_key, card, grade_band)


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
    main_advanced = False

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
    if evaluate_main_line_advance(state, cards, grade_band):
        main_advanced = advance_main_line(state)

    save_training_progress(db, child, state)
    return {
        "main_line": state.get("main_line"),
        "main_line_advanced": main_advanced,
        "skills_bumped": bumped_skills,
        "content_index": main_line_index(state.get("main_line") or "A"),
    }
