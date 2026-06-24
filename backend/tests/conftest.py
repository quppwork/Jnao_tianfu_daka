"""pytest 配置与共享 fixtures"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("TIANFU_RAG_MOCK", "1")

import pytest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.db.base import Base
from app.db.session import get_session_factory, init_db
from app.services.assessment_service import save_assessment
from app.services.auth_service import register_child
from app.services.catalog_import import import_catalog

# 前端模块 ↔ API 映射见 backend/tests/README.md


@pytest.fixture
def db_session() -> Session:
    init_db()
    session = get_session_factory()()
    import_catalog(session, replace=True)
    yield session
    session.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(delete(table))
    session.commit()
    session.close()


@pytest.fixture
def mock_jnao():
    with (
        patch("app.api.talent.jnao_submit", new_callable=AsyncMock) as mock_submit,
        patch("app.api.talent.jnao_get_report", new_callable=AsyncMock) as mock_report,
    ):
        mock_submit.return_value = "test-record-123"
        mock_report.return_value = {
            "id": 123,
            "uid": 999888,
            "type": 1,
            "talent": "学者",
            "check_talent": "学者",
            "create_time": "2026-06-18",
            "results": {},
            "property": "[]",
            "AttributeJs": "{}",
            "StateIcon": "",
        }
        yield {"submit": mock_submit, "report": mock_report}


@pytest.fixture
def mock_doubao():
    """全平台 AI 统一 mock 豆包"""
    reply = "【测试】豆包回复"

    async def _fake_stream(**kwargs):
        yield "你"
        yield "好"

    with (
        patch(
            "app.services.doubao_client.chat_completion",
            new_callable=AsyncMock,
            return_value=reply,
        ) as mock_chat,
        patch("app.api.guide.chat_completion", new_callable=AsyncMock, return_value=reply),
        patch("app.api.chat.chat_completion", new_callable=AsyncMock, return_value=reply),
        patch(
            "app.api.chat.chat_completion_stream",
            side_effect=lambda **kwargs: _fake_stream(),
        ),
        patch(
            "app.services.qa_service.chat_completion",
            new_callable=AsyncMock,
            return_value=reply,
        ),
        patch(
            "app.services.training_plan_generator.chat_completion",
            new_callable=AsyncMock,
            return_value=reply,
        ),
        patch(
            "app.services.doubao_client.chat_completion_stream",
            side_effect=lambda **kwargs: _fake_stream(),
        ),
        patch("app.services.doubao_client.is_configured", return_value=True),
        patch("app.api.guide.is_configured", return_value=True),
        patch("app.api.chat.is_configured", return_value=True),
    ):
        yield {"chat": mock_chat, "stream": _fake_stream}


@pytest.fixture
def client(db_session, mock_jnao, mock_doubao):
    def override_get_db():
        yield db_session

    from main import app

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def registered_user(client) -> dict:
    res = client.post(
        "/api/auth/register",
        json={"parent_phone": "13900139001", "nickname": "无测评童"},
    )
    assert res.status_code == 200
    return res.json()


@pytest.fixture
def child_with_assessment(db_session: Session) -> int:
    user = register_child(db_session, parent_phone="13800138000", nickname="测试童")
    save_assessment(
        db_session,
        child_user_id=user.id,
        jnao_record_id="r1",
        answer_bitstring="1" * 35,
        test_type=1,
        report={"talent": "学者", "create_time": "2026-06-18"},
    )
    return user.id


@pytest.fixture
def user_ready_for_training(client, mock_jnao) -> int:
    reg = client.post(
        "/api/auth/register",
        json={"parent_phone": "13600136001", "nickname": "训练童"},
    )
    uid = reg.json()["child_user_id"]
    client.post(
        "/api/talent/report",
        json={
            "answer": "1" * 35,
            "uid": 888001,
            "type": 1,
            "child_user_id": uid,
        },
    )
    return uid
