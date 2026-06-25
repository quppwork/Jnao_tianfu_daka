"""首页引导对话 — 会话持久化"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GuideMessage, GuideSession
from app.services.doubao_client import chat_completion

SYSTEM_PROMPT = """你是 JNAO 天赋成长平台的「张宇老师」，负责在首页引导家长和学生了解、使用平台（不是学科解题辅导；学科辅导请引导去「知识答题」）。

平台四大功能：
1. 天赋测试 — 35 道选择题，分析天赋类型（学者/思者/赢者/德者/行者），生成专属报告。
2. 今日训练 — 按天赋推送每日音视频训练与打卡总结。
3. 知识答题 — 数学/语文/英语/科学一对一辅导；拍题、语音或文字提问（入口：首页「学科答疑」）。
4. 成长里程碑 — 徽章、时间线与成长分享。

推荐使用顺序：天赋测试 → 今日训练 → 知识答题 → 查看成长。

回答规则：
- 只回答平台使用与功能介绍，语气像耐心的张宇老师，温暖简洁（2-4 句）
- 具体题目、作业答案、训练内容细节：引导去「知识答题」或联系老师
- 不提供用户个人测评/训练数据（引导其进入对应模块查看）
- 不知道的信息诚实说「这部分需要联系老师了解」"""

GREETING = "你好！我是张宇老师 👋 想了解平台怎么用都可以问我～比如：天赋测试怎么做？知识答题在哪里？"


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
