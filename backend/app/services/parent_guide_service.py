"""家长引导 — 会话 CRUD / 落库（接入层下游的 Service 面）。

Agent 核（意图、出话）在 app.agents.parent_guide.runner。
下方再导出 runner 符号，兼容旧测试 patch 路径。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.agents.parent_guide.runner import (
    _kb_or_minimal_reply,
    _live_child_reply,
    asks_about_own_child,
    match_child_from_message,
    needs_child_clarification,
    resolve_focus_child_id,
    run_parent_turn,
    wants_course_kb,
    wants_live_child_data,
    wants_platform_kb,
)
from app.db.models import GuideMessage, GuideSession
from app.services import guide_service, parent_service

PARENT_SESSION_TITLE = "家长助手"

__all__ = [
    "PARENT_SESSION_TITLE",
    "asks_about_own_child",
    "chat",
    "chat_stream",
    "load_session_payload",
    "match_child_from_message",
    "needs_child_clarification",
    "resolve_focus_child_id",
    "run_parent_turn",
    "wants_course_kb",
    "wants_live_child_data",
    "wants_platform_kb",
    "_kb_or_minimal_reply",
    "_live_child_reply",
]


def _get_or_create_parent_session(
    db: Session,
    parent_id: int,
    session_id: int | None = None,
) -> GuideSession:
    if session_id:
        session = db.get(GuideSession, session_id)
        if not session or session.child_user_id != parent_id:
            raise HTTPException(404, "会话不存在")
        return session
    session = guide_service.get_active_session(db, parent_id)
    if session:
        return session
    session = GuideSession(child_user_id=parent_id, title=PARENT_SESSION_TITLE)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _history_for_llm(session: GuideSession) -> list[dict]:
    return [{"role": m.role, "content": m.content} for m in session.messages]


def _assistant_meta(result: dict) -> dict | None:
    actions = list(result.get("actions") or [])
    tools_used = list(result.get("tools_used") or [])
    blocks = list(result.get("blocks") or [])
    if not actions and not tools_used and not blocks:
        return None
    return {"actions": actions, "tools_used": tools_used, "blocks": blocks}


async def chat(
    db: Session,
    parent_id: int,
    message: str,
    *,
    session_id: int | None = None,
    child_id: int | None = None,
) -> dict[str, Any]:
    session = _get_or_create_parent_session(db, parent_id, session_id)
    history = _history_for_llm(session)

    db.add(GuideMessage(session_id=session.id, role="user", content=message))
    if not session.title or session.title == PARENT_SESSION_TITLE:
        session.title = (message or "")[:30] or PARENT_SESSION_TITLE
    db.commit()

    result = await run_parent_turn(
        db, parent_id, message, child_id=child_id, history=history
    )
    reply = result.get("reply") or ""
    db.add(
        GuideMessage(
            session_id=session.id,
            role="assistant",
            content=reply,
            meta_json=_assistant_meta(result),
        )
    )
    db.commit()
    guide_service._archive_session_overflow(db, session)  # noqa: SLF001

    return {
        "session_id": session.id,
        "focus_child_id": result.get("focus_child_id"),
        "reply": reply,
        "actions": result.get("actions") or [],
        "tools_used": result.get("tools_used") or [],
        "rag_used": bool(result.get("rag_used")),
        "rag_source": result.get("rag_source"),
        "situation": result.get("situation"),
        "next_action": result.get("next_action"),
    }


async def chat_stream(
    db: Session,
    parent_id: int,
    message: str,
    *,
    session_id: int | None = None,
    child_id: int | None = None,
) -> AsyncIterator[tuple[str, Any]]:
    """流式：思考状态 → 整段回复（会话已持久化）。"""
    yield ("status", "agent思考中…")
    children = parent_service.list_children(db, parent_id)
    if needs_child_clarification(message, children, child_id=child_id):
        yield ("status", "发现多位孩子，正在确认…")
    elif wants_platform_kb(message) and not asks_about_own_child(message):
        yield ("status", "正在查询知识库…")
    elif wants_live_child_data(message):
        yield ("status", "正在查阅孩子训练与报告…")
    else:
        yield ("status", "正在查询知识库…")

    result = await chat(
        db,
        parent_id,
        message,
        session_id=session_id,
        child_id=child_id,
    )
    reply = result.get("reply") or ""
    if reply:
        yield ("token", reply)
    yield ("done", result)


def load_session_payload(db: Session, parent_id: int) -> dict:
    return guide_service.load_session_payload(db, parent_id)
