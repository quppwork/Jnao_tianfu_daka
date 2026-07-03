"""学科答疑教练元数据 — 错题模式与跨会话摘要"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import QaMessage, QaSession
from app.agents.shared.talent import talent_coaching_hint


MISTAKE_PATTERNS: dict[str, str] = {
    "思者": "overthink",
    "行者": "rush_without_check",
    "学者": "skip_definition",
    "德者": "low_confidence",
    "赢者": "careless_under_pressure",
}

MISTAKE_PATTERN_HINTS: dict[str, str] = {
    "overthink": "容易想太多、纠结步骤，作答前请先写清已知条件",
    "rush_without_check": "容易粗心漏步骤，提醒做完后快速复查",
    "skip_definition": "容易跳过定义与概念，先确认术语再解题",
    "low_confidence": "容易不自信，多给肯定并拆成小步",
    "careless_under_pressure": "压力下易马虎，强调检查关键一步",
}


def fetch_recent_coach_context_for_prompt(
    db: Session,
    child_user_id: int,
    *,
    session_id: int | None = None,
    limit: int = 8,
) -> str | None:
    """读取近期答疑 assistant 消息的 mistake_pattern，注入下次系统提示。"""
    rows = db.scalars(
        select(QaMessage)
        .join(QaSession)
        .where(
            QaSession.child_user_id == child_user_id,
            QaMessage.role == "assistant",
        )
        .order_by(QaMessage.id.desc())
        .limit(limit)
    ).all()

    if session_id:
        session_rows = [r for r in rows if r.session_id == session_id]
        if session_rows:
            rows = session_rows

    patterns: list[str] = []
    seen_pattern: set[str] = set()
    for row in rows:
        meta = row.meta_json if isinstance(row.meta_json, dict) else {}
        pattern = meta.get("mistake_pattern")
        if pattern and pattern not in seen_pattern:
            seen_pattern.add(pattern)
            label = MISTAKE_PATTERN_HINTS.get(pattern, str(pattern))
            patterns.append(label)

    if not patterns:
        return None
    return "学员近期易错模式（请针对性辅导，勿重复说教）：" + "；".join(patterns)


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
    from app.agents.qa.memory import QaMemory

    return QaMemory.recent_topics(db, child_user_id, limit=limit)


def count_user_qa_turns(db: Session, child_user_id: int) -> int:
    return (
        db.scalar(
            select(QaMessage.id)
            .join(QaSession)
            .where(QaSession.child_user_id == child_user_id, QaMessage.role == "user")
        )
        or 0
    )
