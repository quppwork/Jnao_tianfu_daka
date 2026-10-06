"""引导页 Retrieve → 豆包 主链路测试。"""

from unittest.mock import AsyncMock, patch

import pytest

from app.harness.types import ToolResult


@pytest.mark.asyncio
async def test_guide_retrieve_doubao_primary(monkeypatch):
    monkeypatch.setenv("GUIDE_RAG_ENABLED", "1")
    monkeypatch.setenv("BAILIAN_RAG_GENERATE", "0")
    monkeypatch.setenv("BAILIAN_INDEX_ID", "idx-doc")
    monkeypatch.setenv("BAILIAN_WORKSPACE_ID", "ws-test")
    monkeypatch.setenv("OSS_ACCESS_KEY_ID", "ak")
    monkeypatch.setenv("OSS_ACCESS_KEY_SECRET", "sk")

    captured: dict = {}

    def _fake_system_prompt(
        db,
        child_user_id,
        *,
        tool_block="",
        memory_block="",
        rag_block="",
        message="",
    ):
        captured["rag_block"] = rag_block
        captured["tool_block"] = tool_block
        return "SYSTEM"

    async def _fake_turn(profile, user_message, **kwargs):
        captured["system"] = kwargs.get("system_override")
        captured["user"] = user_message
        return {"reply": "先从扫读练起，抓关键词再理解，去今日训练试试。", "rag_used": False, "tools_used": []}

    hit = ToolResult(
        ok=True,
        name="retrieve_kb",
        data={
            "rag_used": True,
            "rag_block": "超脑阅读从扫读开始，先抓关键词。",
            "sources": ["训练手册"],
        },
    )

    with patch(
        "app.harness.runtime.call_tool",
        new=AsyncMock(return_value=hit),
    ), patch(
        "app.harness.turn.run_profile_turn",
        new=AsyncMock(side_effect=_fake_turn),
    ), patch(
        "app.agents.guide.runner._try_bailian_direct_reply",
        new=AsyncMock(),
    ) as direct, patch(
        "app.agents.guide.runner.build_kb_primary_system_prompt",
        side_effect=_fake_system_prompt,
    ), patch(
        "app.agents.guide.kb_agent.guide_kb_agent_ready",
        return_value=False,
    ), patch(
        "app.agents.guide.runner._prepare_context",
    ), patch(
        "app.agents.guide.runner._prepare_memory_and_history",
        return_value=([], ""),
    ), patch(
        "app.agents.guide.runner._gather_tools",
        new=AsyncMock(return_value=([{"name": "get_today_plan", "ok": True}], "今日有训练方案")),
    ), patch(
        "app.agents.guide.runner._meta_from_ctx",
        return_value={"situation": "ready_to_train", "actions": []},
    ):
        from app.agents.guide.runner import run_chat

        result = await run_chat(object(), 1, "超脑阅读怎么练")

    assert "扫读" in result["reply"]
    assert result.get("rag_source") == "retrieve_doubao"
    assert result.get("rag_sources")
    assert result.get("pipeline_path") == "legacy_rag"
    direct.assert_not_called()
    assert "超脑阅读从扫读开始" in captured["rag_block"]
    assert "今日有训练方案" in captured["tool_block"]


@pytest.mark.asyncio
async def test_guide_skips_direct_when_generate_off(monkeypatch):
    monkeypatch.setenv("GUIDE_RAG_ENABLED", "1")
    monkeypatch.setenv("BAILIAN_RAG_GENERATE", "0")
    monkeypatch.setenv("BAILIAN_INDEX_ID", "idx-doc")
    monkeypatch.setenv("BAILIAN_WORKSPACE_ID", "ws-test")
    monkeypatch.setenv("OSS_ACCESS_KEY_ID", "ak")
    monkeypatch.setenv("OSS_ACCESS_KEY_SECRET", "sk")

    miss = ToolResult(ok=True, name="retrieve_kb", data={"rag_used": False, "rag_block": "", "sources": []})

    with patch(
        "app.agents.guide.runner._try_bailian_direct_reply",
        new=AsyncMock(return_value=("不应出现", True)),
    ) as direct, patch(
        "app.harness.runtime.call_tool",
        new=AsyncMock(return_value=miss),
    ), patch(
        "app.harness.turn.run_profile_turn",
        new=AsyncMock(return_value={"reply": "请去今日训练看看。", "tools_used": []}),
    ) as harness, patch(
        "app.agents.guide.kb_agent.guide_kb_agent_ready",
        return_value=False,
    ), patch("app.agents.guide.runner._prepare_context"), patch(
        "app.agents.guide.runner._prepare_memory_and_history",
        return_value=([], ""),
    ), patch(
        "app.agents.guide.runner._gather_tools",
        new=AsyncMock(return_value=([], "")),
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
