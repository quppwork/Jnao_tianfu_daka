"""学科答疑教练元数据 — 错题模式与跨会话摘要"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import QaMessage, QaSession
from app.services.qa_prompt_builder import talent_coaching_hint


MISTAKE_PATTERNS: dict[str, str] = {
    "思者": "overthink",
    "行者": "rush_without_check",
    "学者": "skip_definition",
    "德者": "low_confidence",
    "赢者": "careless_under_pressure",
}


def detect_mistake_pattern(talent_primary: str | None, message: str) -> str | None:
    if not talent_primary:
        return None
    text = message or ""
    if talent_primary == "思者" and any(k in text for k in ("想太多", "纠结", "不确定")):
        return "overthink"
    if talent_primary == "行者" and any(k in text for k in ("算错", "粗心", "漏")):
        return "rush_without_check"
    return MISTAKE_PATTERNS.get(talent_primary)


def build_coach_metadata(
    *,
    talent_primary: str | None,
    report_json: dict | None,
    school_stage: str,
    message: str,
) -> dict:
    hint = talent_coaching_hint(talent_primary, report_json)
    pattern = detect_mistake_pattern(talent_primary, message)
    meta = {
        "coach_hint": hint,
        "school_stage": school_stage,
        "talent_primary": talent_primary,
    }
    if pattern:
        meta["mistake_pattern"] = pattern
    return meta


def recent_session_topics(db: Session, child_user_id: int, limit: int = 5) -> list[str]:
    rows = db.scalars(
        select(QaSession)
        .where(QaSession.child_user_id == child_user_id)
        .order_by(QaSession.id.desc())
        .limit(limit)
    ).all()
    return [r.title for r in rows if r.title and r.title != "新对话"]


def count_user_qa_turns(db: Session, child_user_id: int) -> int:
    return (
        db.scalar(
            select(QaMessage.id)
            .join(QaSession)
            .where(QaSession.child_user_id == child_user_id, QaMessage.role == "user")
        )
        or 0
    )
