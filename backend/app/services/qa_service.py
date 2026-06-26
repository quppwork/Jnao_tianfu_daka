"""学科答疑 — 编排：画像 / 拍图 / RAG / 豆包"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ChildUser, QaMessage, QaSession
from app.services.assessment_service import get_latest_assessment
from app.services.doubao_client import chat_completion, vision_chat_completion
from app.services.qa_cache import get_session_list, invalidate_session_list, set_session_list
from app.services.qa_coach import build_coach_metadata
from app.services.qa_image_store import image_data_url
from app.agents.qa.memory import QaMemory
from app.agents.qa.prompt_builder import build_qa_system_prompt
from app.agents.qa.router import check_subject_mismatch, mismatch_reply
from app.agents.shared.stage import infer_school_stage
from app.services.qa_rag_client import rag_chat
from app.services.qa_rag_router import should_use_rag
from app.services.text_sanitize import sanitize_subject, sanitize_text, session_title_from_message


def _learner_profile(user: ChildUser | None) -> dict:
    if not user:
        return {}
    return dict(user.profile_json or {})


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
    message = sanitize_text(message)
    if not message and not image_id:
        raise ValueError("消息不能为空")
    subject = sanitize_subject(subject)
    user = db.get(ChildUser, child_user_id)
    profile = _learner_profile(user)
    assessment = get_latest_assessment(db, child_user_id)
    talent = assessment.talent_primary if assessment else None
    report_json = assessment.report_json if assessment else None

    school_stage = infer_school_stage(
        grade=profile.get("grade"),
        age=profile.get("age"),
        school_stage=profile.get("school_stage"),
    )

    session = None
    if session_id:
        session = db.get(QaSession, session_id)
        if not session or session.child_user_id != child_user_id:
            raise ValueError("会话不存在")
    else:
        session = create_session(db, child_user_id, subject)

    active_subject = subject or session.subject
    mismatch = None if image_id else check_subject_mismatch(message, active_subject)
    if mismatch:
        QaMemory.append_message(db, session_id=session.id, role="user", content=message)
        if session.title == "新对话":
            session.title = session_title_from_message(message)
        reply = mismatch_reply(mismatch)
        QaMemory.append_message(
            db,
            session_id=session.id,
            role="assistant",
            content=reply,
            meta_json={
                "subject_mismatch": True,
                "suggested_subject": mismatch.detected,
                "selected_subject": mismatch.selected,
            },
        )
        db.commit()
        invalidate_session_list(child_user_id)
        return {
            "session_id": session.id,
            "reply": reply,
            "talent_primary": talent,
            "school_stage": school_stage,
            "subject_mismatch": True,
            "suggested_subject": mismatch.detected,
            "selected_subject": mismatch.selected,
        }

    history = QaMemory.load_chat_history(session, limit=10)

    coach_meta = build_coach_metadata(
        talent_primary=talent,
        report_json=report_json,
        school_stage=school_stage,
        message=message,
    )
    topics = QaMemory.recent_topics(db, child_user_id)
    if topics:
        coach_meta["recent_topics"] = topics[:3]

    ocr_preview = None
    image_url = None
    has_image = bool(image_id)
    if image_id:
        data_url = image_data_url(image_id, child_user_id)
        if not data_url:
            raise ValueError("图片不存在或已过期")
        image_url = f"/api/qa/images/{image_id}?user_id={child_user_id}"
        ocr_preview = await vision_chat_completion(
            system_prompt="你是 OCR 助手。请简要识别图片中的学科题目文字与关键条件，不要解题。",
            user_message="请识别图中题目，列出已知条件和问题。",
            image_data_url=data_url,
            max_tokens=400,
        )

    rag_used = False
    rag_sources: list[str] = []
    rag_context = None
    if should_use_rag(message, subject=subject or session.subject, has_image=has_image, use_rag=use_rag):
        rag = await rag_chat(
            message,
            user_id=f"child_{child_user_id}",
            subject=subject or session.subject,
        )
        if rag and rag.get("answer"):
            rag_used = True
            rag_sources = list(rag.get("sources") or [])
            rag_context = rag["answer"]

    system = build_qa_system_prompt(
        school_stage=school_stage,
        grade=profile.get("grade"),
        age=profile.get("age"),
        talent_primary=talent,
        report_json=report_json,
        subject=subject or session.subject,
        rag_context=rag_context,
        ocr_preview=ocr_preview,
    )

    user_row = QaMessage(
        session_id=session.id,
        role="user",
        content=message,
        image_url=image_url,
        meta_json={"image_id": image_id} if image_id else None,
    )
    db.add(user_row)
    if session.title == "新对话":
        session.title = session_title_from_message(message)
    db.commit()

    if has_image and image_id:
        data_url = image_data_url(image_id, child_user_id)
        reply = await vision_chat_completion(
            system_prompt=system,
            user_message=message,
            image_data_url=data_url or "",
            history=history,
            max_tokens=900,
        )
    else:
        reply = await chat_completion(
            system_prompt=system,
            user_message=message,
            history=history,
            max_tokens=900,
        )

    if not reply:
        reply = "抱歉，AI 暂时无法响应，请稍后再试。"

    assistant_meta = {
        **coach_meta,
        "rag_used": rag_used,
        "rag_sources": rag_sources,
        "ocr_preview": ocr_preview,
    }
    db.add(
        QaMessage(
            session_id=session.id,
            role="assistant",
            content=reply,
            meta_json=assistant_meta,
        )
    )
    db.commit()
    invalidate_session_list(child_user_id)

    return {
        "session_id": session.id,
        "reply": reply,
        "talent_primary": talent,
        "school_stage": school_stage,
        "coach_hint": coach_meta.get("coach_hint"),
        "mistake_pattern": coach_meta.get("mistake_pattern"),
        "rag_used": rag_used,
        "rag_sources": rag_sources,
        "ocr_preview": ocr_preview,
        "recent_topics": coach_meta.get("recent_topics"),
    }


def count_user_messages(db: Session, child_user_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(QaMessage)
        .join(QaSession)
        .where(QaSession.child_user_id == child_user_id, QaMessage.role == "user")
    ) or 0
