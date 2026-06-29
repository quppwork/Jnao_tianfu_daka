"""学员训练进度 — 主线 A→E + 各技能独立 stage/part（存 profile_json）"""

from __future__ import annotations

from typing import TYPE_CHECKING

from config.loader import load_training_curriculum

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.db.models import ChildUser

STATE_KEY = "training_progress"
MAIN_LINES = ("A", "B", "C", "D", "E")


def _default_state() -> dict:
    day_one = load_training_curriculum().get("day_one") or {}
    main_line = day_one.get("main_line") or "A"
    return {
        "main_line": main_line,
        "skills": {},
        "main_line_sessions": 0,
        "training_days": 0,
        "training_day_anchor": None,
        "pending_main_line_to": None,
        "last_settled_plan_date": None,
    }


def get_training_progress(child: ChildUser) -> dict:
    pj = child.profile_json if isinstance(child.profile_json, dict) else {}
    raw = pj.get(STATE_KEY)
    if not isinstance(raw, dict):
        return _default_state()
    return {
        "main_line": raw.get("main_line") or "A",
        "skills": dict(raw.get("skills") or {}),
        "main_line_sessions": int(raw.get("main_line_sessions") or 0),
        "training_days": int(raw.get("training_days") or 0),
        "training_day_anchor": raw.get("training_day_anchor"),
        "pending_main_line_to": raw.get("pending_main_line_to"),
        "last_settled_plan_date": raw.get("last_settled_plan_date"),
    }


def save_training_progress(db: Session, child: ChildUser, state: dict) -> dict:
    pj = dict(child.profile_json or {})
    pj[STATE_KEY] = {
        "main_line": state.get("main_line") or "A",
        "skills": state.get("skills") or {},
        "main_line_sessions": int(state.get("main_line_sessions") or 0),
        "training_days": int(state.get("training_days") or 0),
        "training_day_anchor": state.get("training_day_anchor"),
        "pending_main_line_to": state.get("pending_main_line_to"),
        "last_settled_plan_date": state.get("last_settled_plan_date"),
    }
    child.profile_json = pj
    db.flush()
    return pj[STATE_KEY]


def main_line_index(main_line: str) -> int:
    try:
        return MAIN_LINES.index(main_line)
    except ValueError:
        return 0


def get_skill_position(state: dict, skill: str) -> tuple[int, int]:
    row = (state.get("skills") or {}).get(skill) or {}
    return int(row.get("stage") or 1), int(row.get("part") or 1)


def set_skill_position(state: dict, skill: str, stage: int, part: int) -> None:
    skills = state.setdefault("skills", {})
    skills[skill] = {"stage": stage, "part": part}


def advance_main_line(state: dict) -> bool:
    cur = load_training_curriculum()
    lines = cur.get("main_lines") or {}
    key = state.get("main_line") or "A"
    spec = lines.get(key) or {}
    nxt = spec.get("advance_to")
    if not nxt or nxt not in MAIN_LINES:
        return False
    state["main_line"] = nxt
    state["main_line_sessions"] = 0
    return True


def bump_main_line_session(state: dict) -> None:
    state["main_line_sessions"] = int(state.get("main_line_sessions") or 0) + 1


def set_pending_main_line_advance(state: dict, to_line: str) -> None:
    if to_line in MAIN_LINES:
        state["pending_main_line_to"] = to_line


def apply_pending_main_line_advance(state: dict) -> bool:
    """新训练日生效：将昨日打卡达标的 pending 进阶写入 main_line"""
    pending = state.get("pending_main_line_to")
    if not pending or pending not in MAIN_LINES:
        return False
    state["main_line"] = pending
    state["pending_main_line_to"] = None
    state["main_line_sessions"] = 0
    return True


def training_day_number(state: dict) -> int:
    """已完成的训练日 + 1 = 当前第几天"""
    return int(state.get("training_days") or 0) + 1


def bump_training_completed_day(state: dict) -> None:
    state["training_days"] = int(state.get("training_days") or 0) + 1
