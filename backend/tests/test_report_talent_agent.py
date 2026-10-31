"""成人报告天赋解答：优先 knowledge_qa，原样返回。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import ChildUser, ReportTalentMessage, TalentAssessment
from app.harness.types import ToolResult
from app.services import report_talent_agent as agent


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


def _assessment(db, *, talent="学者", test_type=0, phone="13800000001"):
    user = ChildUser(
        parent_phone=phone,
        nickname="测",
        role="student",
        password_hash="x",
    )
    db.add(user)
    db.flush()
    row = TalentAssessment(
        child_user_id=user.id,
        test_type=test_type,
        talent_primary=talent,
        report_json={"talent": talent},
    )
    db.add(row)
    db.commit()
    return row


def _ok_tool(reply: str = "五者是一套诊断体系。") -> ToolResult:
    return ToolResult(
        ok=True,
        name=agent.TOOL_NAME,
        data={
            "ok": True,
            "reply": reply,
            "aid": "aid-9eca891478184a39a7e0d37419919ae9",
            "request_id": "rid-1",
        },
    )


@pytest.mark.asyncio
async def test_ask_returns_knowledge_qa_as_is(db):
    row = _assessment(db, phone="13800000011")
    with patch(
        "app.harness.runtime.call_tool",
        new=AsyncMock(return_value=_ok_tool("按库内练法，先从阅读起步。")),
    ) as mock_tool:
        out = await agent.ask(db, row, "学者怎么练")
    assert mock_tool.await_count == 1
    assert mock_tool.call_args.args[0] == "knowledge_qa"
    assert out["refused"] is False
    assert out["assistant"]["content"] == "按库内练法，先从阅读起步。"
    assert out["assistant"]["retrieved"] == 1
    assert out["tools_used"][0]["name"] == "knowledge_qa"
    assert out["llm_calls"] == 0


@pytest.mark.asyncio
async def test_ask_tool_fail_uses_link_fallback(db):
    row = _assessment(db, phone="13800000021")
    fail = ToolResult(ok=False, name=agent.TOOL_NAME, error="timeout", data={})
    with patch("app.harness.runtime.call_tool", new=AsyncMock(return_value=fail)):
        out = await agent.ask(db, row, "学者怎么练")
    assert out["refused"] is True
    assert out["assistant"]["content"] == agent.TOOL_FAIL


@pytest.mark.asyncio
async def test_threads_stay_on_their_own_report(db):
    a = _assessment(db, talent="学者", phone="13800000031")
    b = _assessment(db, talent="思者", phone="13800000032")
    with patch(
        "app.harness.runtime.call_tool",
        new=AsyncMock(
            side_effect=[
                _ok_tool("A1"),
                _ok_tool("A2"),
                _ok_tool("B1"),
            ]
        ),
    ):
        await agent.ask(db, a, "学者怎么练")
        await agent.ask(db, a, "刚才说的第一步是什么")
        await agent.ask(db, b, "思者怎么练")

    a_msgs = db.scalars(
        select(ReportTalentMessage).where(ReportTalentMessage.assessment_id == a.id)
    ).all()
    b_msgs = db.scalars(
        select(ReportTalentMessage).where(ReportTalentMessage.assessment_id == b.id)
    ).all()
    assert [m.role for m in a_msgs] == ["user", "assistant", "user", "assistant"]
    assert len(b_msgs) == 2


def test_child_report_rejected(db):
    row = _assessment(db, test_type=1, phone="13800000023")
    with pytest.raises(agent.ReportTalentError) as ei:
        agent.list_messages(db, row)
    assert ei.value.status_code == 403


def test_suggested_chips_follow_talent():
    chips = agent._suggested_chips("赢者", user_id=1, visit_key="fixed")
    assert len(chips) == 4
    assert all("q" in c for c in chips)
    assert "{talent}" not in " ".join(c["q"] for c in chips)
    # 池内含天赋占位条；洗牌后至少整池渲染不含占位符
    one = agent._suggested_chips("赢者", user_id=1, visit_key="talent-only")
    assert any("赢者" in c["q"] or "报告" in c["q"] or "五者" in c["q"] for c in one)


def _stream_events(events):
    async def _gen(*_a, **_k):
        for item in events:
            yield item

    return _gen


@pytest.mark.asyncio
async def test_ask_stream_tokens_then_done(db):
    row = _assessment(db, phone="13800000042")
    result = MagicMock()
    result.reply = "第一步是阅读。"
    result.aid = "aid-x"
    result.request_id = "r1"
    with patch(
        "app.services.bailian.knowledge_chat.knowledge_chat_stream",
        new=_stream_events(
            [("token", "第一步"), ("token", "是阅读。"), ("result", result)]
        ),
    ), patch(
        "app.services.kb_policy.knowledge_qa_aid",
        return_value="aid-x",
    ), patch(
        "app.services.bailian.config.load_bailian_config",
        return_value=MagicMock(),
    ):
        items = [item async for item in agent.ask_stream(db, row, "学者怎么练")]

    kinds = [k for k, _ in items]
    assert kinds == ["token", "token", "done"]
    assert items[-1][1]["assistant"]["content"] == "第一步是阅读。"
    assert items[-1][1]["refused"] is False


@pytest.mark.asyncio
async def test_ask_stream_empty_uses_tool_fail(db):
    row = _assessment(db, phone="13800000043")
    with patch(
        "app.services.bailian.knowledge_chat.knowledge_chat_stream",
        new=_stream_events([("result", None)]),
    ), patch(
        "app.services.kb_policy.knowledge_qa_aid", return_value="aid-x"
    ), patch(
        "app.services.bailian.config.load_bailian_config",
        return_value=MagicMock(),
    ):
        items = [item async for item in agent.ask_stream(db, row, "学者怎么练")]
    assert items[0] == ("token", agent.TOOL_FAIL)
    assert items[-1][1]["refused"] is True
    assert items[-1][1]["assistant"]["content"] == agent.TOOL_FAIL
