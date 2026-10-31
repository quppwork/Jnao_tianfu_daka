# -*- coding: utf-8 -*-
"""首页引导：对话框 20 条上限 + 溢出拆入历史会话"""

from __future__ import annotations

from sqlalchemy import select

from app.db.models import GuideMessage, GuideSession
from app.services.auth_service import register_child
from app.services.guide_service import (
    GUIDE_DIALOG_MESSAGE_LIMIT,
    _archive_session_overflow,
    get_active_session,
    load_session_payload,
    list_sessions,
)


def _seed_session(db, child_id: int, message_count: int) -> GuideSession:
    session = GuideSession(child_user_id=child_id, title="溢出测试")
    db.add(session)
    db.flush()
    for i in range(message_count):
        role = "user" if i % 2 == 0 else "assistant"
        db.add(
            GuideMessage(
                session_id=session.id,
                role=role,
                content=f"msg-{i}",
            )
        )
    db.commit()
    db.refresh(session)
    return session


def test_archive_overflow_splits_oldest_messages(db_session):
    user = register_child(db_session, parent_phone="1390000g201", nickname="溢出童")
    session = _seed_session(db_session, user.id, GUIDE_DIALOG_MESSAGE_LIMIT + 4)

    archive = _archive_session_overflow(db_session, session)
    assert archive is not None
    assert len(archive.messages) == 4
    assert len(session.messages) == GUIDE_DIALOG_MESSAGE_LIMIT
    assert archive.messages[0].content == "msg-0"
    assert session.messages[-1].content == f"msg-{GUIDE_DIALOG_MESSAGE_LIMIT + 3}"


def test_load_active_session_caps_messages(db_session):
    user = register_child(db_session, parent_phone="1390000g202", nickname="加载童")
    session = _seed_session(db_session, user.id, GUIDE_DIALOG_MESSAGE_LIMIT + 2)
    _archive_session_overflow(db_session, session)

    payload = load_session_payload(db_session, user.id)
    assert payload["session_id"] == session.id
    assert len(payload["messages"]) == GUIDE_DIALOG_MESSAGE_LIMIT


def test_get_active_session_prefers_recent_activity(db_session):
    from datetime import datetime, timedelta

    user = register_child(db_session, parent_phone="1390000g203", nickname="活跃童")
    older = GuideSession(
        child_user_id=user.id,
        title="旧会话",
        updated_at=datetime.now() - timedelta(days=2),
    )
    db_session.add(older)
    db_session.flush()
    db_session.add(GuideMessage(session_id=older.id, role="user", content="old"))
    db_session.commit()

    active = _seed_session(db_session, user.id, 2)

    hit = get_active_session(db_session, user.id)
    assert hit is not None
    assert hit.id == active.id


def test_overflow_session_appears_in_history_list(db_session):
    user = register_child(db_session, parent_phone="1390000g204", nickname="历史童")
    session = _seed_session(db_session, user.id, GUIDE_DIALOG_MESSAGE_LIMIT + 2)
    archive = _archive_session_overflow(db_session, session)
    assert archive is not None

    items = list_sessions(db_session, user.id)
    ids = {it["id"] for it in items}
    assert archive.id in ids
    assert session.id in ids
