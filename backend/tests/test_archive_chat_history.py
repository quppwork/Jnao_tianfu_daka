"""QA / Guide 会话归档 cron 工具测试"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.db.models import (
    GuideMessage,
    GuideSession,
    GuideSessionArchive,
    QaMessage,
    QaSession,
    QaSessionArchive,
)
from app.services.chat_archive_service import run_chat_archive
from app.services.qa_service import count_user_messages


def _add_qa_session(db, child_id: int, *, age_days: int, user_msgs: int = 1) -> QaSession:
    created = datetime.now() - timedelta(days=age_days)
    session = QaSession(
        child_user_id=child_id,
        title=f"old-{age_days}",
        subject="数学",
        created_at=created,
    )
    db.add(session)
    db.flush()
    for i in range(user_msgs):
        db.add(
            QaMessage(
                session_id=session.id,
                role="user",
                content=f"q{i}",
                created_at=created,
            )
        )
        db.add(
            QaMessage(
                session_id=session.id,
                role="assistant",
                content=f"a{i}",
                created_at=created,
            )
        )
    db.commit()
    db.refresh(session)
    return session


def _add_guide_session(db, child_id: int, *, age_days: int) -> GuideSession:
    created = datetime.now() - timedelta(days=age_days)
    session = GuideSession(
        child_user_id=child_id,
        title=f"guide-{age_days}",
        created_at=created,
        updated_at=created,
    )
    db.add(session)
    db.flush()
    db.add(GuideMessage(session_id=session.id, role="user", content="hi", created_at=created))
    db.add(GuideMessage(session_id=session.id, role="assistant", content="hello", created_at=created))
    db.commit()
    db.refresh(session)
    return session


def test_archive_qa_keeps_recent_and_preserves_stats(db_session, child_with_assessment):
    child_user_id = child_with_assessment
    old1 = _add_qa_session(db_session, child_user_id, age_days=500, user_msgs=3)
    old2 = _add_qa_session(db_session, child_user_id, age_days=400, user_msgs=1)
    recent = _add_qa_session(db_session, child_user_id, age_days=200, user_msgs=2)

    before_count = count_user_messages(db_session, child_user_id)
    assert before_count == 6

    result = run_chat_archive(
        db_session,
        retain_days=180,
        qa_keep_recent=1,
        guide_keep_recent=0,
        batch_size=50,
        include_guide=False,
    )
    assert result["qa"]["sessions"] == 2
    assert db_session.get(QaSession, recent.id) is not None
    assert db_session.get(QaSession, old1.id) is None
    assert db_session.get(QaSession, old2.id) is None

    archives = db_session.scalars(select(QaSessionArchive)).all()
    assert len(archives) == 2
    archived_ids = {a.original_session_id for a in archives}
    assert archived_ids == {old1.id, old2.id}

    # 成长统计仍计入已归档的用户消息
    assert count_user_messages(db_session, child_user_id) == 6


def test_archive_guide_respects_keep_recent(db_session, child_with_assessment):
    child_user_id = child_with_assessment
    keep = _add_guide_session(db_session, child_user_id, age_days=300)
    drop = _add_guide_session(db_session, child_user_id, age_days=400)

    result = run_chat_archive(
        db_session,
        retain_days=180,
        qa_keep_recent=0,
        guide_keep_recent=1,
        batch_size=50,
        include_qa=False,
    )
    assert result["guide"]["sessions"] == 1
    assert db_session.get(GuideSession, keep.id) is not None
    assert db_session.get(GuideSession, drop.id) is None
    assert db_session.scalar(select(GuideSessionArchive)) is not None


def test_archive_dry_run_no_changes(db_session, child_with_assessment):
    child_user_id = child_with_assessment
    _add_qa_session(db_session, child_user_id, age_days=400)
    result = run_chat_archive(
        db_session,
        retain_days=180,
        qa_keep_recent=0,
        guide_keep_recent=0,
        dry_run=True,
    )
    assert result["dry_run"] is True
    assert result["qa"]["sessions"] == 1
    assert db_session.scalar(select(QaSessionArchive)) is None
