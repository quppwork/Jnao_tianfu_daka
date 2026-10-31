"""上游用量计数单测"""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import ChildUser, ParentChildBind, UpstreamUsageEvent
from app.services import usage_recorder as ur
from app.services import doubao_client


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def _user(db, *, phone="13800000000", nickname="u", role="student"):
    u = ChildUser(
        parent_phone=phone,
        nickname=nickname,
        role=role,
        login_name=f"{nickname}_{phone[-4:]}",
        password_hash="x",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_parse_usage_dict():
    assert ur._parse_usage_dict({"prompt_tokens": 10, "completion_tokens": 5}) == (10, 5, 15)
    assert ur._parse_usage_dict({"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 9}) == (3, 2, 9)
    assert ur._parse_usage_dict(None) == (0, 0, 0)


def test_record_and_sum_by_parent(db):
    parent = _user(db, phone="13900001111", nickname="parent", role="parent")
    child_a = _user(db, phone="13900001111", nickname="childA", role="student")
    child_b = _user(db, phone="13900001111", nickname="childB", role="student")
    db.add(ParentChildBind(parent_id=parent.id, child_id=child_a.id))
    db.add(ParentChildBind(parent_id=parent.id, child_id=child_b.id))
    db.commit()

    ur.record_usage(
        provider="doubao",
        api="chat.completions",
        user_id=child_a.id,
        prompt_tokens=100,
        completion_tokens=40,
        total_tokens=140,
        db=db,
    )
    ur.record_usage(
        provider="doubao",
        api="chat.completions",
        user_id=child_b.id,
        prompt_tokens=50,
        completion_tokens=10,
        total_tokens=60,
        db=db,
    )
    ur.record_usage(
        provider="doubao",
        api="chat.completions",
        user_id=parent.id,
        prompt_tokens=20,
        completion_tokens=5,
        total_tokens=25,
        db=db,
    )
    ur.record_usage(
        provider="bailian",
        api="retrieve",
        user_id=child_a.id,
        metric_kind="call",
        call_count=1,
        doc_count=3,
        total_tokens=0,
        db=db,
    )

    child_sum = ur.sum_tokens_for_user(db, child_a.id)
    assert child_sum["total_tokens"] == 140
    assert child_sum["call_count"] == 2  # doubao + bailian

    parent_bill = ur.sum_tokens_for_billing_parent(db, parent.id)
    assert parent_bill["total_tokens"] == 140 + 60 + 25
    assert parent_bill["call_count"] == 4
    assert len(parent_bill["by_user"]) == 3

    rows = db.scalars(select(UpstreamUsageEvent)).all()
    assert all(r.billing_parent_id == parent.id for r in rows)


@pytest.mark.asyncio
async def test_chat_completion_records_usage(db):
    child = _user(db, nickname="stu")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "OK"}}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
    }
    from unittest.mock import AsyncMock

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_resp)

    with (
        patch.object(
            doubao_client,
            "_cfg",
            return_value={"api_key": "k", "api_base": "http://x", "model": "m", "vision_model": "m"},
        ),
        patch.object(doubao_client, "_get_client", return_value=mock_client),
        patch("app.db.session.get_session_factory", return_value=lambda: db),
        patch("app.services.usage_recorder.get_user_id", return_value=child.id),
        patch.object(db, "close"),
    ):
        result = await doubao_client.chat_completion(system_prompt="s", user_message="hi", feature="qa")
    assert result == "OK"
    ev = db.scalars(select(UpstreamUsageEvent)).first()
    assert ev is not None
    assert ev.provider == "doubao"
    assert ev.user_id == child.id
    assert ev.total_tokens == 18
    assert ev.feature == "qa"
