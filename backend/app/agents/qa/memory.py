"""QA Agent 记忆层 — 封装会话与消息的读写，后续可扩展摘要/长期记忆"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import QaMessage, QaSession


class QaMemory:
    """学科答疑对话记忆：以 qa_session / qa_message 为持久化存储。"""

    @staticmethod
    def load_chat_history(
        session: QaSession,
        *,
        limit: int = 10,
        roles: tuple[str, ...] = ("user", "assistant"),
    ) -> list[dict]:
        msgs = [m for m in session.messages if m.role in roles]
        return [{"role": m.role, "content": m.content} for m in msgs[-limit:]]

    @staticmethod
    def load_messages(db: Session, session_id: int, child_user_id: int) -> list[dict] | None:
        session = db.get(QaSession, session_id)
        if not session or session.child_user_id != child_user_id:
            return None
        return [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "image_url": m.image_url,
                "meta_json": m.meta_json,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in session.messages
        ]

    @staticmethod
    def recent_topics(db: Session, child_user_id: int, limit: int = 5) -> list[str]:
        rows = db.scalars(
            select(QaSession)
            .where(QaSession.child_user_id == child_user_id)
            .order_by(QaSession.id.desc())
            .limit(limit)
        ).all()
        return [r.title for r in rows if r.title and r.title != "新对话"]

    @staticmethod
    def append_message(
        db: Session,
        *,
        session_id: int,
        role: str,
        content: str,
        image_url: str | None = None,
        meta_json: dict | None = None,
    ) -> QaMessage:
        row = QaMessage(
            session_id=session_id,
            role=role,
            content=content,
            image_url=image_url,
            meta_json=meta_json,
        )
        db.add(row)
        return row
