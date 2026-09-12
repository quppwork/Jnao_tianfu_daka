"""家长版大宇对话：意图路由 + API 形态。"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services import auth_service
from app.services.parent_guide_service import (
    wants_course_kb,
    wants_live_child_data,
)


def test_intent_live_training():
    assert wants_live_child_data("孩子最近训练数据怎么样")
    assert wants_live_child_data("今天打卡完成了吗")


def test_intent_live_report():
    assert wants_live_child_data("孩子的天赋报告怎么看")
    assert wants_live_child_data("他是什么天赋")


def test_intent_course_kb():
    assert wants_course_kb("家长课程有哪些")
    assert wants_course_kb("家长课堂怎么学")


def test_pick_source_parent_course():
    from app.agents.guide.kb_agent import pick_source_by_tags
    from app.services.kb_registry import get_kb_registry

    get_kb_registry.cache_clear()
    src = pick_source_by_tags("家长课堂讲什么")
    assert src is not None
    assert src.key == "talent_doc"


@pytest.mark.asyncio
async def test_run_parent_turn_routes_course_to_kb(db_session: Session):
    from app.services import parent_guide_service

    parent = auth_service.register_child(
        db_session,
        parent_phone="13900008801",
        nickname="家长甲",
        role=auth_service.ROLE_PARENT,
        password="Passw0rd!",
    )
    child = auth_service.register_child(
        db_session,
        parent_phone="13900008801",
        nickname="孩子甲",
        role=auth_service.ROLE_STUDENT,
        password="Passw0rd!",
    )
    auth_service.bind_parent_child(db_session, parent.id, child.id)
    db_session.commit()

    with patch(
        "app.services.parent_guide_service._kb_or_minimal_reply",
        new=AsyncMock(
            return_value={
                "reply": "课堂说明",
                "actions": [],
                "tools_used": [],
                "rag_used": True,
                "rag_source": "kb_qa_agent",
                "focus_child_id": child.id,
            }
        ),
    ) as kb_mock, patch(
        "app.services.parent_guide_service._live_child_reply",
        new=AsyncMock(),
    ) as live_mock:
        out = await parent_guide_service.run_parent_turn(
            db_session, parent.id, "家长课程怎么学"
        )

    assert out["reply"] == "课堂说明"
    assert kb_mock.await_count == 1
    assert live_mock.await_count == 0


@pytest.mark.asyncio
async def test_run_parent_turn_routes_train_to_live(db_session: Session):
    from app.services import parent_guide_service

    parent = auth_service.register_child(
        db_session,
        parent_phone="13900008802",
        nickname="家长乙",
        role=auth_service.ROLE_PARENT,
        password="Passw0rd!",
    )
    child = auth_service.register_child(
        db_session,
        parent_phone="13900008802",
        nickname="孩子乙",
        role=auth_service.ROLE_STUDENT,
        password="Passw0rd!",
    )
    auth_service.bind_parent_child(db_session, parent.id, child.id)
    db_session.commit()

    with patch(
        "app.services.parent_guide_service._live_child_reply",
        new=AsyncMock(
            return_value={
                "reply": "训练摘要",
                "actions": [],
                "tools_used": [{"name": "get_today_plan", "ok": True}],
                "rag_used": False,
                "rag_source": "parent_live_tools",
                "focus_child_id": child.id,
            }
        ),
    ) as live_mock, patch(
        "app.services.parent_guide_service._kb_or_minimal_reply",
        new=AsyncMock(),
    ) as kb_mock:
        out = await parent_guide_service.run_parent_turn(
            db_session, parent.id, "孩子训练数据怎么样"
        )

    assert out["rag_source"] == "parent_live_tools"
    assert live_mock.await_count == 1
    assert kb_mock.await_count == 0


def test_parent_guide_chat_api_requires_parent(
    client: TestClient, db_session: Session, child_with_assessment: int
):
    """学生 token 不能打家长引导接口。"""
    uid = child_with_assessment
    res = client.post(
        f"/api/parent/guide/chat?user_id={uid}",
        json={"message": "家长课程有哪些"},
    )
    assert res.status_code in (401, 403)
