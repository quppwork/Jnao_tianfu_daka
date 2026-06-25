"""首页引导对话 — 会话持久化"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GuideMessage, GuideSession
from app.services.doubao_client import chat_completion

SYSTEM_PROMPT = """你是 JNAO 天赋成长平台的智能助手，你的职责是帮助用户了解和使用本平台。

平台有四大功能：
1. 天赋测试 — 回答35道选择题，AI分析你的天赋类型（学者/思者/赢者/德者/行者），生成专属报告含雷达图和情绪分析。
2. 今日训练 — 每日打卡训练，按等级解锁训练内容（视频+音频），完成后生成训练总结。
3. 知识答题 — 语音或文字提问，AI老师一对一个性化辅导（数学/语文/英语/科学）。
4. 成长里程碑 — 记录成长轨迹，获得荣誉徽章，分享精彩瞬间。

使用流程：先做天赋测试→确定等级→每日训练→知识答题→查看成长。

回答规则：
- 只回答平台使用相关的问题，引导用户使用上述功能
- 不提供具体训练内容、题目答案或用户个人数据
- 不知道的信息诚实说"这部分需要联系老师了解"
- 语气温暖亲切，像一位耐心的教育顾问
- 回答简洁，2-4句话即可"""

GREETING = "你好！我是 JNAO 智能助手 👋 有什么想问的吗？比如：天赋测试怎么做？"


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
