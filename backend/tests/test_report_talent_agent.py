"""成人报告天赋解答：ReAct + RAG 工具，按报告隔离，契约与失败检查。"""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import ChildUser, ReportTalentMessage, TalentAssessment
from app.harness.rag_contract import (
    fail_payload,
    validate_talent_doc_input,
    validate_talent_doc_output,
)
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


def test_rag_input_contract():
    assert validate_talent_doc_input({"query": "学者怎么练"}) is None
    assert validate_talent_doc_input({}) is not None
    assert validate_talent_doc_input({"query": "x", "hack": 1}) is not None
    assert validate_talent_doc_input({"query": "x", "top_n": 99}) is not None


def test_rag_output_contract():
    ok = {
        "ok": True,
        "source_key": "talent_doc",
        "index_id": "x1micrdmjq",
        "query": "q",
        "hit_count": 1,
        "hits": [{"text": "片段"}],
    }
    assert validate_talent_doc_output(ok) is None
    bad = fail_payload(query="q", error="x", error_kind="empty")
    # empty fail payload is ok=false with hit_count 0
    assert validate_talent_doc_output(bad) is None
    wrong_src = dict(ok, source_key="video_practice")
    assert validate_talent_doc_output(wrong_src) is not None


@pytest.mark.asyncio
async def test_threads_stay_on_their_own_report(db):
    a = _assessment(db, talent="学者", phone="13800000011")
    b = _assessment(db, talent="思者", phone="13800000012")

    turns = [
        {
            "reply": "按库内练法，先从阅读起步。",
            "tools_used": [{"name": "talent_doc_retrieve", "ok": True}],
            "rag_used": True,
            "llm_calls": 2,
        },
        {
            "reply": "第一步是阅读。",
            "tools_used": [{"name": "talent_doc_retrieve", "ok": True}],
            "rag_used": True,
            "llm_calls": 2,
        },
        {
            "reply": "思者重在条理。",
            "tools_used": [{"name": "talent_doc_retrieve", "ok": True}],
            "rag_used": True,
            "llm_calls": 1,
        },
    ]

    with patch(
        "app.runtime.run_turn",
        new=AsyncMock(side_effect=turns),
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
    listed = agent.list_messages(db, a)
    assert listed["opening"] == agent.OPENING
    assert listed["messages"][0]["content"] != agent.OPENING


@pytest.mark.asyncio
async def test_tool_all_failed_forces_refusal(db):
    row = _assessment(db, phone="13800000021")
    with patch(
        "app.runtime.run_turn",
        new=AsyncMock(
            return_value={
                "reply": "我可以自由发挥一段。",
                "tools_used": [
                    {
                        "name": "talent_doc_retrieve",
                        "ok": False,
                        "error": "runtime",
                    }
                ],
                "rag_used": False,
                "llm_calls": 1,
            }
        ),
    ):
        out = await agent.ask(db, row, "学者怎么练")
    assert out["refused"] is True
    assert out["assistant"]["content"] == agent.REFUSAL
    assert out["tool_check"]["all_failed"] is True
    assert out["assistant"]["retrieved"] == 0


@pytest.mark.asyncio
async def test_greeting_without_tool_is_accepted(db):
    """问候不强制查库：未调工具时采信模型直接回复。"""
    row = _assessment(db, phone="13800000022")
    with patch(
        "app.runtime.run_turn",
        new=AsyncMock(
            return_value={
                "reply": "你好！我是天赋解答助手，关于这份报告你想了解哪一块？",
                "tools_used": [],
                "rag_used": False,
                "llm_calls": 1,
            }
        ),
    ):
        out = await agent.ask(db, row, "你好")
    assert out["refused"] is False
    assert out["assistant"]["retrieved"] == 0
    assert "天赋解答助手" in out["assistant"]["content"]


@pytest.mark.asyncio
async def test_tool_empty_still_refuses(db):
    row = _assessment(db, phone="13800000024")
    with patch(
        "app.runtime.run_turn",
        new=AsyncMock(
            return_value={
                "reply": "我可以编一段。",
                "tools_used": [
                    {"name": "talent_doc_retrieve", "ok": False, "error": "empty"}
                ],
                "rag_used": False,
                "llm_calls": 1,
            }
        ),
    ):
        out = await agent.ask(db, row, "学者怎么练")
    assert out["refused"] is True
    assert out["assistant"]["content"] == agent.REFUSAL


def test_child_report_rejected(db):
    row = _assessment(db, test_type=1, phone="13800000023")
    with pytest.raises(agent.ReportTalentError) as ei:
        agent.list_messages(db, row)
    assert ei.value.status_code == 403


def test_tool_round_default_is_one():
    """默认只查一次库：1 轮工具 + 回答，避免多轮拖垮首字。"""
    assert agent.MAX_TOOL_ROUNDS == 1
    assert agent.MAX_STEPS >= agent.MAX_TOOL_ROUNDS + 1


def test_derive_citations_keyword_map():
    assert agent._derive_citations("你的执行力偏弱，可以先从目标拆解练起。") == ["五维能量星图"]
    assert agent._derive_citations("名人堂里的榜样都有这个特质。") == ["名人堂"]
    assert agent._derive_citations("去天赋剧场看看短片。") == ["天赋剧场"]
    assert agent._derive_citations("你好呀") == []
    assert agent._derive_citations(agent.REFUSAL) == []
    assert agent._derive_citations("") == []
    # 最多 MAX_CITATIONS 个，按章节表顺序取
    many = agent._derive_citations("执行力、领导力都弱，名人堂和剧场也值得看。")
    assert many == ["五维能量星图", "名人堂"]


def test_suggested_chips_follow_talent():
    chips = agent._suggested_chips("赢者")
    assert chips[0] == {"q": "赢者怎么练", "hot": True}
    assert any(c["q"] == "五者是什么" for c in chips)
    empty = agent._suggested_chips("")
    assert empty[0]["q"] == "这个天赋怎么练"


@pytest.mark.asyncio
async def test_chat_payload_carries_chips_and_citations(db):
    row = _assessment(db, talent="学者", phone="13800000031")
    with patch(
        "app.runtime.run_turn",
        new=AsyncMock(
            return_value={
                "reply": "你的协调力不错，执行力可以再练。",
                "tools_used": [{"name": "talent_doc_retrieve", "ok": True}],
                "rag_used": True,
                "llm_calls": 2,
            }
        ),
    ):
        out = await agent.ask(db, row, "我哪项能力强")
    assert out["assistant"]["citations"] == ["五维能量星图"]
    assert out["user"]["citations"] == []

    listed = agent.list_messages(db, row)
    assert listed["chips"][0]["q"] == "学者怎么练"
    assistant_msgs = [m for m in listed["messages"] if m["role"] == "assistant"]
    assert assistant_msgs[0]["citations"] == ["五维能量星图"]

# ── 新增：报告正文切片 / RAG 章节引用 / SSE ─────────────────────────────


def test_report_context_slices_scores():
    from app.services.report_talent_context import build_report_context

    ctx = build_report_context(
        {
            "talent": "思者",
            "check_talent": "思德",
            "AttributeJs": '{"学者":2,"思者":3,"行者":2,"德者":2,"赢者":2}',
            "results": {
                "Ability": [
                    {"abilityName": "执行力", "grade": 3, "value": 62, "desp": "<p>略</p>"},
                    {"abilityName": "领导力", "grade": 2, "value": 57},
                ],
                "State": {"name": "无惧", "desp": "<p>状态说明</p>"},
                "Talent": {"desp": "<p><strong>【天赋能力解读】</strong>思者重条理</p>"},
                "TalentType": {"name": "机制应变型"},
            },
        },
        "思者",
    )
    assert "思者" in ctx and "德者" in ctx
    assert "执行力 62（3级）" in ctx
    assert "领导力 57（2级）" in ctx
    assert "无惧" in ctx and "机制应变型" in ctx
    assert "<p>" not in ctx


def test_report_context_empty_report():
    from app.services.report_talent_context import build_report_context

    assert build_report_context(None, "学者") == ""
    assert build_report_context({}, "学者") == ""


def test_sections_from_hits_uses_metadata():
    from app.services.report_talent_sections import sections_from_hits

    hits = [
        {"title": "五维能量星图·执行力", "text": "正文"},
        {"title": "名人堂", "doc_name": "榜样故事"},
        {"title": "无关", "doc_name": "其他"},
    ]
    assert sections_from_hits(hits) == ["五维能量星图", "名人堂"]
    assert sections_from_hits([]) == []
    assert sections_from_hits(None) == []


@pytest.mark.asyncio
async def test_ask_citations_prefer_tool_hits(db):
    row = _assessment(db, phone="13800000041")
    with patch(
        "app.runtime.run_turn",
        new=AsyncMock(
            return_value={
                "reply": "库内提到先做目标拆解。",
                "tools_used": [{"name": "talent_doc_retrieve", "ok": True}],
                "citations": ["名人堂"],
                "rag_used": True,
                "llm_calls": 2,
            }
        ),
    ):
        out = await agent.ask(db, row, "怎么练")
    assert out["assistant"]["citations"] == ["名人堂"]
    listed = agent.list_messages(db, row)
    assert listed["messages"][-1]["citations"] == ["名人堂"]


def _stream_events(events):
    async def _gen(*_args, **_kwargs):
        for item in events:
            yield item

    return _gen


@pytest.mark.asyncio
async def test_ask_stream_tokens_then_done(db):
    row = _assessment(db, phone="13800000042")
    done = {
        "reply": "第一步是阅读。",
        "tools_used": [{"name": "talent_doc_retrieve", "ok": True}],
        "citations": ["五维能量星图"],
        "rag_used": True,
        "llm_calls": 2,
    }
    with patch(
        "app.runtime.run_turn_stream",
        new=_stream_events(
            [("token", "第一步"), ("token", "是阅读。"), ("done", done)]
        ),
    ):
        items = [item async for item in agent.ask_stream(db, row, "学者怎么练")]

    kinds = [k for k, _ in items]
    assert kinds == ["token", "token", "done"]
    assert items[-1][1]["assistant"]["content"] == "第一步是阅读。"
    assert items[-1][1]["assistant"]["citations"] == ["五维能量星图"]

    listed = agent.list_messages(db, row)
    assert [m["role"] for m in listed["messages"]] == ["user", "assistant"]
    assert listed["messages"][-1]["citations"] == ["五维能量星图"]


@pytest.mark.asyncio
async def test_ask_stream_refusal_replaces_streamed_text(db):
    row = _assessment(db, phone="13800000043")
    done = {
        "reply": "我可以编一段。",
        "tools_used": [{"name": "talent_doc_retrieve", "ok": False, "error": "empty"}],
        "citations": [],
        "rag_used": False,
        "llm_calls": 2,
    }
    with patch(
        "app.runtime.run_turn_stream",
        new=_stream_events([("token", "我可以编一段。"), ("done", done)]),
    ):
        items = [item async for item in agent.ask_stream(db, row, "学者怎么练")]

    kinds = [k for k, _ in items]
    assert "replace" in kinds
    assert items[kinds.index("replace")][1] == agent.REFUSAL
    final = items[-1][1]
    assert final["refused"] is True
    assert final["assistant"]["content"] == agent.REFUSAL
    assert final["assistant"]["citations"] == []


def test_system_extra_carries_slices(db):
    from app.db.models import TalentAssessment

    user = ChildUser(
        parent_phone="13800000044", nickname="测", role="student", password_hash="x"
    )
    db.add(user)
    db.flush()
    row = TalentAssessment(
        child_user_id=user.id,
        test_type=0,
        talent_primary="学者",
        report_json={
            "results": {
                "Ability": [{"abilityName": "执行力", "grade": 3, "value": 66}],
            }
        },
    )
    db.add(row)
    db.commit()
    extra = agent._system_extra(row)
    assert "报告正文切片" in extra
    assert "执行力 66（3级）" in extra
    assert "尚未联调" not in extra
