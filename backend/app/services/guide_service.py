"""首页引导对话 — 会话持久化 + 开场 bootstrap 入口"""

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GuideMessage, GuideSession


def _history_for_llm(session: GuideSession) -> list[dict]:
    """仅 role/content，供模型上下文（不含 actions/tools）。"""
    return [{"role": m.role, "content": m.content} for m in session.messages]


def _meta_from_message(m: GuideMessage) -> dict:
    raw = m.meta_json if isinstance(m.meta_json, dict) else {}
    return {
        "actions": list(raw.get("actions") or []),
        "tools_used": list(raw.get("tools_used") or []),
        "blocks": list(raw.get("blocks") or []),
    }


def _payload_messages(session: GuideSession) -> list[dict]:
    """API 回放：content + actions / tools_used / blocks。"""
    out: list[dict] = []
    for m in session.messages:
        row = {"role": m.role, "content": m.content}
        if m.role == "assistant":
            meta = _meta_from_message(m)
            row["actions"] = meta["actions"]
            row["tools_used"] = meta["tools_used"]
            row["blocks"] = meta["blocks"]
        out.append(row)
    return out


def _assistant_meta(result_or_meta: dict) -> dict | None:
    actions = list(result_or_meta.get("actions") or [])
    tools_used = list(result_or_meta.get("tools_used") or [])
    blocks = list(result_or_meta.get("blocks") or [])
    if not actions and not tools_used and not blocks:
        return None
    return {"actions": actions, "tools_used": tools_used, "blocks": blocks}


def get_active_session(db: Session, child_user_id: int) -> GuideSession | None:
    return db.scalar(
        select(GuideSession)
        .where(GuideSession.child_user_id == child_user_id)
        .order_by(GuideSession.id.desc())
        .limit(1)
    )


def load_session_payload(db: Session, child_user_id: int) -> dict:
    """加载会话历史。开场欢迎改由 bootstrap 负责，此处不再注入静态 GREETING。"""
    session = get_active_session(db, child_user_id)
    if not session:
        return {"session_id": None, "messages": []}
    return {
        "session_id": session.id,
        "messages": _payload_messages(session),
    }


def list_sessions(db: Session, child_user_id: int, limit: int = 30) -> list[dict]:
    """历史会话列表（仅含至少一条用户消息的会话）。"""
    rows = db.scalars(
        select(GuideSession)
        .where(GuideSession.child_user_id == child_user_id)
        .order_by(GuideSession.id.desc())
        .limit(limit * 2)
    ).all()
    items: list[dict] = []
    for s in rows:
        msgs = list(s.messages or [])
        if not any(m.role == "user" for m in msgs):
            continue
        items.append({
            "id": s.id,
            "title": (s.title or "首页对话").strip() or "首页对话",
            "message_count": len(msgs),
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })
        if len(items) >= limit:
            break
    return items


def get_session_payload(
    db: Session, child_user_id: int, session_id: int
) -> dict | None:
    session = db.get(GuideSession, session_id)
    if not session or session.child_user_id != child_user_id:
        return None
    return {
        "session_id": session.id,
        "title": session.title,
        "messages": _payload_messages(session),
    }


def delete_session(db: Session, child_user_id: int, session_id: int) -> bool:
    session = db.get(GuideSession, session_id)
    if not session or session.child_user_id != child_user_id:
        return False
    db.delete(session)
    db.commit()
    return True


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


async def bootstrap(
    db: Session,
    child_user_id: int,
    *,
    force: bool = False,
    use_llm: bool = True,
) -> dict:
    """进首页开场 Agent：sense → decide → speak。欢迎语默认不写入会话。"""
    from app.agents.guide.bootstrap import run_bootstrap

    return await run_bootstrap(db, child_user_id, force=force, use_llm=use_llm)


async def chat(
    db: Session,
    child_user_id: int,
    message: str,
    *,
    session_id: int | None = None,
) -> dict:
    from app.agents.guide.runner import run_chat

    session = _get_or_create_session(db, child_user_id, session_id)
    history = _history_for_llm(session)

    db.add(GuideMessage(session_id=session.id, role="user", content=message))
    if not session.title or session.title == "首页助手":
        session.title = message[:30]
    db.commit()

    result = await run_chat(db, child_user_id, message, history=history)
    reply = result["reply"]

    db.add(
        GuideMessage(
            session_id=session.id,
            role="assistant",
            content=reply,
            meta_json=_assistant_meta(result),
        )
    )
    db.commit()

    return {
        "session_id": session.id,
        "reply": reply,
        "actions": result.get("actions") or [],
        "situation": result.get("situation"),
        "next_action": result.get("next_action"),
        "situation_label": result.get("situation_label"),
        "tools_used": result.get("tools_used") or [],
        "blocks": result.get("blocks") or [],
    }


async def chat_stream(
    db: Session,
    child_user_id: int,
    message: str,
    *,
    session_id: int | None = None,
) -> AsyncIterator[tuple[str, Any]]:
    """流式对话：yield ('token', str) 后 yield ('done', dict)。"""
    from app.agents.guide.runner import run_chat_stream

    session = _get_or_create_session(db, child_user_id, session_id)
    history = _history_for_llm(session)

    db.add(GuideMessage(session_id=session.id, role="user", content=message))
    if not session.title or session.title == "首页助手":
        session.title = message[:30]
    db.commit()

    parts: list[str] = []
    meta: dict = {}
    async for kind, payload in run_chat_stream(
        db, child_user_id, message, history=history
    ):
        if kind == "meta":
            meta = payload if isinstance(payload, dict) else {}
            continue
        if kind == "error":
            yield ("error", payload)
            return
        parts.append(payload)
        yield ("token", payload)

    reply = "".join(parts) or "抱歉，AI 暂时无法响应，请稍后再试。"
    db.add(
        GuideMessage(
            session_id=session.id,
            role="assistant",
            content=reply,
            meta_json=_assistant_meta(meta),
        )
    )
    db.commit()
    yield (
        "done",
        {
            "session_id": session.id,
            "reply": reply,
            "actions": meta.get("actions") or [],
            "situation": meta.get("situation"),
            "next_action": meta.get("next_action"),
            "situation_label": meta.get("situation_label"),
            "tools_used": meta.get("tools_used") or [],
            "blocks": meta.get("blocks") or [],
        },
    )


def clear_sessions(db: Session, child_user_id: int) -> int:
    from app.agents.guide.memory import clear_bootstrap_cache
    from app.agents.guide.student_memory import clear_guide_memory

    sessions = list(
        db.scalars(select(GuideSession).where(GuideSession.child_user_id == child_user_id)).all()
    )
    for s in sessions:
        db.delete(s)
    db.commit()
    clear_bootstrap_cache(child_user_id)
    clear_guide_memory(db, child_user_id)
    return len(sessions)
