"""学科答疑 — 会话 CRUD + 薄封装；对话编排在 agents/qa/runner。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.qa.memory import QaMemory
from app.agents.qa.trace import TurnTimer, build_qa_turn_trace, emit_qa_trace
from app.core.cache import invalidate_user_growth
from app.db.models import ChildUser, QaMessage, QaSession
from app.services.qa_cache import get_session_list, invalidate_session_list, set_session_list
from app.services.text_sanitize import sanitize_subject


def invalidate_qa_caches(child_user_id: int) -> None:
    invalidate_session_list(child_user_id)
    invalidate_user_growth(child_user_id)


# 兼容旧名
_invalidate_qa_caches = invalidate_qa_caches


def emit_turn(
    *,
    timer: TurnTimer,
    child_user_id: int,
    session_id: int | None,
    subject: str | None,
    message: str,
    reply: str | None,
    school_stage: str | None = None,
    has_image: bool = False,
    ocr_used: bool = False,
    rag_used: bool = False,
    subject_mismatch: bool = False,
    suggested_subject: str | None = None,
    clarified: bool = False,
    stream: bool = False,
) -> None:
    emit_qa_trace(
        build_qa_turn_trace(
            child_user_id=child_user_id,
            session_id=session_id,
            subject=subject,
            message=message,
            duration_ms=timer.ms(),
            reply=reply,
            has_image=has_image,
            ocr_used=ocr_used,
            rag_used=rag_used,
            subject_mismatch=subject_mismatch,
            suggested_subject=suggested_subject,
            clarified=clarified,
            stream=stream,
            school_stage=school_stage,
        )
    )


_emit_turn = emit_turn


def learner_profile(user: ChildUser | None) -> dict:
    if not user:
        return {}
    return dict(user.profile_json or {})


_learner_profile = learner_profile


def assistant_meta_for_storage(
    coach_meta: dict,
    *,
    rag_used: bool = False,
    rag_sources: list[str] | None = None,
) -> dict | None:
    """仅持久化跨轮复用所需的内部字段，不存 coach_hint 等可重算数据。"""
    meta: dict = {}
    pattern = coach_meta.get("mistake_pattern")
    if pattern:
        meta["mistake_pattern"] = pattern
    if rag_used:
        meta["rag_used"] = True
        if rag_sources:
            meta["rag_sources"] = rag_sources
    return meta or None


_assistant_meta_for_storage = assistant_meta_for_storage


def public_chat_payload(
    *,
    session_id: int,
    reply: str,
    talent: str | None,
    school_stage: str,
    **extra: Any,
) -> dict:
    """返回给前端的答疑结果，不含教练提示词等内部元数据。"""
    return {
        "session_id": session_id,
        "reply": reply,
        "talent_primary": talent,
        "school_stage": school_stage,
        **extra,
    }


_public_chat_payload = public_chat_payload


def list_sessions(db: Session, child_user_id: int, limit: int = 20) -> list[dict]:
    cached = get_session_list(child_user_id)
    if cached is not None:
        return cached[:limit]

    rows = db.scalars(
        select(QaSession)
        .where(QaSession.child_user_id == child_user_id)
        .order_by(QaSession.id.desc())
        .limit(limit)
    ).all()
    items = [
        {
            "id": s.id,
            "title": s.title,
            "subject": s.subject,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in rows
    ]
    set_session_list(child_user_id, items)
    return items


def get_session_messages(db: Session, session_id: int, child_user_id: int) -> list[dict] | None:
    return QaMemory.load_messages(db, session_id, child_user_id)


def create_session(db: Session, child_user_id: int, subject: str | None = None) -> QaSession:
    session = QaSession(
        child_user_id=child_user_id,
        subject=sanitize_subject(subject),
        title="新对话",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    invalidate_session_list(child_user_id)
    return session


def delete_session(db: Session, session_id: int, child_user_id: int) -> bool:
    session = db.get(QaSession, session_id)
    if not session or session.child_user_id != child_user_id:
        return False
    db.delete(session)
    db.commit()
    invalidate_session_list(child_user_id)
    return True


async def chat(
    db: Session,
    child_user_id: int,
    message: str,
    *,
    session_id: int | None = None,
    subject: str | None = None,
    image_id: str | None = None,
    use_rag: bool | None = None,
) -> dict:
    from app.agents.qa.runner import run_chat

    return await run_chat(
        db,
        child_user_id,
        message,
        session_id=session_id,
        subject=subject,
        image_id=image_id,
        use_rag=use_rag,
    )


async def chat_stream(
    db: Session,
    child_user_id: int,
    message: str,
    *,
    session_id: int | None = None,
    subject: str | None = None,
    image_id: str | None = None,
    use_rag: bool | None = None,
) -> AsyncIterator[tuple[str, Any]]:
    from app.agents.qa.runner import run_chat_stream

    async for item in run_chat_stream(
        db,
        child_user_id,
        message,
        session_id=session_id,
        subject=subject,
        image_id=image_id,
        use_rag=use_rag,
    ):
        yield item


def count_user_messages(db: Session, child_user_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(QaMessage)
        .join(QaSession)
        .where(QaSession.child_user_id == child_user_id, QaMessage.role == "user")
    ) or 0
