"""Guide KB Agent 单元测试。"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.guide.kb_agent import (
    is_homework_message,
    pick_source_by_tags,
    guide_kb_agent_ready,
)
from app.services.kb_registry import load_kb_registry


def test_pick_source_video_practice():
    reg = load_kb_registry()
    src = pick_source_by_tags("开口窍怎么练")
    assert src is not None
    assert src.key == "video_practice"


def test_pick_source_talent_doc():
    src = pick_source_by_tags("学者天赋特点")
    assert src is not None
    assert src.key == "talent_doc"


def test_homework_redirect_pattern():
    assert is_homework_message("帮我做这道应用题")


@pytest.mark.asyncio
async def test_run_guide_kb_turn_mock_query(monkeypatch):
    monkeypatch.setenv("GUIDE_KB_AGENT", "1")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test")
    monkeypatch.setenv("BAILIAN_WORKSPACE_ID", "ws-test")

    from app.agents.guide.context import GuideContext
    from app.agents.guide import kb_agent

    kb_agent.get_kb_registry.cache_clear()

    with patch(
        "app.agents.guide.kb_agent.plan_kb_tool_calls",
        new=AsyncMock(return_value=[]),
    ), patch(
        "app.agents.guide.tools.kb_tools.knowledge_chat_sync",
        return_value=type(
            "R",
            (),
            {
                "reply": "开口窍从慢到快练朗读，先去今日训练看示范。",
                "request_id": "r1",
                "retrieved_docs": [],
            },
        )(),
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
