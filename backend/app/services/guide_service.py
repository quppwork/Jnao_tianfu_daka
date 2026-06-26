"""首页引导对话 — 会话持久化"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GuideMessage, GuideSession
from app.agents.guide.persona import GREETING, SYSTEM_PROMPT
from app.services.doubao_client import chat_completion


def _session_messages(session: GuideSession) -> list[dict]:
    return [
        {"role": m.role, "content": m.content}
        for m in session.messages
    ]


def get_active_session(db: Session, child_user_id: int) -> GuideSession | None:
    return db.scalar(
        select(GuideSession)
        .where(GuideSession.child_user_id == child_user_id)
        .order_by(GuideSession.id.desc())
        .limit(1)
    )


def load_session_payload(db: Session, child_user_id: int) -> dict:
    session = get_active_session(db, child_user_id)
    if not session:
        return {"session_id": None, "messages": [{"role": "assistant", "content": GREETING}]}
    msgs = _session_messages(session)
    if not msgs:
        msgs = [{"role": "assistant", "content": GREETING}]
    return {
        "session_id": session.id,
        "messages": [{"role": m["role"], "content": m["content"]} for m in msgs],
    }


def _get_or_create_session(db: Session, child_user_id: int, session_id: int | None) -> GuideSession:
    if session_id:
        session = db.get(GuideSession, session_id)
        if session and session.child_user_id == child_user_id:
            return session
    session = GuideSession(child_user_id=child_user_id, title="首页助手")
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


async def chat(
    db: Session,
    child_user_id: int,
    message: str,
    *,
    session_id: int | None = None,
) -> dict:
    session = _get_or_create_session(db, child_user_id, session_id)
    history = _session_messages(session)

    db.add(GuideMessage(session_id=session.id, role="user", content=message))
    if not session.title or session.title == "首页助手":
        session.title = message[:30]
    db.commit()

    reply = await chat_completion(
        system_prompt=SYSTEM_PROMPT,
        user_message=message,
        history=history,
    )
    if not reply:
        reply = "抱歉，AI 暂时无法响应，请稍后再试。"

    db.add(GuideMessage(session_id=session.id, role="assistant", content=reply))
    db.commit()

    return {"session_id": session.id, "reply": reply}


def clear_sessions(db: Session, child_user_id: int) -> int:
    sessions = list(
        db.scalars(select(GuideSession).where(GuideSession.child_user_id == child_user_id)).all()
    )
    for s in sessions:
        db.delete(s)
    db.commit()
    return len(sessions)
