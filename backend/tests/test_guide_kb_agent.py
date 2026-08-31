"""Guide KB Agent 单元测试。"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.guide.kb_agent import (
    is_homework_message,
    pick_source_by_tags,
)


def test_pick_source_video_practice():
    from app.services.kb_registry import get_kb_registry

    get_kb_registry.cache_clear()
    src = pick_source_by_tags("开口窍怎么练")
    assert src is not None
    assert src.key == "video_practice"


def test_pick_source_talent_doc():
    from app.services.kb_registry import get_kb_registry

    get_kb_registry.cache_clear()
    src = pick_source_by_tags("学者天赋特点")
    assert src is not None
    assert src.key == "talent_doc"


def test_pick_source_rocket_camp_to_doc():
    """新产品/营期问句应落文档库，而非不查库。"""
    from app.services.kb_registry import get_kb_registry

    get_kb_registry.cache_clear()
    src = pick_source_by_tags("什么是火箭提分营")
    assert src is not None
    assert src.key == "talent_doc"


def test_pick_source_skips_train_progress():
    assert pick_source_by_tags("今日训练怎么样") is None


def test_homework_redirect_pattern():
    assert is_homework_message("帮我做这道应用题")
    assert is_homework_message("我有数学题我该怎么办")


@pytest.mark.asyncio
async def test_plan_fills_query_when_fc_empty(monkeypatch):
    """豆包未调 query 时，启发式仍应补查文档库。"""
    monkeypatch.setenv("GUIDE_KB_AGENT", "1")
    from app.agents.guide import kb_agent
    from app.services.kb_registry import get_kb_registry

    get_kb_registry.cache_clear()

    with patch(
        "app.services.doubao_client.is_configured",
        return_value=True,
    ), patch(
        "app.services.doubao_client.chat_completion_message",
        new=AsyncMock(return_value={"role": "assistant", "content": "ok"}),
    ):
        picks = await kb_agent.plan_kb_tool_calls("什么是火箭提分营")

    assert any(p["name"] == "query_knowledge" for p in picks)
    q = next(p for p in picks if p["name"] == "query_knowledge")
    assert q["args"]["source_key"] == "talent_doc"

@pytest.mark.asyncio
async def test_run_guide_kb_turn_mock_query(monkeypatch):
    monkeypatch.setenv("GUIDE_KB_AGENT", "1")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test")
    monkeypatch.setenv("BAILIAN_WORKSPACE_ID", "ws-test")

    from app.agents.guide.context import GuideContext
    from app.agents.guide import kb_agent
    from app.services.knowledge import KnowledgeAnswer

    kb_agent.get_kb_registry.cache_clear()

    ans = KnowledgeAnswer(
        kind="chat",
        query="开口窍怎么练",
        text="开口窍从慢到快练朗读，先去今日训练看示范。",
        sources=[],
        chat=type(
            "R",
            (),
            {"reply": "开口窍从慢到快练朗读，先去今日训练看示范。", "request_id": "r1", "retrieved_docs": []},
        )(),
        meta={"request_id": "r1"},
    )

    with patch(
        "app.agents.guide.kb_agent.plan_kb_tool_calls",
        new=AsyncMock(return_value=[]),
    ), patch(
        "app.agents.guide.tools.kb_tools.answer_chat_sync",
        return_value=ans,
    ), patch(
        "app.agents.guide.runner._meta_from_ctx",
        return_value={"actions": [], "tools_used": []},
    ):
        ctx = GuideContext(1, "2026-08-27", situation="ready_to_train")
        result = await kb_agent.run_guide_kb_turn(
            object(), 1, "开口窍怎么练", ctx=ctx
        )

    assert result is not None
    assert result.get("rag_source") == "kb_qa_agent"
    assert "开口窍" in result["reply"]
