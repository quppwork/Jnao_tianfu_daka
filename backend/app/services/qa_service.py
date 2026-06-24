"""学科答疑 — 豆包 + 天赋提示词 + 会话持久化"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import QaMessage, QaSession
from app.services.assessment_service import get_latest_assessment
from app.services.doubao_client import chat_completion

QA_SYSTEM_BASE = """你是 JNAO 平台的学科辅导老师「张宇老师」，面向 K12 学生一对一答疑。
学科范围：数学、语文、英语、科学。
回答要求：
- 先理解学生问题，再分步骤讲解
- 语气亲切耐心，适合孩子理解
- 不直接给作业答案时，引导学生思考
- 回答控制在 200 字以内，除非题目复杂"""


def _build_system_prompt(talent_primary: str | None, subject: str | None) -> str:
    prompt = QA_SYSTEM_BASE
    if talent_primary:
        prompt += f"\n该学员主导天赋为「{talent_primary}」，请结合其思维特点辅导。"
    if subject:
        prompt += f"\n当前学科：{subject}。"
    return prompt


def list_sessions(db: Session, child_user_id: int, limit: int = 20) -> list[dict]:
    rows = db.scalars(
        select(QaSession)
        .where(QaSession.child_user_id == child_user_id)
        .order_by(QaSession.id.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": s.id,
            "title": s.title,
            "subject": s.subject,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in rows
    ]


def get_session_messages(db: Session, session_id: int, child_user_id: int) -> list[dict] | None:
    session = db.get(QaSession, session_id)
    if not session or session.child_user_id != child_user_id:
        return None
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in session.messages
    ]


def create_session(db: Session, child_user_id: int, subject: str | None = None) -> QaSession:
    session = QaSession(child_user_id=child_user_id, subject=subject, title="新对话")
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def delete_session(db: Session, session_id: int, child_user_id: int) -> bool:
    session = db.get(QaSession, session_id)
    if not session or session.child_user_id != child_user_id:
        return False
    db.delete(session)
    db.commit()
    return True


async def chat(
    db: Session,
    child_user_id: int,
    message: str,
    *,
    session_id: int | None = None,
    subject: str | None = None,
) -> dict:
    assessment = get_latest_assessment(db, child_user_id)
    talent = assessment.talent_primary if assessment else None

    session = None
    if session_id:
        session = db.get(QaSession, session_id)
        if not session or session.child_user_id != child_user_id:
            raise ValueError("会话不存在")
    else:
        session = create_session(db, child_user_id, subject)

    db.add(QaMessage(session_id=session.id, role="user", content=message))
    if session.title == "新对话":
        session.title = message[:30]
    db.commit()

    system = _build_system_prompt(talent, subject or session.subject)
    reply = await chat_completion(system_prompt=system, user_message=message, max_tokens=800)
    if not reply:
        reply = "抱歉，AI 暂时无法响应，请稍后再试。"

    db.add(QaMessage(session_id=session.id, role="assistant", content=reply))
    db.commit()

    return {
        "session_id": session.id,
        "reply": reply,
        "talent_primary": talent,
    }


def count_user_messages(db: Session, child_user_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(QaMessage)
        .join(QaSession)
        .where(QaSession.child_user_id == child_user_id, QaMessage.role == "user")
    ) or 0
