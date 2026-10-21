"""引导页：优先 Agent 工具 knowledge_qa 原样返回。"""

from unittest.mock import AsyncMock, patch

import pytest

from app.harness.types import ToolResult


@pytest.mark.asyncio
async def test_guide_knowledge_qa_primary(monkeypatch):
    monkeypatch.setenv("GUIDE_RAG_ENABLED", "1")

    hit = ToolResult(
        ok=True,
        name="knowledge_qa",
        data={
            "ok": True,
            "reply": "超脑阅读从扫读开始，先抓关键词。",
            "aid": "aid-x",
        },
    )

    with patch(
        "app.harness.runtime.call_tool",
        new=AsyncMock(return_value=hit),
    ) as mock_tool, patch(
        "app.agents.guide.kb_agent.guide_kb_agent_ready",
        return_value=False,
    ), patch(
        "app.agents.guide.runner._prepare_context",
    ), patch(
        "app.agents.guide.runner._prepare_memory_and_history",
        return_value=([], ""),
    ), patch(
        "app.agents.guide.runner._meta_from_ctx",
        side_effect=lambda *_a, tools_used=None, **_k: {
            "situation": "ready_to_train",
            "actions": [],
            "tools_used": list(tools_used or []),
        },
    ):
        from app.agents.guide.runner import run_chat

        result = await run_chat(object(), 1, "超脑阅读怎么练")

    assert mock_tool.await_count == 1
    assert mock_tool.call_args.args[0] == "knowledge_qa"
    assert "扫读" in result["reply"]
    assert result.get("rag_source") == "knowledge_qa"
    assert result.get("pipeline_path") == "legacy_rag"
    assert result["tools_used"][0]["name"] == "knowledge_qa"


@pytest.mark.asyncio
async def test_guide_knowledge_qa_miss_falls_to_template(monkeypatch):
    monkeypatch.setenv("GUIDE_RAG_ENABLED", "1")
    monkeypatch.setenv("BAILIAN_RAG_GENERATE", "0")
    monkeypatch.setenv("BAILIAN_INDEX_ID", "idx-doc")
    monkeypatch.setenv("BAILIAN_WORKSPACE_ID", "ws-test")
    monkeypatch.setenv("OSS_ACCESS_KEY_ID", "ak")
    monkeypatch.setenv("OSS_ACCESS_KEY_SECRET", "sk")

    miss = ToolResult(
        ok=False,
        name="knowledge_qa",
        error="empty",
        data={"ok": False, "error_kind": "empty"},
    )
    # 后续 legacy retrieve 也 miss
    retrieve_miss = ToolResult(
        ok=True,
        name="retrieve_kb",
        data={"rag_used": False, "rag_block": "", "sources": []},
    )

    async def _call(name, *_a, **_k):
        if name == "knowledge_qa":
            return miss
        return retrieve_miss

    with patch(
        "app.agents.guide.runner._try_bailian_direct_reply",
        new=AsyncMock(return_value=("不应出现", True)),
    ) as direct, patch(
        "app.harness.runtime.call_tool",
        new=AsyncMock(side_effect=_call),
    ), patch(
        "app.runtime.run_turn",
        new=AsyncMock(return_value={"reply": "请去今日训练看看。", "tools_used": []}),
    ) as harness, patch(
        "app.agents.guide.kb_agent.guide_kb_agent_ready",
        return_value=False,
    ), patch("app.agents.guide.runner._prepare_context"), patch(
        "app.agents.guide.runner._prepare_memory_and_history",
        return_value=([], ""),
    ), patch(
        "app.agents.guide.runner._meta_from_ctx",
        return_value={"situation": "idle", "actions": []},
    ):
        from app.agents.guide.runner import run_chat

        result = await run_chat(object(), 1, "学者天赋是什么")

    direct.assert_not_called()
    harness.assert_not_called()
    assert result.get("rag_source") == "template_fallback"
    assert result.get("pipeline_path") == "legacy_rag"
    assert "天赋" in result["reply"]
