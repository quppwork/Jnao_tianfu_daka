"""报告按需注入 + FAQ Redis：夹具来自 dayu 形态真实报告结构。"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import ChildUser
from app.services import report_talent_agent as agent
from app.services.legacy_dayu_service import build_report_json_from_dayu_row
from app.services.partner_report_chat_service import upsert_assessment_from_dayu

_FIXTURE = Path(__file__).parent / "fixtures" / "report_talent_dayu_sample.json"


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


@pytest.fixture()
def fixture_payload():
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture()
def assessment_from_dayu(db, fixture_payload):
    user = ChildUser(
        parent_phone="13900009901",
        nickname="夹具家长",
        role="parent",
        password_hash="x",
    )
    db.add(user)
    db.flush()
    row = upsert_assessment_from_dayu(
        db, child_user_id=user.id, dayu_row=fixture_payload["dayu_row"]
    )
    return row


def test_fixture_builds_report_json_like_online(fixture_payload):
    report = build_report_json_from_dayu_row(fixture_payload["dayu_row"])
    assert report["talent"] == "思者"
    assert "AttributeJs" in report or "results" in report
    from app.services.report_talent_context import build_report_context

    summary = build_report_context(report, "思者")
    assert "思者" in summary
    assert "五者分值" in summary or "五维" in summary or "状态" in summary


def test_cases_intent_matrix(fixture_payload):
    from app.services.report_talent_query import needs_report_context

    for case in fixture_payload["cases"]:
        assert needs_report_context(case["question"]) is case["needs_report"], case["id"]


@pytest.mark.asyncio
async def test_compose_skips_report_for_generic(db, assessment_from_dayu, fixture_payload):
    from app.services.report_talent_query import compose_kb_query

    case = next(c for c in fixture_payload["cases"] if c["id"] == "generic_kb")
    out = await compose_kb_query(db, assessment_from_dayu, case["question"])
    assert "【本份测评报告摘要】" not in out["query"]
    assert out["used_report"] is False
    assert out["query"] == case["question"]


@pytest.mark.asyncio
async def test_compose_loads_report_fragment_for_my_report(
    db, assessment_from_dayu, fixture_payload
):
    from app.services.report_talent_query import compose_kb_query

    case = next(c for c in fixture_payload["cases"] if c["id"] == "my_report")
    out = await compose_kb_query(db, assessment_from_dayu, case["question"])
    assert out["used_report"] is True
    assert "【本份测评报告摘要】" in out["query"]
    assert case["expect_fragment_contains"] in out["query"]
    assert out["report_tool"]["ok"] is True


@pytest.mark.asyncio
async def test_ask_stream_generic_does_not_call_report_tool(db, assessment_from_dayu):
    result = MagicMock()
    result.reply = "五者是诊断体系。"
    result.aid = "aid-x"
    result.request_id = "r1"
    captured = {}

    async def _stream(query, **_kw):
        captured["query"] = query
        yield ("token", "五者")
        yield ("token", "是诊断体系。")
        yield ("result", result)

    with (
        patch(
            "app.services.bailian.knowledge_chat.knowledge_chat_stream",
            new=_stream,
        ),
        patch("app.services.kb_policy.knowledge_qa_aid", return_value="aid-x"),
        patch(
            "app.services.bailian.config.load_bailian_config",
            return_value=MagicMock(),
        ),
        patch(
            "app.harness.runtime.call_tool",
            new=AsyncMock(side_effect=AssertionError("generic 不应调 get_report_content")),
        ),
    ):
        items = [
            item
            async for item in agent.ask_stream(
                db, assessment_from_dayu, "五者天赋体系是什么"
            )
        ]
    assert "【本份测评报告摘要】" not in captured["query"]
    assert items[-1][0] == "done"
    assert items[-1][1]["assistant"]["content"] == "五者是诊断体系。"


@pytest.mark.asyncio
async def test_ask_stream_report_question_uses_grounded_llm_not_knowledge_qa(
    db, assessment_from_dayu
):
    """问报告：报告事实 + RAG 方法 + 本地流式；禁止走 knowledge_qa 样例分。"""
    tool_calls: list[str] = []
    llm_messages: list = []

    async def _call_tool(name, args, **kw):
        from app.harness.types import ToolResult

        tool_calls.append(name)
        if name == "get_report_content":
            return ToolResult(
                ok=True,
                name=name,
                data={
                    "ok": True,
                    "content": (
                        "报告中标注天赋：思者\n"
                        "五维能量（星图）：执行力 85｜公信力 79｜协调力 76｜创新力 65｜领导力 41"
                    ),
                    "section": "全部",
                },
            )
        if name == "talent_doc_retrieve":
            return ToolResult(
                ok=True,
                name=name,
                data={
                    "ok": True,
                    "hits": [
                        {
                            "text": "解读方法：先列真实五维分，再谈优势与补短；示例分95仅供文案勿照抄。"
                        }
                    ],
                },
            )
        raise AssertionError(f"unexpected tool {name}")

    class _Route:
        async def stream(self, messages, tools=None, **overrides):
            llm_messages.extend(messages)
            yield "创新力 "
            yield "65"

        async def complete(self, messages, tools=None, **overrides):
            return {"role": "assistant", "content": "创新力 65"}

    with (
        patch("app.harness.runtime.call_tool", new=_call_tool),
        patch("app.harness.llm.route", return_value=_Route()),
        patch(
            "app.services.bailian.knowledge_chat.knowledge_chat_stream",
            new=AsyncMock(side_effect=AssertionError("报告问句不应打 knowledge_qa")),
        ),
    ):
        items = [
            item
            async for item in agent.ask_stream(
                db, assessment_from_dayu, "这份报告怎么看"
            )
        ]
    assert "get_report_content" in tool_calls
    assert "talent_doc_retrieve" in tool_calls
    user_blob = "\n".join(
        str(m.get("content") or "") for m in llm_messages if m.get("role") == "user"
    )
    assert "创新力 65" in user_blob
    assert "95" not in user_blob or "勿照抄" in user_blob
    assert items[-1][1]["used_report"] is True
    assert items[-1][1]["refused"] is False
    assert "65" in items[-1][1]["assistant"]["content"]


def test_build_report_context_emits_star_scores(fixture_payload):
    from app.services.legacy_dayu_service import build_report_json_from_dayu_row
    from app.services.report_talent_context import build_report_context

    report = build_report_json_from_dayu_row(fixture_payload["dayu_row"])
    summary = build_report_context(report, "思者")
    assert "创新力 65" in summary
    assert "执行力 85" in summary
    assert "领导力 41" in summary


@pytest.mark.asyncio
async def test_faq_cache_hit_skips_knowledge_stream(db, assessment_from_dayu):
    from app.services import report_talent_faq_cache as faq

    with (
        patch.object(
            faq,
            "get_cached_reply",
            return_value="缓存回答：五者是一套诊断体系。",
        ),
        patch(
            "app.services.bailian.knowledge_chat.knowledge_chat_stream",
            new=AsyncMock(side_effect=AssertionError("cache hit 不应打百炼")),
        ),
        patch("app.services.kb_policy.knowledge_qa_aid", return_value="aid-x"),
        patch(
            "app.services.bailian.config.load_bailian_config",
            return_value=MagicMock(),
        ),
    ):
        items = [
            item
            async for item in agent.ask_stream(
                db, assessment_from_dayu, "五者天赋体系是什么"
            )
        ]
    tokens = "".join(p for k, p in items if k == "token")
    assert "缓存回答" in tokens
    assert items[-1][1]["assistant"]["content"].startswith("缓存回答")
    assert items[-1][1].get("cache_hit") is True


def test_faq_cache_key_stable_for_normalized_question():
    from app.services.report_talent_faq_cache import cache_key_for_question

    a = cache_key_for_question("五者天赋体系是什么？", talent="")
    b = cache_key_for_question("  五者天赋体系是什么  ", talent="")
    assert a == b
