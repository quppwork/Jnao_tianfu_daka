"""百炼直答集成测试"""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_training_retrieve_doubao_primary(monkeypatch):
    monkeypatch.setenv("BAILIAN_WORKSPACE_ID", "ws-test")
    monkeypatch.setenv("BAILIAN_VIDEO_INDEX_ID", "l37mx47k4u")
    monkeypatch.setenv("TRAINING_RAG_ENABLED", "1")
    monkeypatch.setenv("BAILIAN_RAG_GENERATE", "0")
    monkeypatch.setenv("BAILIAN_RAG_FALLBACK_DOUBAO", "1")
    monkeypatch.setenv("OSS_ACCESS_KEY_ID", "ak")
    monkeypatch.setenv("OSS_ACCESS_KEY_SECRET", "sk")

    with patch(
        "app.services.bailian.training_knowledge_reply",
        new=AsyncMock(),
    ) as direct, patch(
        "app.services.training_plan_generator._gather_training_rag_block",
        new=AsyncMock(return_value="训练要点：专注听完影像追忆"),
    ), patch(
        "app.services.training_plan_generator.chat_completion",
        new=AsyncMock(return_value="今天认真听影像追忆，听完打卡。"),
    ) as doubao:
        from app.services.training_plan_generator import generate_daily_report_text

        text = await generate_daily_report_text(
            None,
            1,
            lesson_title="影像追忆",
            talent_primary="学者",
        )
        assert "打卡" in text
        direct.assert_not_called()
        doubao.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_daily_report_uses_bailian_direct(monkeypatch):
    monkeypatch.setenv("BAILIAN_WORKSPACE_ID", "ws-test")
    monkeypatch.setenv("BAILIAN_API_HOST", "ws-test.cn-beijing.maas.aliyuncs.com")
    monkeypatch.setenv("BAILIAN_VIDEO_INDEX_ID", "l37mx47k4u")
    monkeypatch.setenv("TRAINING_RAG_ENABLED", "1")
    monkeypatch.setenv("BAILIAN_RAG_GENERATE", "1")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test")

    with patch(
        "app.services.bailian.training_knowledge_reply",
        new=AsyncMock(return_value="今天先听影像追忆，听完记得打卡哦。"),
    ) as gen:
        from app.services.training_plan_generator import generate_daily_report_text

        text = await generate_daily_report_text(
            None,
            1,
            lesson_title="影像追忆",
            talent_primary="学者",
        )
        assert "打卡" in text
        gen.assert_awaited_once()


@pytest.mark.asyncio
async def test_training_fallback_to_doubao_when_bailian_fails(monkeypatch):
    monkeypatch.setenv("BAILIAN_WORKSPACE_ID", "ws-test")
    monkeypatch.setenv("BAILIAN_API_HOST", "ws-test.cn-beijing.maas.aliyuncs.com")
    monkeypatch.setenv("BAILIAN_VIDEO_INDEX_ID", "l37mx47k4u")
    monkeypatch.setenv("TRAINING_RAG_ENABLED", "1")
    monkeypatch.setenv("BAILIAN_RAG_GENERATE", "1")
    monkeypatch.setenv("BAILIAN_RAG_FALLBACK_DOUBAO", "1")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test")

    with patch(
        "app.services.bailian.training_knowledge_reply",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.services.training_plan_generator._gather_training_rag_block",
        new=AsyncMock(return_value="训练要点：专注听完"),
    ), patch(
        "app.services.training_plan_generator.chat_completion",
        new=AsyncMock(return_value="今天认真听影像追忆，听完打卡。"),
    ) as doubao:
        from app.services.training_plan_generator import generate_daily_report_text

        text = await generate_daily_report_text(
            None,
            1,
            lesson_title="影像追忆",
            talent_primary="学者",
        )
        assert "打卡" in text
        doubao.assert_awaited_once()


@pytest.mark.asyncio
async def test_guide_bailian_direct_skips_doubao(monkeypatch):
    monkeypatch.setenv("GUIDE_RAG_ENABLED", "1")
    monkeypatch.setenv("BAILIAN_RAG_GENERATE", "1")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test")
    monkeypatch.setenv("BAILIAN_INDEX_ID", "idx-doc")
    monkeypatch.setenv("BAILIAN_WORKSPACE_ID", "ws-test")
    monkeypatch.setenv("BAILIAN_API_HOST", "ws-test.cn-beijing.maas.aliyuncs.com")
    monkeypatch.setenv("OSS_ACCESS_KEY_ID", "ak")
    monkeypatch.setenv("OSS_ACCESS_KEY_SECRET", "sk")

    with patch(
        "app.agents.guide.runner._try_bailian_direct_reply",
        new=AsyncMock(return_value=("学者天赋注重逻辑思考。", True)),
    ), patch(
        "app.services.doubao_client.chat_completion",
        new=AsyncMock(),
    ) as doubao:
        from app.agents.guide.runner import run_chat

        class _Db:
            pass

        with patch("app.agents.guide.runner._prepare_context"), patch(
            "app.agents.guide.runner._prepare_memory_and_history",
            return_value=([], ""),
        ), patch(
            "app.agents.guide.kb_agent.guide_kb_agent_ready",
            return_value=False,
        ), patch(
            "app.agents.guide.runner._gather_tools",
            new=AsyncMock(return_value=([], "")),
        ), patch(
            "app.agents.guide.runner._meta_from_ctx",
            return_value={"situation": "idle", "actions": []},
        ):
            result = await run_chat(_Db(), 1, "学者有什么特点")
        assert "学者" in result["reply"]
        assert result.get("pipeline_path") == "legacy_rag"
        doubao.assert_not_called()
